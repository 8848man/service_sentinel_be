from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class ServiceType(str, enum.Enum):
    HTTP_API = "http_api"
    HTTPS_API = "https_api"
    GCP_ENDPOINT = "gcp_endpoint"
    FIREBASE = "firebase"
    WEBSOCKET = "websocket"
    GRPC = "grpc"


class HttpMethod(str, enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"


class ServiceState(str, enum.Enum):
    """Service operational state"""
    HEALTHY = "healthy"
    ERROR = "error"
    INACTIVE = "inactive"


class Service(Base):
    """
    Service represents an API or monitoring target.
    Services are NOT aggregate roots - they belong to a Project.
    """
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)

    # Endpoint configuration
    endpoint_url = Column(String(500), nullable=False)
    http_method = Column(Enum(HttpMethod), default=HttpMethod.GET)
    service_type = Column(Enum(ServiceType), nullable=False)

    # Advanced config (JSON field for flexibility)
    headers = Column(JSON, default=dict)  # {"Authorization": "Bearer token"}
    request_body = Column(JSON, nullable=True)  # For POST/PUT
    expected_status_codes = Column(JSON, default=lambda: [200])  # [200, 201, 204]
    timeout_seconds = Column(Integer, default=10)

    # Monitoring configuration
    check_interval_seconds = Column(Integer, default=60)  # How often to check
    failure_threshold = Column(Integer, default=3)  # Failures before incident
    is_active = Column(Boolean, default=True, index=True)
    service_state = Column(
        Enum(ServiceState),
        default=ServiceState.HEALTHY,
        nullable=False,
        index=True
    )

    # notification options
    notification_enabled = Column(Boolean, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_checked_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="services")
    health_checks = relationship("HealthCheck", back_populates="service", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="service", cascade="all, delete-orphan")