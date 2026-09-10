"""Kubernetes API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from src.schedules.models import DeploymentInfo
from src.shared.auth.auth_simple import check_namespace_access, filter_namespaces_by_access, get_current_user
from src.shared.settings import settings

from .services import K8sClient, get_k8s_client

kubernetes_router = APIRouter(tags=["kubernetes"])


@kubernetes_router.get("/namespaces", response_model=list[str])
async def list_namespaces(
    k8s: K8sClient = Depends(get_k8s_client),
    current_user: dict = Depends(get_current_user),
) -> list[str]:
    """List allowed Kubernetes namespaces (with h8ber-mate label), filtered by user permissions"""
    try:
        # Get all allowed namespaces from K8s
        all_namespaces = await run_in_threadpool(
            k8s.list_allowed_namespaces,
            settings.labels.NAMESPACE_LABEL_KEY,
            settings.labels.NAMESPACE_LABEL_VALUE,
        )

        # Filter by user's allowed namespaces
        # Admins see all namespaces, users only see their assigned namespaces
        filtered_namespaces = filter_namespaces_by_access(current_user, all_namespaces)

        return filtered_namespaces
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list namespaces: {str(e)}",
        )


@kubernetes_router.get("/namespaces/{namespace}/deployments")
async def list_deployments(
    namespace: str,
    k8s: K8sClient = Depends(get_k8s_client),
    current_user: dict = Depends(get_current_user),
) -> list[DeploymentInfo]:
    """List all deployments in a specific namespace"""
    # Check if user has access to this namespace
    if not check_namespace_access(current_user, namespace):
        raise HTTPException(
            status_code=403,
            detail=f"You do not have access to namespace '{namespace}'",
        )

    try:
        deployments = await run_in_threadpool(k8s.list_deployments, namespace)
        return deployments
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list deployments: {str(e)}",
        )
