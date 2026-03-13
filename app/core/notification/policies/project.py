from app.core.notification.policies.base import NotificationPolicy
from app.core.notification.decision import NotificationDecision


class ProjectPolicy(NotificationPolicy):
    def evaluate(self, ctx) -> NotificationDecision:
        project = ctx.project

        # 1️⃣ 프로젝트 자체 비활성
        if not project.is_active:
            return NotificationDecision.block("PROJECT_INACTIVE")

        # 2️⃣ (확장) 프로젝트 알림 설정
        # nullable 컬럼 가정: None == ON
        if hasattr(project, "notification_enabled"):
            if project.notification_enabled is False:
                return NotificationDecision.block("PROJECT_NOTIFICATION_DISABLED")

        return NotificationDecision.allow()