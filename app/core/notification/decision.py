from typing import Optional


class NotificationDecision:
    """
    Notification 정책 평가 결과를 나타내는 도메인 객체
    """

    def __init__(self, allowed: bool, reason: Optional[str] = None):
        self.allowed = allowed
        self.reason = reason

    @classmethod
    def allow(cls) -> "NotificationDecision":
        return cls(allowed=True)

    @classmethod
    def block(cls, reason: str) -> "NotificationDecision":
        return cls(allowed=False, reason=reason)

    def __bool__(self) -> bool:
        """
        if decision: 형태로 사용 가능하게 함
        """
        return self.allowed

    def __repr__(self) -> str:
        if self.allowed:
            return "NotificationDecision(allowed=True)"
        return f"NotificationDecision(allowed=False, reason='{self.reason}')"