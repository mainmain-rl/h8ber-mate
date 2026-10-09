"""Scheduler services."""

import logging
from collections import defaultdict
from datetime import UTC, datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from src.k8s.services import K8sClient
from src.schedules.db import ScheduleDB
from src.shared.database import AsyncSessionLocal
from src.shared.settings import settings

logger = logging.getLogger(__name__)

# Get configured timezone
tz = pytz.timezone(settings.TIMEZONE)


def get_current_time() -> datetime:
    """Get current time in configured timezone as naive datetime."""
    utc_now = datetime.now(UTC)
    local_time = utc_now.astimezone(tz)
    return local_time.replace(tzinfo=None)


def _get_deployment_key(schedule: ScheduleDB) -> tuple[str, str]:
    """Get unique key for a deployment (namespace, deployment_name)."""
    return (schedule.namespace, schedule.deployment_name)


class SchedulerService:
    """Service to manage scheduled scaling operations"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)
        self.is_running = False

    def start(self):
        """Start the scheduler"""
        if not self.is_running:
            # Add job to check schedules every minute at second 0
            self.scheduler.add_job(self.check_schedules, "cron", second="0", id="check_schedules")
            self.scheduler.start()
            self.is_running = True
            logger.info(f"Scheduler started with timezone: {settings.TIMEZONE}")

    def stop(self):
        """Stop the scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.debug("Scheduler stopped")

    async def check_schedules(
        self,
        db: AsyncSession | None = None,
        k8s_client: K8sClient | None = None,
        current_time: str | None = None,
    ):
        """Check all enabled schedules and perform scaling if needed.

        Args:
            db: Optional database session for testing. If not provided, creates own session.
            k8s_client: Optional K8s client for testing. If not provided, creates own client.
            current_time: Optional current time string (HH:MM) for testing. If not provided, uses actual time.
        """
        logger.debug("Checking schedules...")

        # Use provided or create K8s client
        if k8s_client is None:
            k8s_client = K8sClient()

        # Use provided or create current time
        if current_time is None:
            tz = pytz.timezone(settings.TIMEZONE)
            current_time = datetime.now(tz).strftime("%H:%M")

        # Handle database session
        own_session = db is None
        if own_session:
            db = AsyncSessionLocal()

        try:
            async with db:
                # Get all enabled schedules
                result = await db.execute(select(ScheduleDB).where(ScheduleDB.enabled))
                schedules = result.scalars().all()

                logger.debug(f"Current time ({settings.TIMEZONE}): {current_time}, Found {len(schedules)} enabled schedules")

                # Group schedules by deployment
                by_deployment: dict[tuple[str, str], list[ScheduleDB]] = defaultdict(list)
                for schedule in schedules:
                    by_deployment[_get_deployment_key(schedule)].append(schedule)

                # Process each deployment group
                for deployment_key, dep_schedules in by_deployment.items():
                    await self.process_deployment(db, dep_schedules, current_time, k8s_client)

                await db.commit()

        except Exception as e:
            logger.error(f"Error checking schedules: {e}")
            if own_session:
                await db.rollback()

    async def process_deployment(
        self,
        db: AsyncSession,
        schedules: list[ScheduleDB],
        current_time: str,
        k8s_client: K8sClient,
    ):
        """Process all schedules for a single deployment.

        Scale down if ANY ENABLED schedule is in hibernation period.
        Scale up only if NO ENABLED schedule is in hibernation period.
        """
        namespace, deployment_name = schedules[0].namespace, schedules[0].deployment_name

        try:
            # Filter to only enabled schedules
            enabled_schedules = [s for s in schedules if s.enabled]

            # Check if ANY enabled schedule is in hibernation period
            any_in_hibernation = any(
                self.is_in_hibernation_period(s.scale_down_time, s.scale_up_time, current_time)
                for s in enabled_schedules
            )

            # Find the "primary" schedule row that holds deployment state
            # Use the one with original_replicas set, or the first one
            primary = next((s for s in schedules if s.original_replicas is not None), schedules[0])

            # If we're in hibernation period and deployment is NOT scaled down → scale down
            if any_in_hibernation and not primary.is_scaled_down:
                # Time to scale down
                logger.debug(f"Scaling down {namespace}/{deployment_name} (triggered by schedule)")

                # Get current replicas before scaling down
                current_replicas = await run_in_threadpool(
                    k8s_client.get_deployment_replicas,
                    namespace,
                    deployment_name,
                )

                # Save original replicas if not already saved
                if primary.original_replicas is None:
                    primary.original_replicas = current_replicas

                # Scale down to 0
                await run_in_threadpool(
                    k8s_client.scale_down,
                    namespace,
                    deployment_name,
                )

                # Update state on primary schedule (shared across all schedules for this deployment)
                primary.is_scaled_down = True
                primary.last_scaled_at = get_current_time()
                primary.updated_at = get_current_time()

                logger.info(f"Scaled down {namespace}/{deployment_name} from {current_replicas} to 0 replicas")

            # If we're NOT in hibernation period and deployment IS scaled down → scale up
            elif not any_in_hibernation and primary.is_scaled_down:
                # Time to scale up
                logger.debug(f"Scaling up {namespace}/{deployment_name}")

                # Scale up to original replicas
                replicas_to_restore = primary.original_replicas or 1
                await run_in_threadpool(
                    k8s_client.scale_up,
                    namespace,
                    deployment_name,
                    replicas_to_restore,
                )

                # Update state on primary schedule
                primary.is_scaled_down = False
                primary.last_scaled_at = get_current_time()
                primary.updated_at = get_current_time()

                logger.info(f"Scaled up {namespace}/{deployment_name} to {replicas_to_restore} replicas")

        except Exception as e:
            logger.error(f"Error processing deployment {namespace}/{deployment_name}: {e}")

    def is_in_hibernation_period(self, scale_down_time: str, scale_up_time: str, current_time: str) -> bool:
        """Check if current time is within the hibernation period (scale-down to scale-up)

        Args:
            scale_down_time: Time when deployment scales down (HH:MM format)
            scale_up_time: Time when deployment scales up (HH:MM format)
            current_time: Current time to check (HH:MM format)

        Returns:
            True if current time is in hibernation period, False otherwise

        Examples:
            - scale_down=19:00, scale_up=08:00, current=22:00 -> True (overnight period)
            - scale_down=19:00, scale_up=08:00, current=10:00 -> False
            - scale_down=13:00, scale_up=14:00, current=13:30 -> True (same day period)
        """

        # Parse time strings to comparable integers (HHMM format)
        def time_to_int(time_str: str) -> int:
            hours, minutes = map(int, time_str.split(":"))
            return hours * 100 + minutes

        down = time_to_int(scale_down_time)
        up = time_to_int(scale_up_time)
        current = time_to_int(current_time)

        # Check if period crosses midnight (e.g., 19:00 to 08:00)
        if down > up:
            # Hibernation period crosses midnight
            # We're in hibernation if: current >= down OR current < up
            return current >= down or current < up
        else:
            # Hibernation period is same day (e.g., 13:00 to 14:00)
            # We're in hibernation if: down <= current < up
            return down <= current < up


# Global scheduler instance
scheduler_service: SchedulerService | None = None


def get_scheduler() -> SchedulerService:
    """Get or create scheduler instance"""
    global scheduler_service
    if scheduler_service is None:
        scheduler_service = SchedulerService()
    return scheduler_service