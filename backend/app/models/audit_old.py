"""
AuditLog model for security and compliance logging.
"""

from typing import Any, Dict, Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, TimestampMixin


class AuditLog(BaseModel, TimestampMixin):
    """Audit log model for security and compliance tracking"""
    
    __tablename__ = "audit_logs"
    
    # User association (optional for system events)
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Action details
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of action performed"
    )
    
    # Resource information
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of resource affected (user, project, job, etc.)"
    )
    
    resource_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
        index=True,
        comment="ID of the affected resource"
    )
    
    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 compatible
        nullable=True,
        index=True
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Additional context as JSON
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional context and details about the action"
    )
    
    # Relationships
    user = relationship(
        "User",
        back_populates="audit_logs",
        foreign_keys=[user_id]
    )
    
    # Indexes for efficient queries and compliance reporting
    __table_args__ = (
        Index("idx_audit_user_created", "user_id", "created_at"),
        Index("idx_audit_action_created", "action", "created_at"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_ip_created", "ip_address", "created_at"),
        Index("idx_audit_created", "created_at"),
        # Composite indexes for common queries
        Index("idx_audit_user_action", "user_id", "action", "created_at"),
        Index("idx_audit_resource_action", "resource_type", "action", "created_at"),
    )
    
    def __repr__(self) -> str:
        user_info = f"user_id={self.user_id}" if self.user_id else "system"
        return f"<AuditLog(id={self.id}, action={self.action}, {user_info})>"
    
    @classmethod
    def get_supported_actions(cls) -> Dict[str, List[str]]:
        """Get mapping of resource types to supported actions"""
        return {
            'user': [
                'create', 'update', 'delete', 'login', 'logout', 
                'password_change', 'totp_enable', 'totp_disable',
                'role_change', 'activate', 'deactivate'
            ],
            'project': [
                'create', 'update', 'delete', 'view', 'expire'
            ],
            'upload': [
                'create', 'delete', 'download', 'view'
            ],
            'job': [
                'create', 'start', 'pause', 'resume', 'cancel', 
                'delete', 'view', 'complete', 'fail'
            ],
            'profile': [
                'create', 'update', 'delete', 'view', 'use'
            ],
            'webhook': [
                'create', 'update', 'delete', 'trigger', 'enable', 'disable'
            ],
            'system': [
                'startup', 'shutdown', 'error', 'maintenance', 
                'backup', 'restore', 'config_change'
            ]
        }
    
    @property
    def is_security_event(self) -> bool:
        """Check if this is a security-relevant event"""
        security_actions = [
            'login', 'logout', 'password_change', 'totp_enable', 
            'totp_disable', 'role_change', 'activate', 'deactivate',
            'unauthorized_access', 'permission_denied'
        ]
        return self.action in security_actions
    
    @property
    def is_system_event(self) -> bool:
        """Check if this is a system-level event"""
        return self.resource_type == 'system'
    
    @property
    def display_action(self) -> str:
        """Get human-readable action description"""
        action_map = {
            'create': 'Created',
            'update': 'Updated', 
            'delete': 'Deleted',
            'view': 'Viewed',
            'login': 'Logged in',
            'logout': 'Logged out',
            'password_change': 'Changed password',
            'totp_enable': 'Enabled 2FA',
            'totp_disable': 'Disabled 2FA',
            'role_change': 'Changed role',
            'activate': 'Activated',
            'deactivate': 'Deactivated',
            'start': 'Started',
            'pause': 'Paused',
            'resume': 'Resumed',
            'cancel': 'Cancelled',
            'complete': 'Completed',
            'fail': 'Failed'
        }
        return action_map.get(self.action, self.action.title())
    
    def get_display_summary(self) -> str:
        """Get a human-readable summary of the audit event"""
        user_part = f"User {self.user_id}" if self.user_id else "System"
        resource_part = f"{self.resource_type}"
        if self.resource_id:
            resource_part += f" {self.resource_id}"
        
        return f"{user_part} {self.display_action.lower()} {resource_part}"