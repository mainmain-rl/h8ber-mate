"""
Tests for the SchedulerService class.
"""

from datetime import datetime
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


def test_is_in_hibernation_period_same_day(scheduler_service):
    """Test is_in_hibernation_period for same-day periods."""
    # Same-day hibernation (e.g., lunch 13:00-14:00)
    assert scheduler_service.is_in_hibernation_period("13:00", "14:00", "13:30") is True
    assert scheduler_service.is_in_hibernation_period("13:00", "14:00", "12:59") is False
    assert scheduler_service.is_in_hibernation_period("13:00", "14:00", "14:00") is False
    assert scheduler_service.is_in_hibernation_period("13:00", "14:00", "14:01") is False


def test_is_in_hibernation_period_overnight(scheduler_service):
    """Test is_in_hibernation_period for overnight periods."""
    # Overnight hibernation (e.g., night 20:00-08:00)
    assert scheduler_service.is_in_hibernation_period("20:00", "08:00", "21:30") is True
    assert scheduler_service.is_in_hibernation_period("20:00", "08:00", "23:59") is True
    assert scheduler_service.is_in_hibernation_period("20:00", "08:00", "00:15") is True
    assert scheduler_service.is_in_hibernation_period("20:00", "08:00", "07:59") is True
    assert scheduler_service.is_in_hibernation_period("20:00", "08:00", "08:00") is False
    assert scheduler_service.is_in_hibernation_period("20:00", "08:00", "09:30") is False
    assert scheduler_service.is_in_hibernation_period("20:00", "08:00", "19:59") is False


@pytest.mark.asyncio
async def test_process_deployment_scale_down(mock_db_session, scheduler_service):
    """Test processing a deployment that should scale down."""
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_down = AsyncMock()

    # Two schedules for same deployment (night + lunch)
    schedule1 = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
    )
    schedule2 = ScheduleDB(
        id=2,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="13:00",
        scale_up_time="14:00",
        enabled=True,
    )

    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=22, minute=0)
        mock_dt.now.return_value = mock_now
        mock_k8s_client.get_deployment_replicas.return_value = 3

        # Test scale down triggered by first schedule (night)
        await scheduler_service.process_deployment(mock_db_session, [schedule1, schedule2], "22:00", mock_k8s_client)

        mock_k8s_client.scale_down.assert_called_once_with("test-ns", "test-deployment")
        # Primary schedule (first with original_replicas or first) should be updated
        assert schedule1.is_scaled_down is True
        assert schedule1.original_replicas == 3


@pytest.mark.asyncio
async def test_process_deployment_scale_down_lunch(mock_db_session, scheduler_service):
    """Test processing a deployment that should scale down due to lunch schedule."""
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_down = AsyncMock()

    schedule1 = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
    )
    schedule2 = ScheduleDB(
        id=2,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="13:00",
        scale_up_time="14:00",
        enabled=True,
    )

    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=13, minute=30)
        mock_dt.now.return_value = mock_now
        mock_k8s_client.get_deployment_replicas.return_value = 5

        # Test scale down triggered by second schedule (lunch)
        await scheduler_service.process_deployment(mock_db_session, [schedule1, schedule2], "13:30", mock_k8s_client)

        mock_k8s_client.scale_down.assert_called_once_with("test-ns", "test-deployment")
        assert schedule1.is_scaled_down is True
        assert schedule1.original_replicas == 5


@pytest.mark.asyncio
async def test_process_deployment_scale_up(mock_db_session, scheduler_service):
    """Test processing a deployment that should scale up when no schedule is in hibernation."""
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_up = AsyncMock()

    schedule1 = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
        is_scaled_down=True,
        original_replicas=3,
    )
    schedule2 = ScheduleDB(
        id=2,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="13:00",
        scale_up_time="14:00",
        enabled=True,
        is_scaled_down=True,
        original_replicas=3,
    )

    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=10, minute=0)
        mock_dt.now.return_value = mock_now

        # Test scale up - no schedule in hibernation at 10:00
        await scheduler_service.process_deployment(mock_db_session, [schedule1, schedule2], "10:00", mock_k8s_client)

        mock_k8s_client.scale_up.assert_called_once_with("test-ns", "test-deployment", 3)
        assert schedule1.is_scaled_down is False


@pytest.mark.asyncio
async def test_process_deployment_no_action(mock_db_session, scheduler_service):
    """Test processing a deployment when no action should be taken."""
    mock_k8s_client = MagicMock()

    schedule1 = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
        is_scaled_down=False,
    )
    schedule2 = ScheduleDB(
        id=2,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="13:00",
        scale_up_time="14:00",
        enabled=True,
        is_scaled_down=False,
    )

    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=18, minute=0)
        mock_dt.now.return_value = mock_now

        # Test no action - not in any hibernation period
        await scheduler_service.process_deployment(mock_db_session, [schedule1, schedule2], "18:00", mock_k8s_client)

        assert not mock_k8s_client.scale_down.called
        assert not mock_k8s_client.scale_up.called


@pytest.mark.asyncio
async def test_process_deployment_disabled_schedule_ignored(mock_db_session, scheduler_service):
    """Test that disabled schedules don't trigger scaling."""
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_down = AsyncMock()

    schedule1 = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
    )
    schedule2 = ScheduleDB(
        id=2,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="13:00",
        scale_up_time="14:00",
        enabled=False,  # Disabled
    )

    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=13, minute=30)
        mock_dt.now.return_value = mock_now
        mock_k8s_client.get_deployment_replicas.return_value = 2

        # Lunch schedule is disabled, night schedule not in hibernation at 13:30
        await scheduler_service.process_deployment(mock_db_session, [schedule1, schedule2], "13:30", mock_k8s_client)

        # Should not scale down because only disabled schedule is in hibernation
        assert not mock_k8s_client.scale_down.called


