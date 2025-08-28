"""
Job and JobEvent models for hash cracking orchestration.
"""

import enum
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, AuditMixin, TimestampMixin


class JobStatus(str, enum.Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXHAUSTED = "exhausted"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobEventType(str, enum.Enum):
    """Job event type enumeration"""
    CREATED = "created"
    STARTED = "started"
    PAUSED = "paused"
    RESUMED = "resumed"
    PROGRESS = "progress"
    HASH_CRACKED = "hash_cracked"
    ATTACK_COMPLETED = "attack_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ERROR = "error"
    STATUS_UPDATE = "status_update"


class Job(BaseModel, AuditMixin, TimestampMixin):
    """Job model for hash cracking operations"""
    
    __tablename__ = "jobs"
    
    # Basic job information
    name: Mapped[str] = mapped_column(
        String(255), 
        nullable=False,
        index=True
    )
    
    # Project and upload association
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    upload_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Hash configuration
    hash_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Detected or specified hash type"
    )
    
    profile_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Attack profile used for this job"
    )
    
    # Job status and progress
    status: Mapped[JobStatus] = mapped_column(
        String(20),
        nullable=False,
        default=JobStatus.QUEUED,
        index=True
    )
    
    total_hashes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        index=True
    )
    
    cracked_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        index=True
    )
    
    # Timing information
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    # User who created the job
    created_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True
    )
    
    # Relationships
    project = relationship(
        "Project",
        back_populates="jobs",
        foreign_keys=[project_id]
    )
    
    upload = relationship(
        "Upload",
        back_populates="jobs",
        foreign_keys=[upload_id]
    )
    
    created_by_user = relationship(
        "User",
        back_populates="jobs",
        foreign_keys=[created_by]
    )
    
    events = relationship(
        "JobEvent",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobEvent.created_at"
    )
    
    hash_samples = relationship(
        "HashSample",
        back_populates="job",
        cascade="all, delete-orphan"
    )
    
    crack_results = relationship(
        "CrackResult",
        back_populates="job",
        cascade="all, delete-orphan"
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_job_project_status", "project_id", "status"),
        Index("idx_job_status_created", "status", "created_at"),
        Index("idx_job_hash_type", "hash_type"),
        Index("idx_job_profile", "profile_name"),
        Index("idx_job_progress", "total_hashes", "cracked_count"),
        Index("idx_job_timing", "started_at", "completed_at"),
        Index("idx_job_creator", "created_by", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<Job(id={self.id}, name={self.name}, status={self.status})>"
    
    @property
    def progress_percentage(self) -> float:
        """Calculate cracking progress percentage"""
        if not self.total_hashes or self.total_hashes == 0:
            return 0.0
        return round((self.cracked_count / self.total_hashes) * 100, 2)
    
    @property
    def is_active(self) -> bool:
        """Check if job is currently active"""
        return self.status in (JobStatus.PREPARING, JobStatus.RUNNING)
    
    @property
    def is_completed(self) -> bool:
        """Check if job has completed (successfully or not)"""
        return self.status in (
            JobStatus.COMPLETED, 
            JobStatus.EXHAUSTED, 
            JobStatus.FAILED, 
            JobStatus.CANCELLED
        )
    
    @property
    def runtime_seconds(self) -> Optional[int]:
        """Calculate job runtime in seconds"""
        if not self.started_at:
            return None
        
        end_time = self.completed_at or datetime.now()
        return int((end_time - self.started_at).total_seconds())


class JobEvent(BaseModel, TimestampMixin):
    """Job event model for tracking job state changes and progress"""
    
    __tablename__ = "job_events"
    
    # Job association
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Event details
    event_type: Mapped[JobEventType] = mapped_column(
        String(30),
        nullable=False,
        index=True
    )
    
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    # Flexible metadata storage
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True
    )
    
    # Relationships
    job = relationship(
        "Job",
        back_populates="events",
        foreign_keys=[job_id]
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_job_event_job_created", "job_id", "created_at"),
        Index("idx_job_event_type", "event_type", "created_at"),
        Index("idx_job_event_created", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<JobEvent(id={self.id}, type={self.event_type}, job_id={self.job_id})>"