from typing import Optional
from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.orm import Session
from firebase_admin import auth as firebase_auth

from app.core.database import get_db
from app.repositories.user_repository import UserRepository
from app.repositories.api_key_repository import APIKeyRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.auth_context import AuthContext
from app.models.user import User


def verify_firebase_token(token: str) -> dict:
    """
    Verify Firebase JWT token and return decoded token payload.
    Raises HTTPException if token is invalid.
    """
    try:
        import firebase_admin

        # Firebase 앱 정보 확인
        app = firebase_admin.get_app()
        print(f"Firebase App Name: {app.name}")
        print(f"Firebase Project ID: {app.project_id}")

        # 또는 credentials에서 직접 확인
        print(f"Credentials Project ID: {app.credential.project_id}")
        decoded_token = firebase_auth.verify_id_token(token)
        print(decoded_token)
        return decoded_token
    except firebase_auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token"
        )
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token has expired"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}"
        )


async def get_auth_context(
    project_id: int,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> AuthContext:
    """
    Unified authentication for v3 APIs.

    Authentication priority:
    1. Authorization: Bearer <firebase_jwt> (Firebase authentication)
    2. X-API-Key: <api_key> (Guest authentication)

    If both headers exist, Authorization takes priority.
    Invalid or missing credentials → 401 Unauthorized

    Returns AuthContext with user identity and project context.
    """
    # Priority 1: Firebase JWT authentication
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format. Expected 'Bearer <token>'"
            )

        token = authorization[7:]  # Remove "Bearer " prefix
        decoded_token = verify_firebase_token(token)

        firebase_uid = decoded_token.get("uid")
        email = decoded_token.get("email")
        name = decoded_token.get("name")

        if not firebase_uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Firebase token missing uid"
            )

        # Find or create user
        user_repo = UserRepository(db)
        user = user_repo.find_or_create_by_firebase_uid(
            firebase_uid=firebase_uid,
            email=email,
            name=name
        )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )

        return AuthContext(
            user_id=user.id,
            firebase_uid=firebase_uid,
            guest_uuid=None,
            auth_type="firebase",
            project_id=project_id
        )

    # Priority 2: Guest API key authentication
    elif x_api_key:
        api_key_repo = APIKeyRepository(db)
        api_key_obj = api_key_repo.find_by_key_value(x_api_key)

        print(x_api_key)

        if not api_key_obj:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )

        if not api_key_obj.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key is inactive"
            )

        # Check expiration
        from datetime import datetime
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key has expired"
            )

        # Update usage tracking
        api_key_repo.update_last_used(api_key_obj.id)

        return AuthContext(
            user_id=None,
            firebase_uid=None,
            guest_uuid=api_key_obj.key_value,
            auth_type="guest",
            project_id=project_id
        )

    # No authentication provided
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide either Authorization header (Bearer token) or X-API-Key header."
        )


async def verify_project_ownership(
    auth_context: AuthContext,
    db: Session = Depends(get_db)
) -> AuthContext:
    """
    Verify that the authenticated user has access to the project.

    Validation rules:
    - Project must exist
    - For Firebase users: project.user_id must match auth_context.user_id
    - For Guest users: project_id must match the API key's project

    Returns the same AuthContext if validation passes.
    Raises 403 Forbidden if validation fails.
    """
    project_repo = ProjectRepository(db)
    project = project_repo.find_by_id(auth_context.project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Firebase user validation
    if auth_context.auth_type == "firebase":
        if project.user_id != auth_context.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You do not own this project."
            )

    # Guest user validation (API key)
    elif auth_context.auth_type == "guest":
        # Check two types of guest access:
        # 1. Primary guest key (project.guest_key matches the API key)
        # 2. Delegated API key (api_keys table, project-scoped)

        # Check if this is the primary guest key
        if project.guest_key == auth_context.guest_uuid:
            # Guest owns this project directly via guest_key
            return auth_context

        # Otherwise, check if it's a delegated API key
        api_key_repo = APIKeyRepository(db)
        api_key_obj = api_key_repo.find_by_key_value(auth_context.guest_uuid)

        if not api_key_obj or api_key_obj.project_id != auth_context.project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. API key does not have access to this project."
            )

    return auth_context


async def get_firebase_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """
    Firebase-only authentication for endpoints that require Firebase users.

    Used for:
    - Project creation (only Firebase users can create projects)
    - Project listing (only Firebase users can list their projects)
    - API key management (only project owners can manage keys)

    Returns the authenticated User object.
    Raises 401 if authentication fails or if not Firebase user.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Only Firebase-authenticated users can access this endpoint."
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    token = authorization[7:]
    decoded_token = verify_firebase_token(token)

    firebase_uid = decoded_token.get("uid")
    email = decoded_token.get("email")
    name = decoded_token.get("name")

    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token missing uid"
        )

    # Find or create user
    user_repo = UserRepository(db)
    user = user_repo.find_or_create_by_firebase_uid(
        firebase_uid=firebase_uid,
        email=email,
        name=name
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user

async def delete_firebase_user(firebase_uid: str):
    try:
        firebase_auth.delete_user(firebase_uid)
    except firebase_auth.UserNotFoundError:
        # 이미 삭제된 경우는 무시해도 됨
        pass
    except Exception as e:
        raise e