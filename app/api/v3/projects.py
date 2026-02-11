from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth_v3 import get_auth_context, get_firebase_user, verify_project_ownership
from app.repositories.project_repository import ProjectRepository
from app.repositories.api_key_repository import APIKeyRepository
from app.schemas.auth_context import AuthContext
from app.models.user import User
from app.schemas.project_schema import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ProjectWithStats,
    ProjectHealth,
    GuestBootstrapResponse
)
from app.schemas.api_key_schema import (
    APIKeyCreate,
    APIKeyResponse,
    APIKeyWithSecret,
    APIKeyListResponse
)

router = APIRouter(prefix="/projects", tags=["Projects (v3)"])


@router.post("/bootstrap", response_model=GuestBootstrapResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap_guest_project(
    request: ProjectCreate,
    db: Session = Depends(get_db),
):
    """
    Bootstrap a new guest-owned project (NO authentication required).

    This is the ONLY v3 endpoint that allows unauthenticated access.
    It creates a project and returns a one-time-shown API key.

    Use case: Allow guests to get started without Firebase authentication.

    Returns:
    - project: The created project details
    - api_key: The guest key (STORE SECURELY - shown only once!)

    Security notes:
    - Rate limit this endpoint to prevent abuse
    - Each call creates a new isolated project
    - Guest key is the master key for the project
    """
    from app.models.api_key import generate_api_key

    # Generate unique guest key
    guest_key = generate_api_key()

    # Create project with guest ownership
    repo = ProjectRepository(db)
    project = repo.create(
        name=request.name,
        description=request.description,
        guest_key=guest_key
    )

    # Create corresponding API key record for tracking
    api_key_repo = APIKeyRepository(db)
    api_key_obj = api_key_repo.create(
        project_id=project.id,
        name="Primary Guest Key",
        description="Auto-generated bootstrap key"
    )
    # Override the generated key with our guest_key
    api_key_obj.key_value = guest_key
    db.commit()
    db.refresh(project)

    return GuestBootstrapResponse(
        project=project,
        api_key=guest_key,
        message="API key shown only once. Store it securely!"
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    user: User = Depends(get_firebase_user),
    db: Session = Depends(get_db),
):
    """
    Create a new project.

    v3 REQUIRES Firebase authentication.
    The project will be owned by the authenticated user.
    """
    # Create project with user ownership
    repo = ProjectRepository(db)
    project = repo.create(
        name=request.name,
        description=request.description,
        user_id=user.id
    )

    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    is_active: bool = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    List projects owned by the authenticated user or guest.

    Authentication:
    - Firebase users: Returns projects where user_id matches
    - Guest users: Returns projects where guest_key matches

    Note: This endpoint does NOT use get_auth_context because there's no project_id in the path.
    """
    from datetime import datetime

    repo = ProjectRepository(db)

    # Firebase authentication (priority 1)
    if authorization:
        user = await get_firebase_user(authorization=authorization, db=db)
        projects = repo.find_by_user_id(
            user_id=user.id,
            is_active=is_active,
            skip=skip,
            limit=limit
        )
        repo.calculate_health_for_projects(projects)
        return projects


    # Guest authentication (priority 2)
    elif x_api_key:
        # Validate API key exists and is active
        api_key_repo = APIKeyRepository(db)
        api_key_obj = api_key_repo.find_by_key_value(x_api_key)

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
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key has expired"
            )

        # Update usage tracking
        api_key_repo.update_last_used(api_key_obj.id)

        # Find projects owned by this guest key
        projects = repo.find_by_guest_key(
            guest_key=x_api_key,
            is_active=is_active
        )

        # Also include projects where this is a delegated key
        delegated_project = repo.find_by_id(api_key_obj.project_id)
        if delegated_project and delegated_project not in projects:
            projects.append(delegated_project)

        repo.calculate_health_for_projects(projects)
        return projects[skip:skip+limit]

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide either Authorization header (Bearer token) or X-API-Key header."
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Get project by ID (requires ownership)"""
    # Verify ownership
    await verify_project_ownership(auth_context, db)

    repo = ProjectRepository(db)
    project = repo.find_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.get("/{project_id}/stats", response_model=ProjectWithStats)
async def get_project_stats(
    project_id: int,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Get project with statistics (requires ownership)"""
    # Verify ownership
    await verify_project_ownership(auth_context, db)

    repo = ProjectRepository(db)
    project = repo.find_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get stats from repository
    stats = repo.get_stats(project_id)

    return ProjectWithStats(
        **project.__dict__,
        **stats
    )


@router.get("/{project_id}/health", response_model=ProjectHealth)
async def get_project_health(
    project_id: int,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get derived health status for a project.
    This is NEVER stored - always calculated from service states and incidents.

    Returns:
    - status: HEALTHY, DEGRADED, or UNKNOWN
    - total_services: Total number of services
    - healthy_services: Services in HEALTHY state
    - error_services: Services in ERROR state
    - inactive_services: Services in INACTIVE state
    - active_incidents: Count of OPEN or INVESTIGATING incidents
    """
    # Verify ownership
    await verify_project_ownership(auth_context, db)

    repo = ProjectRepository(db)
    health = repo.get_health(project_id)

    return ProjectHealth(**health)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Update project (requires ownership)"""
    # Verify ownership
    await verify_project_ownership(auth_context, db)

    repo = ProjectRepository(db)
    project = repo.update(project_id, **data.model_dump(exclude_unset=True))

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Delete a project and ALL associated data (requires ownership).
    This is a destructive operation and cannot be undone.
    """
    # Verify ownership
    await verify_project_ownership(auth_context, db)

    repo = ProjectRepository(db)
    success = repo.delete(project_id)

    if not success:
        raise HTTPException(status_code=404, detail="Project not found")


# ===== API Key Management =====

@router.post("/{project_id}/api-keys", response_model=APIKeyWithSecret, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    project_id: int,
    request: APIKeyCreate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Create a new API key for a project (requires ownership).
    The key_value will ONLY be shown in this response - store it securely!
    """
    # Verify ownership
    await verify_project_ownership(auth_context, db)

    # Create API key
    repo = APIKeyRepository(db)
    api_key = repo.create(
        project_id=project_id,
        name=request.name,
        description=request.description,
        expires_at=request.expires_at
    )

    return api_key


@router.get("/{project_id}/api-keys", response_model=APIKeyListResponse)
async def list_project_api_keys(
    project_id: int,
    is_active: bool = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db)
):
    """List all API keys for a project (requires ownership)"""
    # Verify ownership
    await verify_project_ownership(auth_context, db)

    repo = APIKeyRepository(db)
    keys = repo.find_all_for_project(project_id, is_active=is_active, skip=skip, limit=limit)

    return APIKeyListResponse(
        project_id=project_id,
        total=len(keys),
        items=keys
    )


@router.delete("/{project_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    project_id: int,
    key_id: int,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Delete an API key (requires ownership)"""
    # Verify ownership
    await verify_project_ownership(auth_context, db)

    repo = APIKeyRepository(db)
    api_key = repo.find_by_id(key_id)

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    if api_key.project_id != project_id:
        raise HTTPException(status_code=403, detail="API key does not belong to this project")

    repo.delete(key_id)


@router.post("/{project_id}/api-keys/{key_id}/deactivate", response_model=APIKeyResponse)
async def deactivate_api_key(
    project_id: int,
    key_id: int,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Deactivate an API key (requires ownership)"""
    # Verify ownership
    await verify_project_ownership(auth_context, db)

    repo = APIKeyRepository(db)
    api_key = repo.find_by_id(key_id)

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    if api_key.project_id != project_id:
        raise HTTPException(status_code=403, detail="API key does not belong to this project")

    api_key = repo.deactivate(key_id)
    return api_key
