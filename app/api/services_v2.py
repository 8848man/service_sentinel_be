from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.service_repository import ServiceRepository
from app.repositories.health_check_repository import HealthCheckRepository
from app.repositories.incident_repository import IncidentRepository
from app.schemas.service_schema import (
    ServiceCreate,
    ServiceResponse,
    ServiceUpdate,
    ServiceStats
)
from app.schemas.health_check_schema import (
    HealthCheckResponse,
    HealthCheckListResponse
)
from app.schemas.incident_schema import IncidentWithService
from app.services.monitoring.monitoring_worker import MonitoringWorker

router = APIRouter(prefix="/projects/{project_id}", tags=["Services (Project-Scoped)"])


@router.post("/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
def create_service(
    request: ServiceCreate,
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Create a new service to monitor within the project.
    """
    repo = ServiceRepository(db)
    return repo.create(project_id=project_id, data=request)


@router.get("/services", response_model=list[ServiceResponse])
def get_services(
    project_id: int,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get all services for the project.
    """
    repo = ServiceRepository(db)
    return repo.find_all(project_id=project_id, is_active=is_active, skip=skip, limit=limit)


@router.get("/services/{service_id}", response_model=ServiceResponse)
def get_service(
    service_id: int,
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Get service by ID within the project.
    """
    repo = ServiceRepository(db)
    service = repo.find_by_id(service_id, project_id=project_id)

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    return service


@router.patch("/services/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: int,
    data: ServiceUpdate,
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Update service configuration.
    """
    repo = ServiceRepository(db)

    # Verify service belongs to project
    service = repo.find_by_id(service_id, project_id=project_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    service = repo.update(service_id, data)
    return service


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: int,
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a service.
    """
    repo = ServiceRepository(db)

    # Verify service belongs to project
    service = repo.find_by_id(service_id, project_id=project_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    repo.delete(service_id)


@router.post("/services/{service_id}/activate", response_model=ServiceResponse)
def activate_service(
    service_id: int,
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Activate monitoring for a service.
    """
    repo = ServiceRepository(db)

    # Verify service belongs to project
    service = repo.find_by_id(service_id, project_id=project_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    service = repo.update(service_id, ServiceUpdate(is_active=True))
    return service


@router.post("/services/{service_id}/deactivate", response_model=ServiceResponse)
def deactivate_service(
    service_id: int,
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Pause monitoring for a service.
    """
    repo = ServiceRepository(db)

    # Verify service belongs to project
    service = repo.find_by_id(service_id, project_id=project_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    service = repo.update(service_id, ServiceUpdate(is_active=False))
    return service


@router.post("/services/{service_id}/check-now", response_model=HealthCheckResponse)
async def check_service_now(
    service_id: int,
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Trigger immediate health check for a service.
    """
    service_repo = ServiceRepository(db)
    service = service_repo.find_by_id(service_id, project_id=project_id)

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Use monitoring worker to perform check
    worker = MonitoringWorker()
    await worker.initialize()

    try:
        health_check = await worker.check_service(service, db)
        return health_check
    finally:
        await worker.shutdown()


@router.get("/services/{service_id}/health-checks", response_model=HealthCheckListResponse)
def get_service_health_checks(
    project_id: int,
    service_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Get health check history for a service.
    """
    service_repo = ServiceRepository(db)
    service = service_repo.find_by_id(service_id, project_id=project_id)

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    health_repo = HealthCheckRepository(db)
    checks = health_repo.find_all_for_service(service_id, skip=skip, limit=limit)
    total = health_repo.count_for_service(service_id)

    return HealthCheckListResponse(
        service_id=service_id,
        total=total,
        items=checks
    )


@router.get("/services/{service_id}/health-checks/latest", response_model=HealthCheckResponse)
def get_latest_health_check(
    service_id: int,
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Get latest health check for a service.
    """
    service_repo = ServiceRepository(db)
    service = service_repo.find_by_id(service_id, project_id=project_id)

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    health_repo = HealthCheckRepository(db)
    latest = health_repo.find_latest_for_service(service_id)

    if not latest:
        raise HTTPException(status_code=404, detail="No health checks found for this service")

    return latest


@router.get("/services/{service_id}/stats", response_model=ServiceStats)
def get_service_stats(
    project_id: int,
    service_id: int,
    period: str = Query("24h", pattern="^(1h|24h|7d|30d)$"),
    db: Session = Depends(get_db),
):
    """
    Get uptime statistics for a service.
    """
    service_repo = ServiceRepository(db)
    service = service_repo.find_by_id(service_id, project_id=project_id)

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Calculate since datetime based on period
    period_map = {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30)
    }

    since = datetime.utcnow() - period_map[period]

    health_repo = HealthCheckRepository(db)
    stats = health_repo.get_stats_for_service(service_id, since=since)

    return ServiceStats(
        service_id=service_id,
        period=period,
        **stats
    )


@router.get("/services/{service_id}/incidents", response_model=list[IncidentWithService])
def get_service_incidents(
    project_id: int,
    service_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Get incidents for a service.
    """
    service_repo = ServiceRepository(db)
    service = service_repo.find_by_id(service_id, project_id=project_id)

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    incident_repo = IncidentRepository(db)
    incidents = incident_repo.find_all(service_id=service_id, skip=skip, limit=limit)

    return [
        IncidentWithService(**incident.__dict__, service_name=service.name)
        for incident in incidents
    ]
