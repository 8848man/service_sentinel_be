from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ProjectCreate(BaseModel):
    """Schema for creating a new project"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)


class ProjectUpdate(BaseModel):
    """Schema for updating a project"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None

class ProjectHealthSummary(BaseModel):
    status: str  # "HEALTHY" | "DEGRADED" | "UNKNOWN"
    total_services: int
    error_services: int


class ProjectHealth(BaseModel):
    """Derived project health (never stored in DB)"""
    status: str  # "HEALTHY" | "DEGRADED" | "UNKNOWN"
    total_services: int
    healthy_services: int
    error_services: int
    inactive_services: int
    active_incidents: int

class ProjectResponse(BaseModel):
    """Schema for project response"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    health: Optional[ProjectHealth] = None

class ProjectWithStats(ProjectResponse):
    """Project response with additional statistics"""
    total_services: int = 0
    active_services: int = 0
    total_incidents: int = 0
    open_incidents: int = 0

class ProjectWithHealth(ProjectResponse):
    """Project response with derived health status"""
    health: ProjectHealth


class GuestBootstrapResponse(BaseModel):
    """Response for guest bootstrap endpoint"""
    project: ProjectResponse
    api_key: str = Field(..., description="Guest API key (shown only once)")
    message: str = Field(default="API key shown only once. Store it securely!")