@pytest.mark.asyncio
async def test_process_deployment_already_scaled_down(mock_db_session, scheduler_service):
    """Test processing a deployment that's already scaled down."""
    mock_k8s_client = MagicMock()

    schedule1 = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
        is_scaled_down=True,
        original_replicas=3,
    )
    schedule2 = ScheduleDB(
        id=2,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="13:00",
        scale_up_time="14:00",
        enabled=True,
        is_scaled_down=True,
        original_replicas=3,
    )

    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=22, minute=0)
        mock_dt.now.return_value = mock_now

        # Already scaled down, should not scale again
        await scheduler_service.process_deployment(mock_db_session, [schedule1, schedule2], "22:00", mock_k8s_client)

        assert not mock_k8s_client.scale_down.called
        assert not mock_k8s_client.scale_up.called


@pytest.mark.asyncio
async def test_check_schedules_multiple_deployments(mock_db_session, scheduler_service):
    """Test the check_schedules method with multiple deployments and schedules."""
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_up = AsyncMock()
    mock_k8s_client.scale_down = AsyncMock()

    # Deployment 1: two schedules (night + lunch)
    dep1_sched1 = ScheduleDB(
        id=1,
        namespace="ns1",
        deployment_name="deploy1",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
        is_scaled_down=False,
    )
    dep1_sched2 = ScheduleDB(
        id=2,
        namespace="ns1",
        deployment_name="deploy1",
        scale_down_time="13:00",
        scale_up_time="14:00",
        enabled=True,
        is_scaled_down=False,
    )

    # Deployment 2: one schedule
    dep2_sched1 = ScheduleDB(
        id=3,
        namespace="ns2",
        deployment_name="deploy2",
        scale_down_time="15:00",
        scale_up_time="16:00",
        enabled=True,
        is_scaled_down=False,
    )

    # Deployment 3: disabled schedule
    dep3_sched1 = ScheduleDB(
        id=4,
        namespace="ns3",
        deployment_name="deploy3",
        scale_down_time="20:00",
        scale_up_time="08:00",
        enabled=False,
        is_scaled_down=True,
    )

    # Add schedules to db mock
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [dep1_sched1, dep1_sched2, dep2_sched1, dep3_sched1]
    mock_db_session.execute.return_value = result_mock

    # Mock replicas for each deployment
    mock_k8s_client.get_deployment_replicas.side_effect = [3, 2]

    # Process all schedules with mocked time
    await scheduler_service.check_schedules(db=mock_db_session, k8s_client=mock_k8s_client, current_time="22:00")

    # Verify scale operations were called correctly
    # deploy1 should scale down (night schedule triggers)
    mock_k8s_client.scale_down.assert_any_call("ns1", "deploy1")
    # deploy2 should NOT scale (15:00-16:00, current is 22:00)
    # deploy3 should NOT scale (disabled)
    assert mock_k8s_client.scale_down.call_count == 1


@pytest.mark.asyncio
async def test_check_schedules_scale_up(mock_db_session, scheduler_service):
    """Test check_schedules scales up when no hibernation periods active."""
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_up = AsyncMock()
    mock_k8s_client.scale_down = AsyncMock()

    schedule1 = ScheduleDB(
        id=1,
        namespace="ns1",
        deployment_name="deploy1",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
        is_scaled_down=True,
        original_replicas=3,
    )

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [schedule1]
    mock_db_session.execute.return_value = result_mock

    # Process with mocked time (10:00 - outside hibernation period)
    await scheduler_service.check_schedules(db=mock_db_session, k8s_client=mock_k8s_client, current_time="10:00")

    mock_k8s_client.scale_up.assert_called_once_with("ns1", "deploy1", 3)
    assert schedule1.is_scaled_down is False


@pytest.mark.asyncio
async def test_process_deployment_shared_state(mock_db_session, scheduler_service):
    """Test that deployment state is shared across schedules for same deployment."""
    mock_k8s_client = MagicMock()
    mock_k8s_client.scale_down = AsyncMock()

    # First schedule created - gets original_replicas
    schedule1 = ScheduleDB(
        id=1,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="22:00",
        scale_up_time="08:00",
        enabled=True,
        original_replicas=3,  # Already has state
        is_scaled_down=False,
    )
    # Second schedule created later - no state yet
    schedule2 = ScheduleDB(
        id=2,
        namespace="test-ns",
        deployment_name="test-deployment",
        scale_down_time="13:00",
        scale_up_time="14:00",
        enabled=True,
        original_replicas=None,
        is_scaled_down=False,
    )

    with patch("src.schedules.services.datetime") as mock_dt:
        mock_now = datetime.now().replace(hour=22, minute=0)
        mock_dt.now.return_value = mock_now
        mock_k8s_client.get_deployment_replicas.return_value = 5

        # Process - schedule1 is primary (has original_replicas)
        await scheduler_service.process_deployment(mock_db_session, [schedule1, schedule2], "22:00", mock_k8s_client)

        mock_k8s_client.scale_down.assert_called_once_with("test-ns", "test-deployment")
        # Primary schedule (schedule1) should be updated
        assert schedule1.is_scaled_down is True
        assert schedule1.original_replicas == 3  # Keeps original value
        # Second schedule should not have state (state is on primary)
        assert schedule2.original_replicas is None