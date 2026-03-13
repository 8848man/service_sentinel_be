from sqlalchemy.orm import Session

from app.core.notification.context import NotificationContext
from app.models import Project, Service, Incident
from app.repositories.device_token_repository import DeviceTokenRepository


class NotificationContextFactory:
    def __init__(self, db: Session):
        self.device_repo = DeviceTokenRepository(db)

    def create_for_incident(
        self,
        *,
        project: Project,
        service: Service,
        incident: Incident,
    ) -> NotificationContext:
        devices = self.device_repo.get_active_tokens_by_user(
            project.user_id
        )

        return NotificationContext(
            project=project,
            service=service,
            incident=incident,
            devices=devices,
        )