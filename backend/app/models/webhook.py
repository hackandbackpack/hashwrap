"""
WebhookConfig model for notification integrations.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, AuditMixin, TimestampMixin


class WebhookConfig(BaseModel, AuditMixin, TimestampMixin):
    """Webhook configuration model for external notifications"""
    
    __tablename__ = "webhook_configs"
    
    # Basic webhook information
    name: Mapped[str] = mapped_column(
        String(100), 
        nullable=False,
        index=True,
        comment="Friendly name for the webhook"
    )
    
    webhook_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Target URL for webhook notifications"
    )
    
    # Event configuration
    events: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        comment="List of events that trigger this webhook"
    )
    
    # Webhook status
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True
    )
    
    # Optional configuration
    headers: Mapped[Optional[Dict[str, str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Custom HTTP headers for webhook requests"
    )
    
    secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Secret for webhook signature verification"
    )
    
    timeout_seconds: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        default=10,
        comment="Request timeout in seconds"
    )
    
    retry_attempts: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        default=3,
        comment="Number of retry attempts on failure"
    )
    
    # User who created the webhook
    created_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Relationships
    created_by_user = relationship(
        "User",
        back_populates="webhooks",
        foreign_keys=[created_by]
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_webhook_name", "name"),
        Index("idx_webhook_enabled", "is_enabled", "name"),
        Index("idx_webhook_creator", "created_by", "created_at"),
    )
    
    def __repr__(self) -> str:
        status = "enabled" if self.is_enabled else "disabled"
        return f"<WebhookConfig(id={self.id}, name={self.name}, {status})>"
    
    @property
    def supported_events(self) -> List[str]:
        """Get list of all supported webhook events"""
        return [
            'job.created',
            'job.started', 
            'job.paused',
            'job.resumed',
            'job.completed',
            'job.failed',
            'job.cancelled',
            'hash.cracked',
            'project.created',
            'project.expired',
            'upload.completed',
            'system.error',
            'system.maintenance'
        ]
    
    def validates_events(self) -> tuple[bool, Optional[str]]:
        """Validate that configured events are supported"""
        if not isinstance(self.events, list):
            return False, "events must be a list"
        
        if not self.events:
            return False, "at least one event must be configured"
        
        supported = self.supported_events
        for event in self.events:
            if event not in supported:
                return False, f"Unsupported event: {event}. Supported: {supported}"
        
        return True, None
    
    def should_trigger(self, event_type: str) -> bool:
        """Check if webhook should trigger for given event type"""
        return (
            self.is_enabled and 
            event_type in self.events
        )
    
    def get_request_headers(self) -> Dict[str, str]:
        """Get headers for webhook HTTP requests"""
        default_headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'HashWrap-Webhook/1.0'
        }
        
        if self.headers:
            default_headers.update(self.headers)
        
        return default_headers
    
    def validate_url(self) -> tuple[bool, Optional[str]]:
        """Validate webhook URL format"""
        if not self.webhook_url:
            return False, "webhook URL is required"
        
        if not self.webhook_url.startswith(('http://', 'https://')):
            return False, "webhook URL must start with http:// or https://"
        
        # Security: recommend HTTPS
        if self.webhook_url.startswith('http://'):
            return True, "Warning: HTTP URLs are not secure. Consider using HTTPS."
        
        return True, None