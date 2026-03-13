from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Repository for User operations"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, firebase_uid: str, email: Optional[str] = None, name: Optional[str] = None) -> User:
        """Create a new user"""
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            name=name,
            is_active=True
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def find_by_id(self, user_id: int) -> Optional[User]:
        """Find user by internal ID"""
        return self.db.query(User).filter(User.id == user_id).first()

    def find_by_firebase_uid(self, firebase_uid: str) -> Optional[User]:
        """Find user by Firebase UID"""
        return self.db.query(User).filter(User.firebase_uid == firebase_uid).first()

    def find_or_create_by_firebase_uid(
        self,
        firebase_uid: str,
        email: Optional[str] = None,
        name: Optional[str] = None
    ) -> User:
        """Find user by Firebase UID or create if not exists"""
        user = self.find_by_firebase_uid(firebase_uid)
        if user:
            # Update last login
            user.last_login_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
            return user
        return self.create(firebase_uid=firebase_uid, email=email, name=name)

    def update_last_login(self, user_id: int) -> bool:
        """Update last login timestamp"""
        user = self.find_by_id(user_id)
        if not user:
            return False

        user.last_login_at = datetime.utcnow()
        self.db.commit()
        return True

    def delete_by_firebase_uid(self, firebase_uid: str):
        user = self.find_by_firebase_uid(firebase_uid)
        if not user:
            return None

        self.db.delete(user)
        self.db.commit()
        return user