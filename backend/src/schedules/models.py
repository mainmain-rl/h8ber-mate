"""Models for scheduling scaling operations on Kubernetes deployments."""

from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleBase(BaseModel):
    """Base schedule model"""

    namespace: str = Field(..., description="Kubernetes namespace")
    deployment_name: str = Field(..., description="Deployment name")
    scale_down_time: str = Field(
        ...,
        description="Scale down time (HH:MM format)",
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
    )
    scale_up_time: str = Field(
        ...,
        description="Scale up time (HH:MM format)",
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
    )


class ScheduleCreate(ScheduleBase):
    """Model for creating a new schedule"""

    pass


class ScheduleUpdate(BaseModel):
    """Model for updating a schedule"""

    scale_down_time: str | None = Field(
        None,
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
    )
    scale_up_time: str | None = Field(
        None,
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
    )
    enabled: bool | None = None


class Schedule(ScheduleBase):
    """Complete schedule model"""

    id: int
    enabled: bool = Field(
        default=True,
        description="Whether the schedule is enabled",
    )
    original_replicas: int | None = Field(
        None,
        description="Original number of replicas to restore",
    )
    is_scaled_down: bool = Field(default=False, description="Whether the deployment is currently scaled down")
    last_scaled_at: datetime | None = Field(None, description="Last time the deployment was scaled")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeploymentInfo(BaseModel):
    """Kubernetes deployment information"""

    name: str
    namespace: str
    replicas: int
    available_replicas: int
