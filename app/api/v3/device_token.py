from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.device_token import DeviceTokenRegisterRequest
from app.services.device_token_service import DeviceTokenService
from app.core.auth_v3 import get_firebase_user

router = APIRouter(prefix="/device-tokens", tags=["Device Tokens"])

@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def register_device_token(
    body: DeviceTokenRegisterRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Register (or update) FCM device token for current user.

    - Requires Firebase authentication
    - Idempotent (safe to call multiple times)
    """

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required."
        )

    # Firebase 인증 → User 확보
    user = await get_firebase_user(
        authorization=authorization,
        db=db,
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive."
        )

    service = DeviceTokenService(db)
    service.register(
        user_id=user.id,
        token=body.token,
        platform=body.platform,
    )

    return

@router.post("/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def register_device_token(
    body: DeviceTokenRegisterRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required."
        )

    service = DeviceTokenService(db)
    service.deactivate(
        token=body.token,
    )