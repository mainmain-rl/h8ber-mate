"""Database models for schedules module."""

from datetime import UTC, datetime

import pytz
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from src.shared.database.database import Base
from src.shared.settings import settings

# Get configured timezone
tz = pytz.timezone(settings.TIMEZONE)


def get_current_time():
    """Get current time in configured timezone as naive datetime for PostgreSQL."""
    utc_now = datetime.now(UTC)
    local_time = utc_now.astimezone(tz)
    return local_time.replace(tzinfo=None)


class ScheduleDB(Base):
    """SQLAlchemy model for schedules - owned by schedules module."""

    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    namespace = Column(String, nullable=False, index=True)
    deployment_name = Column(String, nullable=False, index=True)
    scale_down_time = Column(String, nullable=False)  # Format: "HH:MM"
    scale_up_time = Column(String, nullable=False)  # Format: "HH:MM"
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=get_current_time, nullable=False)
    updated_at = Column(DateTime, default=get_current_time, onupdate=get_current_time, nullable=False)

    # Deployment-level state (shared across schedules for same deployment)
    # These are stored on one schedule row per deployment (first one created)
    original_replicas = Column(Integer, nullable=True)
    is_scaled_down = Column(Boolean, default=False, nullable=False)
    last_scaled_at = Column(DateTime, nullable=True)