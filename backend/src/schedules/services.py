"""Scheduler services."""

import logging
from datetime import UTC, datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from src.k8s.services import K8sClient
from src.shared.database import AsyncSessionLocal, ScheduleDB
from src.shared.settings import settings

logger = logging.getLogger(__name__)

# Get configured timezone
tz = pytz.timezone(settings.TIMEZONE)


def get_current_time() -> datetime:
    """Get current time in configured timezone as naive datetime."""
    utc_now = datetime.now(UTC)
    local_time = utc_now.astimezone(tz)
    return local_time.replace(tzinfo=None)


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

    async def check_schedules(self):
        """Check all enabled schedules and perform scaling if needed"""
        logger.debug("Checking schedules...")

        # Create K8s client for in-cluster access
        k8s_client = K8sClient()

        async with AsyncSessionLocal() as db:
            try:
                # Get all enabled schedules
                result = await db.execute(select(ScheduleDB).where(ScheduleDB.enabled))
                schedules = result.scalars().all()

                # Get current time in configured timezone
                tz = pytz.timezone(settings.TIMEZONE)
                current_time = datetime.now(tz).strftime("%H:%M")
                logger.debug(f"Current time ({settings.TIMEZONE}): {current_time}, Found {len(schedules)} enabled schedules")

                for schedule in schedules:
                    await self.process_schedule(db, schedule, current_time, k8s_client)

                await db.commit()

            except Exception as e:
                logger.error(f"Error checking schedules: {e}")
                await db.rollback()

    async def process_schedule(self, db: AsyncSession, schedule: ScheduleDB, current_time: str, k8s_client: K8sClient):
        """Process a single schedule"""
        try:
            # Check if we're in the hibernation period (between scale_down and scale_up times)
            in_hibernation = self.is_in_hibernation_period(
                schedule.scale_down_time,
                schedule.scale_up_time,
                current_time,
            )

            # If we're in hibernation period and deployment is NOT scaled down → scale down
            if in_hibernation and not schedule.is_scaled_down:
                # Time to scale down
                logger.debug(f"Scaling down {schedule.namespace}/{schedule.deployment_name}")

                # Get current replicas before scaling down
                current_replicas = await run_in_threadpool(
                    k8s_client.get_deployment_replicas,
                    schedule.namespace,
                    schedule.deployment_name,
                )

                # Save original replicas if not already saved
                if schedule.original_replicas is None or current_replicas > 0:
                    schedule.original_replicas = current_replicas

                # Scale down to 0
                await run_in_threadpool(
                    k8s_client.scale_down,
                    schedule.namespace,
                    schedule.deployment_name,
                )

                # Update schedule state
                schedule.is_scaled_down = True
                schedule.last_scaled_at = get_current_time()
                schedule.updated_at = get_current_time()

                logger.info(f"Scaled down {schedule.namespace}/{schedule.deployment_name} from {current_replicas} to 0 replicas")

            # If we're NOT in hibernation period and deployment IS scaled down → scale up
            elif not in_hibernation and schedule.is_scaled_down:
                # Time to scale up
                logger.debug(f"Scaling up {schedule.namespace}/{schedule.deployment_name}")

                # Scale up to original replicas
                replicas_to_restore = schedule.original_replicas or 1
                await run_in_threadpool(
                    k8s_client.scale_up,
                    schedule.namespace,
                    schedule.deployment_name,
                    replicas_to_restore,
                )

                # Update schedule state
                schedule.is_scaled_down = False
                schedule.last_scaled_at = get_current_time()
                schedule.updated_at = get_current_time()

                logger.info(f"Scaled up {schedule.namespace}/{schedule.deployment_name} to {replicas_to_restore} replicas")

        except Exception as e:
            logger.error(f"Error processing schedule for {schedule.namespace}/{schedule.deployment_name}: {e}")

    def should_scale_down(self, scale_down_time: str, current_time: str) -> bool:
        """Check if it's time to scale down"""
        return current_time == scale_down_time

    def should_scale_up(self, scale_up_time: str, current_time: str) -> bool:
        """Check if it's time to scale up"""
        return current_time == scale_up_time

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
