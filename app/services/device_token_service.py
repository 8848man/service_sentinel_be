from sqlalchemy.orm import Session

from app.models.device_token import UserDeviceToken
from app.repositories.device_token_repository import DeviceTokenRepository

class DeviceTokenService:
    def __init__(self, db: Session):
        self.repo = DeviceTokenRepository(db)

    def register(self, *, user_id: int, token: str, platform: str):
        device = self.repo.find_by_token(token)

        if device:
            device.user_id = user_id
            device.platform = platform
            device.is_active = True
        else:
            device = UserDeviceToken(
                user_id=user_id,
                token=token,
                platform=platform,
            )
            self.repo.create(device)

    def deactivate(self, token: str):
        self.repo.deactivate(token)

    def get_active_tokens(self, user_id: int) -> list[UserDeviceToken]:
        return self.repo.get_active_tokens_by_user(user_id)