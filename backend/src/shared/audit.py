"""Audit logging utilities."""

import json
from typing import Any

from fastapi import Request
from loguru import logger


async def log_action(
    user_email: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
):
    """
    Log an action to application logs.

    Args:
        user_email: Email of the user performing the action
        action: Action being performed (e.g., 'create_schedule', 'scale_deployment')
        resource_type: Type of resource (e.g., 'schedule', 'deployment', 'user')
        resource_id: ID or identifier of the resource
        details: Additional details about the action
        ip_address: IP address of the client
    """
    log_data = {
        "user_email": user_email,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "ip_address": ip_address,
    }

    if details:
        log_data["details"] = json.dumps(details)

    logger.info(
        f"AUDIT: {action} | User: {user_email} | Resource: {resource_type}/{resource_id} | IP: {ip_address}", extra=log_data
    )


def get_client_ip(request: Request) -> str:
    """Get client IP address from request, handling proxies."""
    # Check X-Forwarded-For header (for proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP if multiple are present
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header (alternative proxy header)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client
    if request.client:
        return request.client.host

    return "unknown"
