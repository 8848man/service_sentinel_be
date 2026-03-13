import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.notification.policies.project import ProjectPolicy
from app.core.notification.policies.service import ServicePolicy
from app.models.service import Service
from app.models.health_check import HealthCheck
from app.repositories.device_token_repository import DeviceTokenRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.health_check_repository import HealthCheckRepository
from app.services.incident_service import IncidentService
from app.services.notification.context_factory import NotificationContextFactory
from app.services.notification.senders.firebase_sender import FirebasePushNotificationSender
from app.services.notification.usecase import NotifyIncidentUseCase

logger = logging.getLogger(__name__)


class MonitoringWorker:
    def __init__(self):
        self.http_client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """Initialize async HTTP client"""
        self.http_client = httpx.AsyncClient(
            follow_redirects=True,
            verify=True,
            http2=True
        )
        logger.info("Monitoring worker initialized")

    async def shutdown(self):
        """Clean up resources"""
        if self.http_client:
            await self.http_client.aclose()
        logger.info("Monitoring worker shutdown")

    async def check_service(self, service: Service, db: Session) -> HealthCheck:
        """Perform a single health check on a service"""
        health_repo = HealthCheckRepository(db)

        start_time = datetime.utcnow()
        check_data = {
            "service_id": service.id,
            "is_alive": False,
            "status_code": None,
            "latency_ms": 0,
            "error_message": None,
            "error_type": None,
            "response_body": None,
            "needs_analysis": False
        }

        try:
            # Build request
            request_kwargs = {
                "timeout": service.timeout_seconds,
                "headers": service.headers or {}
            }

            if service.http_method.value in ["POST", "PUT", "PATCH"] and service.request_body:
                request_kwargs["json"] = service.request_body

            # Execute request
            response = await self.http_client.request(
                method=service.http_method.value,
                url=service.endpoint_url,
                **request_kwargs
            )

            # Calculate latency
            end_time = datetime.utcnow()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)

            # Evaluate result
            is_alive = response.status_code in (service.expected_status_codes or [200])

            check_data.update({
                "is_alive": is_alive,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "response_body": response.text[:1000] if not is_alive else None,
                "needs_analysis": not is_alive
            })

            if not is_alive:
                check_data["error_message"] = f"Unexpected status code: {response.status_code}"
                check_data["error_type"] = "unexpected_status"

        except httpx.TimeoutException as e:
            end_time = datetime.utcnow()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)

            check_data.update({
                "latency_ms": latency_ms,
                "error_message": f"Request timeout after {service.timeout_seconds}s",
                "error_type": "timeout",
                "needs_analysis": True
            })

        except httpx.ConnectError as e:
            end_time = datetime.utcnow()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)

            check_data.update({
                "latency_ms": latency_ms,
                "error_message": f"Connection failed: {str(e)}",
                "error_type": "connection_error",
                "needs_analysis": True
            })

        except httpx.HTTPStatusError as e:
            end_time = datetime.utcnow()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)

            check_data.update({
                "latency_ms": latency_ms,
                "status_code": e.response.status_code,
                "error_message": f"HTTP error: {e.response.status_code}",
                "error_type": "http_error",
                "needs_analysis": True
            })

        except Exception as e:
            logger.exception(f"Unexpected error checking service {service.id}")
            end_time = datetime.utcnow()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)

            check_data.update({
                "latency_ms": latency_ms,
                "error_message": f"Unexpected error: {str(e)}",
                "error_type": "unknown",
                "needs_analysis": True
            })

        # Save health check
        health_check = health_repo.create(check_data)

        # Update service last_checked_at
        service.last_checked_at = datetime.utcnow()
        db.commit()

        return health_check

    async def monitor_all_services(self):
        """Main monitoring loop - checks all active services"""
        db = SessionLocal()
        try:
            service_repo = ServiceRepository(db)
            incident_service = IncidentService(db)

            active_services = service_repo.find_active_for_monitoring()

            if not active_services:
                logger.debug("No active services to monitor")
                return

            logger.info(f"Monitoring {len(active_services)} active services")

            # Check all services concurrently
            tasks = [
                self.check_service(service, db)
                for service in active_services
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and detect incidents
            for service, result in zip(active_services, results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to check service {service.id}: {result}")
                    continue

                sender = FirebasePushNotificationSender()

                notify_uc = NotifyIncidentUseCase(
                    policies=[
                        ProjectPolicy(),
                        ServicePolicy(),
                    ],
                    sender=sender,
                )

                if not result.is_alive:
                    # Failure detected - check if incident should be created/updated
                    await incident_service.handle_failure(service, result, notification_uc= notify_uc)
                    logger.warning(
                        f"Service {service.name} health check failed: "
                        f"{result.error_type} - {result.error_message}"
                    )
                else:
                    # Service is healthy - resolve any open incidents
                    await incident_service.resolve_if_healthy(service)
                    logger.debug(
                        f"Service {service.name} health check passed: "
                        f"{result.status_code} in {result.latency_ms}ms"
                    )

        except Exception as e:
            logger.exception("Error in monitoring loop")
        finally:
            db.close()
