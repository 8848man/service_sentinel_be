from app.models.device_token import UserDeviceToken
from sqlalchemy.orm import Session


class DeviceTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_token(self, token: str) -> UserDeviceToken | None:
        return (
            self.db.query(UserDeviceToken)
            .filter(UserDeviceToken.token == token)
            .one_or_none()
        )

    def get_active_tokens_by_user(self, user_id: int) -> list[UserDeviceToken]:
        return (
            self.db.query(UserDeviceToken)
            .filter(
                UserDeviceToken.user_id == user_id,
                UserDeviceToken.is_active.is_(True),
            )
            .all()
        )

    def create(self, device: UserDeviceToken) -> UserDeviceToken:
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def deactivate(self, token: str):
        device = self.find_by_token(token)
        if device:
            device.is_active = False
            self.db.commit()