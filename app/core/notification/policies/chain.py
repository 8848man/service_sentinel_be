from typing import Iterable
from app.core.notification.context import NotificationContext
from app.core.notification.decision import NotificationDecision
from app.core.notification.policies.base import NotificationPolicy


class PolicyChain:
    def __init__(self, policies: Iterable[NotificationPolicy]):
        self._policies = list(policies)

    def evaluate(self, ctx: NotificationContext) -> NotificationDecision:
        """
        Notification Policy Chain 실행기 (Fail-fast)

        - 정책을 순서대로 평가한다
        - 하나라도 BLOCK이면 즉시 종료한다
        - 모두 통과하면 ALLOW 반환
        """
        for policy in self._policies:
            decision = policy.evaluate(ctx)

            if not decision:
                return decision

        return NotificationDecision.allow()