from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    # Firebase Auth UID
    firebase_uid = Column(String(128), unique=True, index=True, nullable=False)

    email = Column(String, index=True)
    name = Column(String)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True))

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan",)

    device_tokens = relationship(
        "UserDeviceToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )