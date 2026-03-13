from gc import isenabled
from typing import Iterable

from app.core.notification.context import NotificationContext
from app.core.notification.decision import NotificationDecision
from app.core.notification.policies.chain import PolicyChain
from app.core.notification.policies.base import NotificationPolicy
from app.services.notification.senders.base import NotificationSender
from app.models import Project, Service, Incident, User, UserDeviceToken


class NotifyIncidentUseCase:
    """
    Incident 발생 시 알림을 보낼지 판단하고,
    허용된 경우 실제 알림을 발송하는 UseCase
    """

    def __init__(
        self,
        *,
        policies: Iterable[NotificationPolicy],
        sender: NotificationSender,
    ):
        self._policy_chain = PolicyChain(policies)
        self._sender = sender

    # def execute(
    #     self,
    #     *,
    #     project: Project,
    #     service: Service,
    #     incident: Incident,
    #     user: User | None = None,
    #     devices: list[Incident] | None = None,
    # ) -> NotificationDecision:
    #     """
    #     알림 실행 진입점
    #
    #     - NotificationContext 생성
    #     - PolicyChain 평가
    #     - 허용 시 sender 호출
    #     - Decision 반환 (로그/추적/테스트용)
    #     """
    #     isenabledProejct = project.notification_enabled
    #
    #
    #     ctx = NotificationContext(
    #         project=project,
    #         service=service,
    #         incident=incident,
    #         devices=devices,
    #     )
    #
    #     decision = self._policy_chain.evaluate(ctx)
    #
    #     if decision.allowed:
    #         self._sender.send(ctx)
    #
    #     return decision
    # def execute(
    #     self,
    #     *,
    #     project: Project,
    #     service: Service,
    #     incident: Incident,
    #     devices: list[UserDeviceToken] | None = None,
    # ) -> NotificationDecision:
    #     ctx = NotificationContext(
    #         project=project,
    #         service=service,
    #         incident=incident,
    #         devices=devices or [],
    #     )
    #
    #     decision = self._policy_chain.evaluate(ctx)
    #
    #     if decision.allowed:
    #         self._sender.send(ctx)
    #
    #     return decision

    def execute(self, ctx: NotificationContext) -> NotificationDecision:
        decision = self._policy_chain.evaluate(ctx)

        if decision.allowed:
            self._sender.send(ctx)

        return decision