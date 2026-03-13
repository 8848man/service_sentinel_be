from app.core.notification.policies.base import NotificationPolicy
from app.core.notification.decision import NotificationDecision
from app.models.service import ServiceState


class ServicePolicy(NotificationPolicy):
    def evaluate(self, ctx) -> NotificationDecision:
        service = ctx.service

        # 1️⃣ 서비스 비활성
        if not service.is_active:
            return NotificationDecision.block("SERVICE_INACTIVE")

        # 2️⃣ 운영 상태 비정상
        if service.service_state == ServiceState.INACTIVE:
            return NotificationDecision.block("SERVICE_STATE_INACTIVE")

        # 3️⃣ (확장) 서비스 알림 설정
        # nullable 컬럼 가정
        if hasattr(service, "notification_enabled"):
            if service.notification_enabled is False:
                return NotificationDecision.block("SERVICE_NOTIFICATION_DISABLED")

        return NotificationDecision.allow()