"""
Project model for client engagement tracking
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel, TimestampMixin, AuditMixin


class Project(BaseModel, TimestampMixin, AuditMixin):
    """Project model for organizing jobs by client engagement"""
    __tablename__ = "projects"
    
    # Basic project information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Legal/compliance information
    client_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    engagement_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    authorization_statement: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    expiration_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Foreign keys
    created_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Relationships
    created_by_user = relationship("User", back_populates="projects")
    uploads = relationship("Upload", back_populates="project")
    jobs = relationship("Job", back_populates="project")
    
    # Database indexes
    __table_args__ = (
        Index("idx_projects_name", "name"),
        Index("idx_projects_client", "client_name"),
        Index("idx_projects_engagement", "engagement_id"),
        Index("idx_projects_created_by", "created_by"),
        Index("idx_projects_expiration", "expiration_date"),
    )
    
    def __repr__(self) -> str:
        return f"<Project(name={self.name}, client={self.client_name})>"
    
    def is_expired(self) -> bool:
        """Check if project authorization has expired"""
        if not self.expiration_date:
            return False
        return datetime.utcnow() > self.expiration_date