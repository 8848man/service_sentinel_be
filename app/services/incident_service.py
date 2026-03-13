import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.notification.context import NotificationContext
from app.models.service import Service
from app.models.health_check import HealthCheck
from app.models.incident import Incident, IncidentStatus, IncidentSeverity
from app.repositories.device_token_repository import DeviceTokenRepository
from app.repositories.incident_repository import IncidentRepository
from app.repositories.health_check_repository import HealthCheckRepository
from app.services.notification.context_factory import NotificationContextFactory
from app.services.notification.usecase import NotifyIncidentUseCase

logger = logging.getLogger(__name__)


class IncidentService:
    def __init__(self, db: Session,):
        self.db = db
        self.incident_repo = IncidentRepository(db)
        self.health_repo = HealthCheckRepository(db)

    async def handle_failure(self, service: Service, failed_check: HealthCheck, notification_uc: NotifyIncidentUseCase):
        """Handle a failed health check - create or update incident"""

        # Check if there's already an open incident
        existing_incident = self.incident_repo.find_open_incident_for_service(service.id)

        if existing_incident:
            # Increment failure count
            self.incident_repo.increment_failure_count(existing_incident.id)

            # Update severity based on consecutive failures
            existing_incident.severity = self._calculate_severity(
                existing_incident.consecutive_failures,
                service.failure_threshold
            )
            self.db.commit()

            logger.info(
                f"Updated incident {existing_incident.id} for service {service.name}. "
                f"Consecutive failures: {existing_incident.consecutive_failures}"
            )

        else:
            # Check recent failure count to see if we should create incident
            lookback_minutes = (service.check_interval_seconds / 60) * service.failure_threshold
            recent_failures = self._count_recent_failures(
                service.id,
                lookback_minutes=lookback_minutes
            )

            if recent_failures >= service.failure_threshold:
                # Create new incident
                incident_data = {
                    "service_id": service.id,
                    "trigger_check_id": failed_check.id,
                    "title": self._generate_incident_title(service, failed_check),
                    "description": self._generate_incident_description(service, failed_check),
                    "status": IncidentStatus.OPEN,
                    "severity": self._calculate_severity(recent_failures, service.failure_threshold),
                    "consecutive_failures": recent_failures,
                    "total_affected_checks": recent_failures,
                    "ai_analysis_requested": False
                }

                incident = self.incident_repo.create(incident_data)

                # Update service state to ERROR
                from app.repositories.service_repository import ServiceRepository
                from app.models.service import ServiceState

                service_repo = ServiceRepository(self.db)
                service_repo.update_state(service.id, ServiceState.ERROR)

                logger.warning(
                    f"Created new incident {incident.id} for service {service.name}. "
                    f"Severity: {incident.severity.value}, Failures: {recent_failures}. "
                    f"Service state transitioned to ERROR"
                )

                factory = NotificationContextFactory(self.db)
                ctx = factory.create_for_incident(
                    project=service.project,
                    service=service,
                    incident=incident,
                )

                # TODO: Trigger notification
                notification_uc.execute(ctx)

                # TODO: Queue AI analysis if enabled

    async def resolve_if_healthy(self, service: Service):
        """Auto-resolve open incidents if service is healthy"""
        open_incident = self.incident_repo.find_open_incident_for_service(service.id)

        if open_incident:
            # Check if service has been healthy for last N checks
            recent_checks = self.health_repo.find_recent_for_service(
                service.id,
                limit=3
            )

            if recent_checks and all(check.is_alive for check in recent_checks):
                self.incident_repo.update_status(
                    open_incident.id,
                    IncidentStatus.RESOLVED,
                    resolved_at=datetime.utcnow()
                )

                # Update service state to HEALTHY (only if still active)
                from app.repositories.service_repository import ServiceRepository
                from app.models.service import ServiceState

                service_repo = ServiceRepository(self.db)
                if service.is_active:  # Only if still active
                    service_repo.update_state(service.id, ServiceState.HEALTHY)

                logger.info(
                    f"Auto-resolved incident {open_incident.id} for service {service.name}. "
                    f"Service state transitioned to HEALTHY"
                )

                # factory = NotificationContextFactory(self.db)
                # ctx = factory.create_for_incident(
                #     project=service.project,
                #     service=service,
                #     incident=incident,
                # )
                #
                # # TODO: Trigger notification
                # notification_uc.execute(ctx)

    def _count_recent_failures(self, service_id: int, lookback_minutes: float) -> int:
        """Count failures in recent time window"""
        since = datetime.utcnow() - timedelta(minutes=lookback_minutes)
        return self.health_repo.count_failures_since(service_id, since)

    def _calculate_severity(self, failure_count: int, threshold: int) -> IncidentSeverity:
        """Calculate incident severity based on failure count"""
        ratio = failure_count / max(threshold, 1)

        if ratio >= 5:
            return IncidentSeverity.CRITICAL
        elif ratio >= 3:
            return IncidentSeverity.HIGH
        elif ratio >= 1.5:
            return IncidentSeverity.MEDIUM
        else:
            return IncidentSeverity.LOW

    def _generate_incident_title(self, service: Service, check: HealthCheck) -> str:
        """Generate human-readable incident title"""
        if check.error_type == "timeout":
            return f"{service.name} - Request Timeout"
        elif check.error_type == "connection_error":
            return f"{service.name} - Connection Failed"
        elif check.status_code:
            return f"{service.name} - HTTP {check.status_code} Error"
        else:
            return f"{service.name} - Service Failure"

    def _generate_incident_description(self, service: Service, check: HealthCheck) -> str:
        """Generate incident description"""
        return f"""Service: {service.name}
Endpoint: {service.endpoint_url}
Error: {check.error_message or 'Unknown error'}
Status Code: {check.status_code or 'N/A'}
Latency: {check.latency_ms}ms
Time: {check.checked_at}"""
