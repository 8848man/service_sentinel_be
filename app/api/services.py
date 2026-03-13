from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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

router = APIRouter(prefix="/services", tags=["Services"])


@router.post("", response_model=ServiceResponse, status_code=201)
def create_service(
    request: ServiceCreate,
    db: Session = Depends(get_db),
):
    """Create a new service to monitor"""
    repo = ServiceRepository(db)
    return repo.create(request)


@router.get("", response_model=list[ServiceResponse])
def get_services(
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get all services with optional filtering"""
    repo = ServiceRepository(db)
    return repo.find_all(is_active=is_active, skip=skip, limit=limit)


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(
    service_id: int,
    db: Session = Depends(get_db),
):
    """Get service by ID"""
    repo = ServiceRepository(db)
    service = repo.find_by_id(service_id)

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    return service


@router.patch("/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: int,
    data: ServiceUpdate,
    db: Session = Depends(get_db),
):
    """Update service configuration"""
    repo = ServiceRepository(db)
    service = repo.update(service_id, data)

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    return service


@router.delete("/{service_id}", status_code=204)
def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
):
    """Delete a service"""
    repo = ServiceRepository(db)
    success = repo.delete(service_id)

    if not success:
        raise HTTPException(status_code=404, detail="Service not found")


@router.post("/{service_id}/activate", response_model=ServiceResponse)
def activate_service(
    service_id: int,
    db: Session = Depends(get_db),
):
    """Activate monitoring for a service"""
    repo = ServiceRepository(db)
    service = repo.update(service_id, ServiceUpdate(is_active=True))

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    return service


@router.post("/{service_id}/deactivate", response_model=ServiceResponse)
def deactivate_service(
    service_id: int,
    db: Session = Depends(get_db),
):
    """Pause monitoring for a service"""
    repo = ServiceRepository(db)
    service = repo.update(service_id, ServiceUpdate(is_active=False))

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    return service


@router.post("/{service_id}/check-now", response_model=HealthCheckResponse)
async def check_service_now(
    service_id: int,
    db: Session = Depends(get_db),
):
    """Trigger immediate health check for a service"""
    service_repo = ServiceRepository(db)
    service = service_repo.find_by_id(service_id)

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


@router.get("/{service_id}/health-checks", response_model=HealthCheckListResponse)
def get_service_health_checks(
    service_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get health check history for a service"""
    service_repo = ServiceRepository(db)
    service = service_repo.find_by_id(service_id)

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


@router.get("/{service_id}/health-checks/latest", response_model=HealthCheckResponse)
def get_latest_health_check(
    service_id: int,
    db: Session = Depends(get_db),
):
    """Get latest health check for a service"""
    service_repo = ServiceRepository(db)
    service = service_repo.find_by_id(service_id)

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    health_repo = HealthCheckRepository(db)
    latest = health_repo.find_latest_for_service(service_id)

    if not latest:
        raise HTTPException(status_code=404, detail="No health checks found for this service")

    return latest


@router.get("/{service_id}/stats", response_model=ServiceStats)
def get_service_stats(
    service_id: int,
    period: str = Query("24h", regex="^(1h|24h|7d|30d)$"),
    db: Session = Depends(get_db),
):
    """Get uptime statistics for a service"""
    service_repo = ServiceRepository(db)
    service = service_repo.find_by_id(service_id)

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


@router.get("/{service_id}/incidents", response_model=list[IncidentWithService])
def get_service_incidents(
    service_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get incidents for a service"""
    service_repo = ServiceRepository(db)
    service = service_repo.find_by_id(service_id)

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    incident_repo = IncidentRepository(db)
    incidents = incident_repo.find_all(service_id=service_id, skip=skip, limit=limit)

    return [
        IncidentWithService(**incident.__dict__, service_name=service.name)
        for incident in incidents
    ]