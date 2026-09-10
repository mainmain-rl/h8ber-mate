from datetime import UTC, datetime

import pytz
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from src.k8s.services import K8sClient, get_k8s_client
from src.shared.audit import get_client_ip, log_action
from src.shared.auth.auth_simple import check_namespace_access, get_current_user
from src.shared.database import ScheduleDB, get_db
from src.shared.settings import settings

from .models import Schedule, ScheduleCreate, ScheduleUpdate

scheduler_router = APIRouter(prefix="/schedules", tags=["schedules"])

# Get configured timezone
tz_config = pytz.timezone(settings.TIMEZONE)


def get_current_time() -> datetime:
    """Get current time in configured timezone as naive datetime."""
    utc_now = datetime.now(UTC)
    local_time = utc_now.astimezone(tz_config)
    return local_time.replace(tzinfo=None)


def is_in_hibernation_period(scale_down_time: str, scale_up_time: str, current_time: str) -> bool:
    """
    Check if current time is within the hibernation period (between scale_down and scale_up).
    Handles both same-day and overnight periods.

    Examples:
    - scale_down=22:00, scale_up=08:00, current=23:00 → True (overnight period)
    - scale_down=22:00, scale_up=08:00, current=07:00 → True (overnight period)
    - scale_down=22:00, scale_up=08:00, current=10:00 → False
    - scale_down=13:00, scale_up=14:00, current=13:30 → True (same-day period)
    """
    if scale_down_time < scale_up_time:
        # Same-day period (e.g., 13:00 to 14:00)
        return scale_down_time <= current_time < scale_up_time
    else:
        # Overnight period (e.g., 22:00 to 08:00)
        return current_time >= scale_down_time or current_time < scale_up_time


