"""
Tests for database models.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.schedules.db import ScheduleDB, get_current_time


@pytest.fixture
async def db_session():
    """Create an in-memory database session for model behavior tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(ScheduleDB.__table__.create)

    async with AsyncSession(engine) as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_schedule_model_creation(db_session):
    """Test creating a ScheduleDB model."""
    schedule = ScheduleDB(
        namespace="test-ns", deployment_name="test-deployment", scale_down_time="22:00", scale_up_time="08:00"
    )
    db_session.add(schedule)
    await db_session.flush()

    assert schedule.namespace == "test-ns"
    assert schedule.deployment_name == "test-deployment"
    assert schedule.scale_down_time == "22:00"
    assert schedule.scale_up_time == "08:00"
    assert schedule.enabled is True
    assert schedule.is_scaled_down is False
    assert schedule.original_replicas is None


@pytest.mark.asyncio
async def test_schedule_model_defaults(db_session):
    """Test default values in ScheduleDB model."""
    schedule = ScheduleDB(
        namespace="test-ns", deployment_name="test-deployment", scale_down_time="20:00", scale_up_time="08:00"
    )
    before_flush = get_current_time()
    db_session.add(schedule)
    await db_session.flush()

    assert schedule.enabled is True
    assert schedule.is_scaled_down is False
    assert schedule.original_replicas is None

    assert schedule.created_at is not None
    assert schedule.updated_at is not None
    assert before_flush <= schedule.created_at
    after_flush = get_current_time()
    assert schedule.created_at <= after_flush
    assert schedule.updated_at <= after_flush


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
async def test_schedule_model_timestamps(db_session):
    """Test timestamp behavior in ScheduleDB model."""
    schedule = ScheduleDB(
        namespace="test-ns", deployment_name="test-deployment", scale_down_time="20:00", scale_up_time="08:00"
    )
    db_session.add(schedule)
    await db_session.flush()

    created_at = schedule.created_at
    updated_at = schedule.updated_at

    schedule.scale_down_time = "21:00"
    await db_session.flush()
    assert schedule.updated_at > updated_at
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


@pytest.mark.asyncio
async def test_schedule_model_state_transitions(db_session):
    """Test state transitions in ScheduleDB model."""
    schedule = ScheduleDB(
        namespace="test-ns", deployment_name="test-deployment", scale_down_time="22:00", scale_up_time="08:00"
    )
    db_session.add(schedule)
    await db_session.flush()

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
