from abc import ABC, abstractmethod

from app.core.notification.context import NotificationContext


class NotificationSender(ABC):
    """
    Notification 발송 Port (Interface)

    - core.notification은 이 인터페이스만 의존해야 한다
    - 실제 구현(Firebase, Email, Slack 등)은 services 레이어에서 담당
    """

    @abstractmethod
    def send(self, ctx: NotificationContext) -> None:
        """
        Notification을 실제로 발송한다.
        실패 시 예외를 던질 수 있다 (재시도/로그는 상위 레이어 책임)
        """
        raise NotImplementedError