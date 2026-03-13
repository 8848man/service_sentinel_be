from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UserDeviceToken(Base):
    __tablename__ = "user_device_tokens"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # FCM device token
    token = Column(String(255), nullable=False)

    # android / ios / web
    platform = Column(String(20), nullable=False)

    is_active = Column(Boolean, default=True)

    # 마지막으로 이 토큰으로 푸시를 보낸 시점
    last_seen_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # relationships
    user = relationship("User", back_populates="device_tokens")

    __table_args__ = (
        # 동일 토큰 중복 저장 방지
        UniqueConstraint("token", name="uq_user_device_token_token"),
    )