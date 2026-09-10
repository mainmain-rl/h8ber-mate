"""
Tests for the SchedulerService class.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schedules.services import SchedulerService
from src.shared.database.models import ScheduleDB
from src.shared.settings import settings


@pytest.fixture
def mock_db_session():
    """Mock database session fixture."""
    mock_session = AsyncMock()
    return mock_session


@pytest.fixture
def scheduler_service():
    """Create a SchedulerService instance for testing."""
    service = SchedulerService()
    return service


def test_scheduler_initialization():
    """Test that the scheduler initializes correctly."""
    service = SchedulerService()
    assert not service.is_running
    assert service.scheduler is not None


def test_schedule_down_time_calculation():
    """Test the should_scale_down method."""
    service = SchedulerService()

    # Test exact match
    assert service.should_scale_down("15:30", "15:30") is True

    # Test no match
    assert service.should_scale_down("15:30", "16:00") is False
    assert service.should_scale_down("15:30", "15:29") is False
    assert service.should_scale_down("15:30", "15:31") is False


def test_schedule_up_time_calculation():
    """Test the should_scale_up method."""
    service = SchedulerService()

    # Test exact match
    assert service.should_scale_up("08:00", "08:00") is True

    # Test no match
    assert service.should_scale_up("08:00", "07:59") is False
    assert service.should_scale_up("08:00", "08:01") is False


@pytest.mark.asyncio
async def test_process_schedule_scale_down(mock_db_session, scheduler_service):
    """Test processing a schedule that should scale down."""
    # Mock dependencies
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_down = AsyncMock()
    mock_schedule = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
        is_scaled_down=False,
    )

    # Mock current time to be scale-down time
    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=22, minute=0)
        mock_dt.now.return_value = mock_now

        # Mock get_deployment_replicas to return 3
        mock_k8s_client.get_deployment_replicas.return_value = 3

        # Test scale down
        await scheduler_service.process_schedule(mock_db_session, mock_schedule, "22:00", mock_k8s_client)

        # Verify scale_down was called
        mock_k8s_client.scale_down.assert_called_once_with("test-ns", "test-deployment")
        assert mock_schedule.is_scaled_down is True
        assert mock_schedule.original_replicas == 3


@pytest.mark.asyncio
async def test_process_schedule_scale_up(mock_db_session, scheduler_service):
    """Test processing a schedule that should scale up."""
    # Mock dependencies
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_up = AsyncMock()
    mock_schedule = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
        is_scaled_down=True,  # Already scaled down
        original_replicas=3,
    )

    # Mock current time to be scale-up time
    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=8, minute=0)
        mock_dt.now.return_value = mock_now

        # Test scale up
        await scheduler_service.process_schedule(mock_db_session, mock_schedule, "08:00", mock_k8s_client)

        # Verify scale_up was called with original replicas
        mock_k8s_client.scale_up.assert_called_once_with("test-ns", "test-deployment", 3)
        assert mock_schedule.is_scaled_down is False


@pytest.mark.asyncio
async def test_process_schedule_no_action(mock_db_session, scheduler_service):
    """Test processing a schedule when no action should be taken."""
    # Mock dependencies
    mock_k8s_client = MagicMock()
    mock_schedule = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
        is_scaled_down=False,
    )

    # Mock current time to be outside scale times (not yet 22:00)
    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=18, minute=0)
        mock_dt.now.return_value = mock_now

        # Test no action
        await scheduler_service.process_schedule(mock_db_session, mock_schedule, "18:00", mock_k8s_client)

        # Verify no scaling operations were called
        assert not mock_k8s_client.scale_down.called
        assert not mock_k8s_client.scale_up.called


@pytest.mark.asyncio
async def test_process_schedule_disabled(mock_db_session, scheduler_service):
    """Test processing a disabled schedule."""
    # Mock dependencies
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_down = AsyncMock()
    mock_schedule = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=False,  # Disabled
        is_scaled_down=False,
    )

    # Mock current time to be scale-down time
    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=22, minute=0)
        mock_dt.now.return_value = mock_now

        # Test no action due to disabled schedule
        await scheduler_service.process_schedule(mock_db_session, mock_schedule, "22:00", mock_k8s_client)

        # Verify no scaling operations were called
        assert not mock_k8s_client.scale_down.called
        assert not mock_k8s_client.scale_up.called


@pytest.mark.asyncio
async def test_process_schedule_already_scaled_down(mock_db_session, scheduler_service):
    """Test processing a schedule that's already scaled down."""
    # Mock dependencies
    mock_k8s_client = MagicMock()
    mock_schedule = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
        is_scaled_down=True,  # Already scaled down
    )

    # Mock current time to be scale-down time (again)
    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=22, minute=0)
        mock_dt.now.return_value = mock_now

        # Test no action since already scaled down
        await scheduler_service.process_schedule(mock_db_session, mock_schedule, "22:00", mock_k8s_client)

        # Verify no scaling operations were called
        assert not mock_k8s_client.scale_down.called
        assert not mock_k8s_client.scale_up.called


