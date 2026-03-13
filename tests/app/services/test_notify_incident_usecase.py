from app.services.notification.usecase import NotifyIncidentUseCase
from app.core.notification.decision import NotificationDecision
from app.core.notification.enum import NotificationDecisionResult
from app.core.notification.policies.base import NotificationPolicy
from app.models import Project, Service, Incident


class AlwaysAllowPolicy(NotificationPolicy):
    def evaluate(self, ctx):
        return NotificationDecision.allow()


class AlwaysBlockPolicy(NotificationPolicy):
    def evaluate(self, ctx):
        return NotificationDecision.block(
            NotificationDecisionResult.PROJECT_DISABLED
        )


def test_sender_not_called_when_policy_blocks(mocker):
    sender = mocker.Mock()

    usecase = NotifyIncidentUseCase(
        policies=[AlwaysBlockPolicy()],
        sender=sender,
    )

    decision = usecase.execute(
        project=Project(is_active=False),
        service=Service(is_active=True),
        incident=Incident(),
        user=None,
    )

    sender.send.assert_not_called()
    assert not decision.allowed
    assert decision.reason == NotificationDecisionResult.PROJECT_DISABLED


def test_sender_called_when_policy_allows(mocker):
    sender = mocker.Mock()

    usecase = NotifyIncidentUseCase(
        policies=[AlwaysAllowPolicy()],
        sender=sender,
    )

    decision = usecase.execute(
        project=Project(is_active=True),
        service=Service(is_active=True),
        incident=Incident(),
        user=None,
    )

    sender.send.assert_called_once()
    assert decision.allowed