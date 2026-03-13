from abc import ABC, abstractmethod
from app.core.notification.decision import NotificationDecision


class NotificationPolicy(ABC):
    """
    Notification 정책의 공통 인터페이스

    - 하나의 정책은 하나의 책임만 가진다
    - NotificationContext를 받아 판단한다
    - 판단 결과는 NotificationDecision으로 반환한다
    """

    @abstractmethod
    def evaluate(self, ctx) -> NotificationDecision:
        """
        알림을 보낼 수 있는지 평가한다.

        :param ctx: NotificationContext
        :return: NotificationDecision
        """
        raise NotImplementedError