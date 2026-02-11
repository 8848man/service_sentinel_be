from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth_v3 import get_firebase_user, delete_firebase_user

router = APIRouter(prefix="/auth", tags=["Auth (v3)"])

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    print('test001, delete current user')
    """
    Delete currently authenticated Firebase user.

    Authentication:
    - Requires Authorization header (Bearer token)
    - Guest users cannot delete user accounts

    This will:
    - Delete the user record
    - Cascade delete owned projects
    """

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required."
        )

    # Firebase 인증
    user = await get_firebase_user(
        authorization=authorization,
        db=db
    )

    print('test002, user is $user', user)
    await delete_firebase_user(user.firebase_uid)

    # 유저 삭제
    db.delete(user)
    db.commit()

    return