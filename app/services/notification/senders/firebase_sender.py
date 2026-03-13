import logging

from app.core.notification.context import NotificationContext
from app.services.notification.senders.base import NotificationSender

logger = logging.getLogger(__name__)


# class FirebasePushNotificationSender(NotificationSender):
#     def __init__(self, firebase_client):
#         """
#         firebase_client:
#             - Firebase Admin SDK wrapper
#             - send_push(token, title, body, data) 같은 인터페이스를 가진 객체
#         """
#         self._firebase = firebase_client
#
#     def send(self, ctx: NotificationContext) -> None:
#         user = ctx.user
#         incident = ctx.incident
#         service = ctx.service
#
#         if not user.fcm_token:
#             logger.info(
#                 "Skip push notification: user has no fcm_token",
#                 extra={"user_id": user.id},
#             )
#             return
#
#         title = f"[{service.name}] Incident 발생"
#         body = incident.summary
#
#         self._firebase.send_push(
#             token=user.fcm_token,
#             title=title,
#             body=body,
#             data={
#                 "incident_id": str(incident.id),
#                 "service_id": str(service.id),
#                 "project_id": str(ctx.project.id),
#             },
#         )
import logging

from app.core.firebase import send_push_message
from app.services.notification.senders.base import NotificationSender

logger = logging.getLogger(__name__)


class FirebasePushNotificationSender(NotificationSender):
    """
    Firebase FCM Push Notification Sender

    Responsibility:
    - Send push notifications only
    - No DB writes
    - No retry / deactivate logic
    """

    def send(self, ctx) -> None:
        if not ctx.devices:
            logger.info(
                "Skip push notification: no target devices",
                extra={"incident_id": ctx.incident.id},
            )
            return

        for device in ctx.devices:
            if not device.is_active:
                continue

            try:
                send_push_message(
                    token=device.token,
                    title="Incident Detected",
                    body=f"{ctx.service.name} has failed",
                    data={
                        "incident_id": str(ctx.incident.id),
                        "service_id": str(ctx.service.id),
                        "project_id": str(ctx.project.id),
                    },
                )

            except Exception as e:
                # ❗ 실패는 기록만 하고 전파하지 않음
                logger.warning(
                    f"Failed to send firebase push notification: {e}",
                    extra={
                        "device_token_id": device.id,
                        "incident_id": ctx.incident.id,
                        "error": str(e),
                    },
                )

        logger.info(
            "Firebase push notification send attempt finished",
            extra={
                "incident_id": ctx.incident.id,
                "device_count": len(ctx.devices),
            },
        )