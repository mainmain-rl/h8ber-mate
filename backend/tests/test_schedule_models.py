"""
Tests for Schedule models.
"""

from datetime import datetime, timedelta

import pytest
from pytz import timezone

from src.schedules.models import ScheduleBase, ScheduleCreate, ScheduleUpdate
from src.shared.settings import settings


def test_schedule_base_valid():
    """Test that a valid ScheduleBase model is created successfully."""
    schedule = ScheduleBase(
        namespace="test-ns", deployment_name="test-deployment", scale_down_time="18:00", scale_up_time="08:00"
    )
    assert schedule.namespace == "test-ns"
    assert schedule.deployment_name == "test-deployment"
    assert schedule.scale_down_time == "18:00"
    assert schedule.scale_up_time == "08:00"


def test_schedule_base_invalid_times():
    """Test that invalid time formats are rejected."""
    with pytest.raises(ValueError):
        ScheduleBase(
            namespace="test-ns",
            deployment_name="test-deployment",
            scale_down_time="18:00",
            scale_up_time="invalid-time",
        )

    with pytest.raises(ValueError):
        ScheduleBase(
            namespace="test-ns",
            deployment_name="test-deployment",
            scale_down_time="25:00",  # Invalid hour
            scale_up_time="08:00",
        )


def test_schedule_create():
    """Test that ScheduleCreate model works as expected."""
    schedule = ScheduleCreate(
        namespace="test-ns", deployment_name="test-deployment", scale_down_time="22:00", scale_up_time="08:00"
    )
    assert schedule.namespace == "test-ns"
    assert schedule.deployment_name == "test-deployment"
    assert schedule.scale_down_time == "22:00"
    assert schedule.scale_up_time == "08:00"


def test_schedule_update():
    """Test that ScheduleUpdate model works with partial updates."""
    update = ScheduleUpdate(scale_down_time="23:00", scale_up_time=None, enabled=True)
    assert update.scale_down_time == "23:00"
    assert update.enabled is True
    assert update.scale_up_time is None


def test_schedule_update_invalid_time():
    """Test that invalid time in update raises error."""
    with pytest.raises(ValueError):
        ScheduleUpdate(scale_down_time="invalid-time", scale_up_time=None)


# Test timezone handling
def test_timezone_handling():
    """Test that the default timezone is set correctly."""
    assert settings.TIMEZONE == "Europe/Paris"


# Test time validation patterns
@pytest.mark.parametrize(
    "time_str,is_valid",
    [
        ("08:00", True),
        ("23:59", True),
        ("00:00", True),
        ("12:34", True),
        ("25:00", False),  # Invalid hour
        ("12:60", False),  # Invalid minute
        ("abc", False),  # Invalid format
        ("12:3", False),  # Missing minute digit
    ],
)
def test_time_format_validation(time_str, is_valid):
    """Test various time formats for validation."""
    if is_valid:
        # Should not raise error
        ScheduleBase(namespace="test", deployment_name="test", scale_down_time=time_str, scale_up_time=time_str)
    else:
        # Should raise error
        with pytest.raises(ValueError):
            ScheduleBase(namespace="test", deployment_name="test", scale_down_time=time_str, scale_up_time=time_str)