@scheduler_router.get("", response_model=list[Schedule])
async def get_schedules(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ScheduleDB:
    """Get all schedules (filtered by user's allowed namespaces for non-admin users)"""
    result = await db.execute(
        select(ScheduleDB).order_by(ScheduleDB.created_at.desc()),
    )
    all_schedules = result.scalars().all()

    # Filter schedules by user's allowed namespaces
    if current_user["role"] == "admin":
        return all_schedules
    else:
        # Non-admin users only see schedules for their allowed namespaces
        return [s for s in all_schedules if s.namespace in current_user["allowed_namespaces"]]


@scheduler_router.get("/{schedule_id}", response_model=Schedule)
async def get_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ScheduleDB:
    """Get a specific schedule"""
    result = await db.execute(
        select(ScheduleDB).where(ScheduleDB.id == schedule_id),
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Check if user has access to this schedule's namespace
    if not check_namespace_access(current_user, schedule.namespace):
        raise HTTPException(status_code=403, detail="You do not have access to this schedule")

    return schedule


@scheduler_router.post("", response_model=Schedule, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule_data: ScheduleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    k8s: K8sClient = Depends(get_k8s_client),
) -> ScheduleDB:
    """Create a new schedule"""
    # Check if user has access to this namespace
    if not check_namespace_access(current_user, schedule_data.namespace):
        raise HTTPException(
            status_code=403,
            detail=f"You do not have access to namespace '{schedule_data.namespace}'",
        )

    # Check if namespace is allowed (has required label)
    is_allowed = await run_in_threadpool(
        k8s.is_namespace_allowed,
        schedule_data.namespace,
        settings.labels.NAMESPACE_LABEL_KEY,
        settings.labels.NAMESPACE_LABEL_VALUE,
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Namespace '{schedule_data.namespace}' is not allowed. "
            f"Add label {settings.labels.NAMESPACE_LABEL_KEY}={settings.labels.NAMESPACE_LABEL_VALUE} to enable scheduling.",
        )

    # Verify deployment exists and get current replicas
    try:
        current_replicas = await run_in_threadpool(
            k8s.get_deployment_replicas,
            schedule_data.namespace,
            schedule_data.deployment_name,
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Deployment not found: {str(e)}")

    # Check if schedule already exists for this deployment
    result = await db.execute(
        select(ScheduleDB).where(
            ScheduleDB.namespace == schedule_data.namespace,
            ScheduleDB.deployment_name == schedule_data.deployment_name,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "A schedule already exists for this deployment",
                "suggestion": "Please edit the existing schedule instead of creating a new one",
                "existing_schedule": {
                    "id": existing.id,
                    "scale_down_time": existing.scale_down_time,
                    "scale_up_time": existing.scale_up_time,
                    "enabled": existing.enabled,
                },
            },
        )

    # Create schedule
    schedule = ScheduleDB(
        namespace=schedule_data.namespace,
        deployment_name=schedule_data.deployment_name,
        scale_down_time=schedule_data.scale_down_time,
        scale_up_time=schedule_data.scale_up_time,
        original_replicas=current_replicas,
        enabled=True,
        is_scaled_down=False,
        last_scaled_at=None,
    )

    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)

    # Check if we're already in the hibernation period
    # If yes, scale down immediately
    tz = pytz.timezone(settings.TIMEZONE)
    current_time = datetime.now(tz).strftime("%H:%M")

    if is_in_hibernation_period(schedule.scale_down_time, schedule.scale_up_time, current_time):
        # We're in hibernation period, scale down immediately
        try:
            await run_in_threadpool(k8s.scale_down, schedule.namespace, schedule.deployment_name)

            # Update schedule state
            schedule.is_scaled_down = True
            schedule.last_scaled_at = get_current_time()
            schedule.updated_at = get_current_time()

            await db.commit()
            await db.refresh(schedule)
        except Exception:
            # Log the error but don't fail the schedule creation
            # The scheduler will try again at the next minute
            pass

    # Log the action
    await log_action(
        user_email=current_user["email"],
        action="create_schedule",
        resource_type="schedule",
        resource_id=str(schedule.id),
        details={
            "namespace": schedule.namespace,
            "deployment_name": schedule.deployment_name,
            "scale_down_time": schedule.scale_down_time,
            "scale_up_time": schedule.scale_up_time,
        },
        ip_address=get_client_ip(request),
    )

    return schedule


@scheduler_router.patch("/{schedule_id}", response_model=Schedule)
async def update_schedule(
    schedule_id: int,
    schedule_data: ScheduleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    k8s: K8sClient = Depends(get_k8s_client),
) -> ScheduleDB:
    """Update a schedule"""
    result = await db.execute(select(ScheduleDB).where(ScheduleDB.id == schedule_id))
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Check if user has access to this schedule's namespace
    if not check_namespace_access(current_user, schedule.namespace):
        raise HTTPException(status_code=403, detail="You do not have access to this schedule")

    # Get current time in configured timezone
    tz = pytz.timezone(settings.TIMEZONE)
    current_time = datetime.now(tz).strftime("%H:%M")

    # Determine the new values after update
    new_scale_down_time = schedule_data.scale_down_time if schedule_data.scale_down_time is not None else schedule.scale_down_time
    new_scale_up_time = schedule_data.scale_up_time if schedule_data.scale_up_time is not None else schedule.scale_up_time
    new_enabled = schedule_data.enabled if schedule_data.enabled is not None else schedule.enabled

    # Case 1: If disabling a schedule that is currently scaled down, scale it back up
    if (
        schedule_data.enabled is not None
        and not schedule_data.enabled  # Disabling
        and schedule.is_scaled_down  # Currently scaled down
        and schedule.original_replicas is not None
    ):
        try:
            await run_in_threadpool(
                k8s.scale_deployment,
                schedule.namespace,
                schedule.deployment_name,
                schedule.original_replicas,
            )
            # Update state
            schedule.is_scaled_down = False
            schedule.last_scaled_at = get_current_time()
        except Exception as e:
            # Log error but continue with update
            import logging

            logging.error(f"Failed to scale up deployment when disabling schedule: {e}")

    # Case 2: If enabling a schedule (or updating times) and currently in hibernation period, scale down immediately
    elif (
        new_enabled  # Schedule will be enabled after update
        and not schedule.is_scaled_down  # Not currently scaled down
        and is_in_hibernation_period(new_scale_down_time, new_scale_up_time, current_time)
    ):
        try:
            # Get current replicas before scaling down
            current_replicas = await run_in_threadpool(k8s.get_deployment_replicas, schedule.namespace, schedule.deployment_name)

            # Save original replicas if not already saved
            if schedule.original_replicas is None or current_replicas > 0:
                schedule.original_replicas = current_replicas

            # Scale down to 0
            await run_in_threadpool(k8s.scale_down, schedule.namespace, schedule.deployment_name)

            # Update state
            schedule.is_scaled_down = True
            schedule.last_scaled_at = get_current_time()
        except Exception as e:
            # Log error but continue with update
            import logging

            logging.error(f"Failed to scale down deployment when enabling schedule during hibernation period: {e}")

    # Update fields
    if schedule_data.scale_down_time is not None:
        schedule.scale_down_time = schedule_data.scale_down_time
    if schedule_data.scale_up_time is not None:
        schedule.scale_up_time = schedule_data.scale_up_time
    if schedule_data.enabled is not None:
        schedule.enabled = schedule_data.enabled

    await db.commit()
    await db.refresh(schedule)

    # Log the action
    await log_action(
        user_email=current_user["email"],
        action="update_schedule",
        resource_type="schedule",
        resource_id=str(schedule.id),
        details={
            "namespace": schedule.namespace,
            "deployment_name": schedule.deployment_name,
            "scale_down_time": schedule.scale_down_time,
            "scale_up_time": schedule.scale_up_time,
            "enabled": schedule.enabled,
        },
        ip_address=get_client_ip(request),
    )

    return schedule


@scheduler_router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    k8s: K8sClient = Depends(get_k8s_client),
) -> None:
    """Delete a schedule"""
    result = await db.execute(select(ScheduleDB).where(ScheduleDB.id == schedule_id))
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Check if user has access to this schedule's namespace
    if not check_namespace_access(current_user, schedule.namespace):
        raise HTTPException(status_code=403, detail="You do not have access to this schedule")

    # If deployment is currently scaled down, scale it back up before deleting
    if schedule.is_scaled_down and schedule.original_replicas is not None:
        try:
            await run_in_threadpool(
                k8s.scale_deployment,
                schedule.namespace,
                schedule.deployment_name,
                schedule.original_replicas,
            )
        except Exception as e:
            # Log error but continue with deletion
            import logging

            logging.error(f"Failed to scale up deployment when deleting schedule: {e}")

    # Save details for audit log before deleting
    schedule_details = {
        "namespace": schedule.namespace,
        "deployment_name": schedule.deployment_name,
        "scale_down_time": schedule.scale_down_time,
        "scale_up_time": schedule.scale_up_time,
    }

    await db.delete(schedule)
    await db.commit()

    # Log the action
    await log_action(
        user_email=current_user["email"],
        action="delete_schedule",
        resource_type="schedule",
        resource_id=str(schedule_id),
        details=schedule_details,
        ip_address=get_client_ip(request),
    )

    return None
