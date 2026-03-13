from typing import Optional
from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.project_schema import ProjectHealth, ProjectResponse


class ProjectRepository:
    """Repository for Project aggregate root operations"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        description: Optional[str] = None,
        user_id: Optional[int] = None,
        guest_key: Optional[str] = None
    ) -> Project:
        """
        Create a new project.

        Args:
            name: Project name
            description: Optional project description
            user_id: Firebase user ID (for authenticated users)
            guest_key: Guest API key (for guest users)

        Returns:
            Created project

        Raises:
            ValueError: If mutual exclusivity constraint is violated
        """
        # Validate mutual exclusivity: exactly one of user_id OR guest_key must be set
        if not ((user_id is not None) ^ (guest_key is not None)):
            raise ValueError(
                "Exactly one of user_id or guest_key must be set. "
                "A project must be owned by either a Firebase user OR a guest, not both and not neither."
            )

        project = Project(
            name=name,
            description=description,
            user_id=user_id,
            guest_key=guest_key,
            is_active=True
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def find_by_id(self, project_id: int) -> Optional[Project]:
        """Find project by ID"""
        return self.db.query(Project).filter(Project.id == project_id).first()

    def find_all(
        self,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> list[Project]:
        """Find all projects with optional filtering"""
        query = self.db.query(Project)

        if is_active is not None:
            query = query.filter(Project.is_active == is_active)

        return query.order_by(Project.created_at.desc()).offset(skip).limit(limit).all()

    def update(self, project_id: int, **kwargs) -> Optional[Project]:
        """Update project"""
        project = self.find_by_id(project_id)
        if not project:
            return None

        for key, value in kwargs.items():
            if hasattr(project, key) and value is not None:
                setattr(project, key, value)

        self.db.commit()
        self.db.refresh(project)
        return project

    def delete(self, project_id: int) -> bool:
        """Delete project and all associated data (cascade)"""
        project = self.find_by_id(project_id)
        if not project:
            return False

        self.db.delete(project)
        self.db.commit()
        return True

    def count(self, is_active: Optional[bool] = None) -> int:
        """Count projects"""
        query = self.db.query(Project)

        if is_active is not None:
            query = query.filter(Project.is_active == is_active)

        return query.count()

    def find_by_user_id(
        self,
        user_id: int,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> list[Project]:
        """Find all projects owned by a specific user"""
        query = self.db.query(Project).filter(Project.user_id == user_id)

        if is_active is not None:
            query = query.filter(Project.is_active == is_active)

        return query.order_by(Project.created_at.desc()).offset(skip).limit(limit).all()

    def find_by_guest_key(
        self,
        guest_key: str,
        is_active: Optional[bool] = None
    ) -> list[Project]:
        """
        Find all projects owned by a specific guest key.

        Args:
            guest_key: The guest API key value
            is_active: Optional filter for active/inactive projects

        Returns:
            List of projects owned by this guest key
        """
        query = self.db.query(Project).filter(Project.guest_key == guest_key)

        if is_active is not None:
            query = query.filter(Project.is_active == is_active)

        return query.order_by(Project.created_at.desc()).all()

    def get_stats(self, project_id: int) -> dict:
        """
        Get statistics for a project.
        Returns dict with total_services, active_services, total_incidents, open_incidents.
        """
        from app.models.service import Service
        from app.models.incident import Incident, IncidentStatus
        from sqlalchemy import func

        # Count services
        total_services = self.db.query(func.count(Service.id)).filter(
            Service.project_id == project_id
        ).scalar() or 0

        active_services = self.db.query(func.count(Service.id)).filter(
            Service.project_id == project_id,
            Service.is_active == True
        ).scalar() or 0

        # Count incidents (join with Service to filter by project)
        total_incidents = self.db.query(func.count(Incident.id)).join(Service).filter(
            Service.project_id == project_id
        ).scalar() or 0

        open_incidents = self.db.query(func.count(Incident.id)).join(Service).filter(
            Service.project_id == project_id,
            Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.INVESTIGATING])
        ).scalar() or 0

        return {
            "total_services": total_services,
            "active_services": active_services,
            "total_incidents": total_incidents,
            "open_incidents": open_incidents
        }

    def get_health(self, project_id: int) -> dict:
        """
        Calculate derived project health from service states and incidents.
        NEVER stores this data - always calculated on-demand.

        Returns:
            dict with:
                - status: "HEALTHY" | "DEGRADED" | "UNKNOWN"
                - total_services: int
                - healthy_services: int
                - error_services: int
                - inactive_services: int
                - active_incidents: int
        """
        from app.models.service import Service, ServiceState
        from app.models.incident import Incident, IncidentStatus
        from sqlalchemy import func

        # Count services by state using GROUP BY
        service_counts = self.db.query(
            Service.service_state,
            func.count(Service.id).label('count')
        ).filter(
            Service.project_id == project_id
        ).group_by(Service.service_state).all()

        # Convert to dict with all states initialized to 0
        state_map = {state: 0 for state in ServiceState}
        for state, count in service_counts:
            state_map[state] = count

        total_services = sum(state_map.values())

        # Count active incidents
        active_incidents = self.db.query(func.count(Incident.id)).join(Service).filter(
            Service.project_id == project_id,
            Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.INVESTIGATING])
        ).scalar() or 0

        # Determine project health status
        if total_services == 0:
            status = "UNKNOWN"
        elif state_map[ServiceState.ERROR] > 0 or active_incidents > 0:
            status = "DEGRADED"
        else:
            status = "HEALTHY"

        return {
            "status": status,
            "total_services": total_services,
            "healthy_services": state_map[ServiceState.HEALTHY],
            "error_services": state_map[ServiceState.ERROR],
            "inactive_services": state_map[ServiceState.INACTIVE],
            "active_incidents": active_incidents
        }

    def get_health_map(
            self,
            project_ids: list[int],
    ) -> dict[int, ProjectHealth]:
        """
        Calculate derived project health for multiple projects at once.
        NEVER stores this data - always calculated on-demand.

        Returns:
            dict mapping:
                project_id -> ProjectHealth
        """
        from app.models.service import Service, ServiceState
        from app.models.incident import Incident, IncidentStatus
        from sqlalchemy import func

        if not project_ids:
            return {}

        # -----------------------------
        # 1. 서비스 상태 집계 (project_id + service_state)
        # -----------------------------
        service_counts = self.db.query(
            Service.project_id,
            Service.service_state,
            func.count(Service.id).label("count"),
        ).filter(
            Service.project_id.in_(project_ids)
        ).group_by(
            Service.project_id,
            Service.service_state,
        ).all()

        # project_id -> {ServiceState: count}
        service_state_map: dict[int, dict[ServiceState, int]] = {
            pid: {state: 0 for state in ServiceState}
            for pid in project_ids
        }

        for project_id, state, count in service_counts:
            service_state_map[project_id][state] = count

        # -----------------------------
        # 2. 활성 incident 집계
        # -----------------------------
        incident_counts = self.db.query(
            Service.project_id,
            func.count(Incident.id).label("count"),
        ).join(Service).filter(
            Service.project_id.in_(project_ids),
            Incident.status.in_([
                IncidentStatus.OPEN,
                IncidentStatus.INVESTIGATING,
            ])
        ).group_by(
            Service.project_id
        ).all()

        # project_id -> active_incident_count
        incident_map: dict[int, int] = {
            project_id: count
            for project_id, count in incident_counts
        }

        # -----------------------------
        # 3. ProjectHealth 생성
        # -----------------------------
        health_map: dict[int, ProjectHealth] = {}

        for project_id in project_ids:
            state_map = service_state_map[project_id]
            total_services = sum(state_map.values())
            active_incidents = incident_map.get(project_id, 0)

            if total_services == 0:
                status = "NOSERVICE"
            elif state_map[ServiceState.ERROR] > 0 or active_incidents > 0:
                status = "DEGRADED"
            else:
                status = "HEALTHY"

            health_map[project_id] = ProjectHealth(
                status=status,
                total_services=total_services,
                healthy_services=state_map[ServiceState.HEALTHY],
                error_services=state_map[ServiceState.ERROR],
                inactive_services=state_map[ServiceState.INACTIVE],
                active_incidents=active_incidents,
            )

        return health_map

    def calculate_health_for_projects(self, projects: list[Project]) -> None:
        project_ids = [p.id for p in projects]

        health_map = self.get_health_map(project_ids)

        for project in projects:
            project.health = health_map.get(project.id)