"""
Tests for the K8sClient class.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.k8s.services import K8sClient


@pytest.fixture
def k8s_client():
    """Create a K8sClient instance for testing."""
    with patch("src.k8s.services.config.load_incluster_config"):
        client = K8sClient()
        return client


def test_k8s_client_initialization(k8s_client):
    """Test that the K8sClient initializes correctly."""
    assert k8s_client.apps_v1 is not None
    assert k8s_client.core_v1 is not None


@pytest.mark.asyncio
async def test_scale_deployment(k8s_client):
    """Test scaling a deployment."""
    mock_deployment = MagicMock()
    mock_deployment.spec.replicas = 3
    mock_deployment.metadata.annotations = {}

    # Mock the Kubernetes API client methods
    k8s_client.apps_v1.read_namespaced_deployment = MagicMock(return_value=mock_deployment)
    k8s_client.apps_v1.replace_namespaced_deployment = MagicMock()

    # Test scaling down
    k8s_client.scale_down("test-namespace", "test-deployment")

    # Verify the deployment was scaled to 0
    k8s_client.apps_v1.replace_namespaced_deployment.assert_called_once()
    args = k8s_client.apps_v1.replace_namespaced_deployment.call_args

    # Check that replicas were set to 0
    assert args[1]["body"].spec.replicas == 0

    # Reset mock for next test
    k8s_client.apps_v1.replace_namespaced_deployment.reset_mock()

    # Test scaling up
    k8s_client.scale_up("test-namespace", "test-deployment", 5)

    # Verify the deployment was scaled to 5
    k8s_client.apps_v1.replace_namespaced_deployment.assert_called_once()
    args = k8s_client.apps_v1.replace_namespaced_deployment.call_args

    # Check that replicas were set to 5
    assert args[1]["body"].spec.replicas == 5


def test_get_deployment_replicas(k8s_client):
    """Test getting deployment replicas."""
    mock_deployment = MagicMock()
    mock_deployment.spec.replicas = 3

    # Mock the Kubernetes API client methods
    k8s_client.apps_v1.read_namespaced_deployment = MagicMock(return_value=mock_deployment)

    # Test getting replicas
    replicas = k8s_client.get_deployment_replicas("test-namespace", "test-deployment")

    # Verify the correct method was called
    k8s_client.apps_v1.read_namespaced_deployment.assert_called_once_with("test-deployment", "test-namespace")

    # Check that the correct number of replicas was returned
    assert replicas == 3


@pytest.mark.asyncio
async def test_list_deployments(k8s_client):
    """Test listing deployments in a namespace."""
    # Create mock deployment
    mock_deployment = MagicMock()
    mock_deployment.metadata.name = "test-deployment"
    mock_deployment.metadata.namespace = "test-namespace"
    mock_deployment.spec.replicas = 2
    mock_deployment.status.available_replicas = 2

    # Create mock list response
    mock_list = MagicMock()
    mock_list.items = [mock_deployment]

    # Mock the Kubernetes API client methods
    k8s_client.apps_v1.list_namespaced_deployment = MagicMock(return_value=mock_list)

    # Test listing deployments
    deployments = k8s_client.list_deployments("test-namespace")

    # Verify the correct method was called
    k8s_client.apps_v1.list_namespaced_deployment.assert_called_once_with("test-namespace")

    # Check that the deployment was returned
    assert len(deployments) == 1
    assert deployments[0].name == "test-deployment"
