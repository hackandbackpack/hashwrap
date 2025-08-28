"""
User model for authentication and authorization
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, TimestampMixin


class UserRole(enum.Enum):
    """User role enumeration"""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(BaseModel, TimestampMixin):
    """User model for authentication and authorization"""
    __tablename__ = "users"
    
    # Basic user information
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # TOTP for 2FA
    totp_secret: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True
    )
    
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False
    )
    
    # Authorization
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.VIEWER,
        nullable=False
    )
    
    # Account status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False
    )
    
    # Login tracking
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    login_attempts: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        nullable=False
    )
    
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    projects = relationship("Project", back_populates="created_by_user")
    uploads = relationship("Upload", back_populates="uploaded_by_user")
    jobs = relationship("Job", back_populates="created_by_user")
    profiles = relationship("Profile", back_populates="created_by_user")
    webhooks = relationship("WebhookConfig", back_populates="created_by_user")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    # Database indexes
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_role", "role"),
        Index("idx_users_active", "is_active"),
        Index("idx_users_last_login", "last_login"),
    )
    
    def __repr__(self) -> str:
        return f"<User(email={self.email}, role={self.role.value})>"
    
    def is_admin(self) -> bool:
        """Check if user has admin role"""
        return self.role == UserRole.ADMIN
    
    def is_operator_or_higher(self) -> bool:
        """Check if user has operator or admin role"""
        return self.role in [UserRole.ADMIN, UserRole.OPERATOR]
    
    def can_reveal_passwords(self) -> bool:
        """Check if user can reveal cracked passwords"""
        return self.role in [UserRole.ADMIN, UserRole.OPERATOR]
    
    def can_export_data(self) -> bool:
        """Check if user can export data"""
        return self.role in [UserRole.ADMIN, UserRole.OPERATOR]
    
    def can_manage_jobs(self) -> bool:
        """Check if user can manage jobs (create, start, stop)"""
        return self.role in [UserRole.ADMIN, UserRole.OPERATOR]
    
    def is_locked(self) -> bool:
        """Check if user account is locked"""
        if not self.locked_until:
            return False
        return datetime.utcnow() < self.locked_until