@pytest.mark.asyncio
async def test_process_schedule_in_hibernation_period(mock_db_session, scheduler_service):
    """Test that schedule processing works correctly while in hibernation period."""
    # Mock dependencies
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_up = AsyncMock()
    mock_schedule = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="20:00",  # Evening
        scale_up_time="08:00",  # Morning (next day)
        enabled=True,
        is_scaled_down=False,
    )

    # Test various times during hibernation period (20:00-08:00)
    test_times = ["21:30", "22:45", "23:59", "00:15", "07:59"]

    for current_time in test_times:
        mock_k8s_client.reset_mock()

        # Mock current time
        with patch("src.schedules.services.datetime") as mock_dt:
            hour, minute = map(int, current_time.split(":"))
            mock_now = datetime.now().replace(hour=hour, minute=minute)
            mock_dt.now.return_value = mock_now
            mock_k8s_client.get_deployment_replicas.return_value = 2

            # Process schedule
            await scheduler_service.process_schedule(mock_db_session, mock_schedule, current_time, mock_k8s_client)

            # First time in hibernation period should scale down
            if current_time == "21:30":
                mock_k8s_client.scale_down.assert_called_once_with("test-ns", "test-deployment")
                mock_k8s_client.scale_up.assert_not_called()
            else:
                # Subsequent times during hibernation should not scale (already scaled down)
                mock_k8s_client.scale_down.assert_not_called()
                mock_k8s_client.scale_up.assert_not_called()


@pytest.mark.asyncio
async def test_check_schedules(mock_db_session, scheduler_service):
    """Test the check_schedules method with multiple schedules."""
    # Mock dependencies
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_up = AsyncMock()
    mock_k8s_client.scale_down = AsyncMock()
    mock_k8s_client.scale_up = AsyncMock()
    mock_k8s_client.scale_down = AsyncMock()

    # Create multiple schedules with different states and times
    active_schedule_1 = ScheduleDB(
        id=1,
        namespace="ns1",
        deployment_name="deploy1",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
        is_scaled_down=False,
    )

    active_schedule_2 = ScheduleDB(
        id=2,
        namespace="ns2",
        deployment_name="deploy2",
        scale_down_time="15:00",  # Lunch break
        scale_up_time="16:00",
        enabled=True,
        is_scaled_down=False,
    )

    disabled_schedule = ScheduleDB(
        id=3,
        namespace="ns3",
        deployment_name="deploy3",
        scale_down_time="20:00",
        scale_up_time="08:00",
        enabled=False,
        is_scaled_down=True,
    )

    # Add schedules to db mock
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [active_schedule_1, active_schedule_2, disabled_schedule]
    mock_db_session.execute.return_value = result_mock

    # Mock current time to be 22:00 (evening for first schedule, pre-lunch for second)
    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=22, minute=0)
        mock_dt.now.return_value = mock_now

        # Mock replicas for each deployment
        mock_k8s_client.get_deployment_replicas.side_effect = [3, 2]

        # Process all schedules
        await scheduler_service.check_schedules()

        # Verify scale operations were called correctly
        # First schedule (ns1/deploy1) should scale down at 22:00
        mock_k8s_client.scale_down.assert_any_call("ns1", "deploy1")
        # Second schedule (ns2/deploy2) should not scale at 22:00
        mock_k8s_client.scale_up.assert_not_called()
        # Third schedule (ns3/deploy3) should not scale (disabled)
        assert mock_k8s_client.scale_down.call_count == 1  # Only first schedule should be scaled down


@pytest.mark.asyncio
async def test_process_schedule_scale_up(mock_db_session, scheduler_service):
    """Test processing a schedule that should scale up."""
    service = SchedulerService()

    # Test same-day hibernation
    assert service.is_in_hibernation_period("13:00", "14:00", "13:30") is True
    assert service.is_in_hibernation_period("13:00", "14:00", "12:59") is False
    assert service.is_in_hibernation_period("13:00", "14:00", "14:01") is False

    # Test overnight hibernation
    assert service.is_in_hibernation_period("20:00", "08:00", "21:30") is True
    assert service.is_in_hibernation_period("20:00", "08:00", "7:59") is True
    assert service.is_in_hibernation_period("20:00", "08:00", "9:30") is False
    assert service.is_in_hibernation_period("20:00", "08:00", "19:59") is False
    assert service.is_in_hibernation_period("20:00", "08:00", "07:59") is True  # Edge case
    assert service.is_in_hibernation_period("20:00", "08:00", "07:59") is True  # Testing midnight crossing
