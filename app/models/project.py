from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.core.database import Base


class Project(Base):
    """
    Project is the Aggregate Root.
    All Services (APIs), monitoring activities, and AI analyses belong to a Project.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Owner (exactly one of user_id OR guest_key must be set)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    guest_key = Column(String(200), unique=True, nullable=True, index=True)

    # Project status
    is_active = Column(Boolean, default=True, index=True)

    # notification options
    notification_enabled = Column(Boolean, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="projects")
    services = relationship("Service", back_populates="project", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="project", cascade="all, delete-orphan")

    @validates('user_id', 'guest_key')
    def validate_ownership_exclusivity(self, key, value):
        """
        Ensure exactly one of user_id or guest_key is set (not both, not neither).
        This validation runs when either field is being set.
        """
        # Allow setting during object construction
        if not hasattr(self, 'user_id') or not hasattr(self, 'guest_key'):
            return value

        # After construction, enforce mutual exclusivity
        if key == 'user_id':
            if value is not None and self.guest_key is not None:
                raise ValueError("Cannot set user_id when guest_key is already set. A project must be owned by either a Firebase user OR a guest, not both.")
        elif key == 'guest_key':
            if value is not None and self.user_id is not None:
                raise ValueError("Cannot set guest_key when user_id is already set. A project must be owned by either a Firebase user OR a guest, not both.")

        return value
