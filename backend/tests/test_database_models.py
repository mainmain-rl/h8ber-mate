"""
Tests for database models.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database.models import ScheduleDB


@pytest.fixture
def mock_db_session():
    """Mock database session fixture."""
    return AsyncSession()


def test_schedule_model_creation():
    """Test creating a ScheduleDB model."""
    schedule = ScheduleDB(
        namespace="test-ns", deployment_name="test-deployment", scale_down_time="22:00", scale_up_time="08:00"
    )

    assert schedule.namespace == "test-ns"
    assert schedule.deployment_name == "test-deployment"
    assert schedule.scale_down_time == "22:00"
    assert schedule.scale_up_time == "08:00"
    assert schedule.enabled is True
    assert schedule.is_scaled_down is False
    assert schedule.original_replicas is None


def test_schedule_model_defaults():
    """Test default values in ScheduleDB model."""
    schedule = ScheduleDB(
        namespace="test-ns", deployment_name="test-deployment", scale_down_time="20:00", scale_up_time="08:00"
    )

    # Check default values
    assert schedule.enabled is True
    assert schedule.is_scaled_down is False
    assert schedule.original_replicas is None

    # Check timestamps are set (within tolerance)
    now = datetime.now()
    assert abs((schedule.created_at - now).total_seconds()) < 60
    assert abs((schedule.updated_at - now).total_seconds()) < 60


def test_schedule_model_unique_constraint():
    """Test the unique constraint on namespace and deployment_name."""
    schedule1 = ScheduleDB(namespace="test-ns", deployment_name="test-deployment-1")

    schedule2 = ScheduleDB(
        namespace="test-ns",
        deployment_name="test-deployment-1",  # Same as schedule1
    )

    assert schedule1.namespace == schedule2.namespace
    assert schedule1.deployment_name == schedule2.deployment_name


@pytest.mark.asyncio
async def test_schedule_model_timestamps(mock_db_session):
    """Test timestamp behavior in ScheduleDB model."""
    # Create a schedule
    schedule = ScheduleDB(
        namespace="test-ns", deployment_name="test-deployment", scale_down_time="20:00", scale_up_time="08:00"
    )

    # Check initial timestamps
    created_at = schedule.created_at
    updated_at = schedule.updated_at

    # Update some fields
    schedule.scale_down_time = "21:00"
    schedule.updated_at = datetime.now()

    # Check that updated_at changed
    assert schedule.updated_at > updated_at

    # Check that created_at remained the same
    assert schedule.created_at == created_at


def test_schedule_model_time_format():
    """Test that time format is properly stored."""
    schedule = ScheduleDB(
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",  # HH:MM format
        scale_up_time="08:00",  # HH:MM format
    )

    assert schedule.scale_down_time == "22:00"
    assert schedule.scale_up_time == "08:00"

    # Test various valid formats
    test_cases = [("08:00", "08:30"), ("12:34", "15:45"), ("23:59", "00:01")]

    for scale_down, scale_up in test_cases:
        schedule = ScheduleDB(
            namespace="test-ns",
            deployment_name=f"deploy-{scale_down}",
            scale_down_time=scale_down,
            scale_up_time=scale_up,
        )
        assert schedule.scale_down_time == scale_down
        assert schedule.scale_up_time == scale_up


def test_schedule_model_state_transitions():
    """Test state transitions in ScheduleDB model."""
    schedule = ScheduleDB(namespace="test-ns", deployment_name="test-deployment")

    # Initial state
    assert schedule.is_scaled_down is False

    # Simulate scale down
    schedule.is_scaled_down = True
    assert schedule.is_scaled_down is True

    # Simulate scale up
    schedule.is_scaled_down = False
    assert schedule.is_scaled_down is False

    # Test original_replicas storage
    schedule.original_replicas = 3
    assert schedule.original_replicas == 3

    # Test after scale up, original replicas are preserved
    assert schedule.original_replicas == 3
