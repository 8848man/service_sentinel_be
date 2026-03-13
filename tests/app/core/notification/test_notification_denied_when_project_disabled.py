from app.core.notification.context import NotificationContext
from app.core.notification.enum import NotificationDecisionResult
from app.core.notification.policies.chain import PolicyChain
from app.models import Project, Service, Incident, User


def test_notification_denied_when_project_disabled():
    ctx = NotificationContext(
        project=Project(is_active=False),
        service=Service(is_active=True),
        incident=Incident(),
        user=User(is_active=True),
    )

    decision = PolicyChain([...]).evaluate(ctx)

    assert not decision.allowed
    assert decision.reason == NotificationDecisionResult.PROJECT_DISABLED