from dataclasses import dataclass

from app.models import Project, Service, Incident, User, UserDeviceToken



@dataclass(frozen=True)
class NotificationContext:
    """
    Messaging context passed to NotificationSender.

    - User is intentionally excluded
    - Device tokens are resolved before sending
    """
    project: Project
    service: Service
    incident: Incident

    # Active device tokens to notify
    devices: list[UserDeviceToken]