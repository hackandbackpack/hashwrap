"""
Upload model for file tracking with security metadata.
"""

from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, TimestampMixin


class Upload(BaseModel, TimestampMixin):
    """Upload model for tracking uploaded files"""
    
    __tablename__ = "uploads"
    
    # File identification
    filename: Mapped[str] = mapped_column(
        String(255), 
        nullable=False,
        index=True,
        comment="Stored filename on disk"
    )
    
    original_filename: Mapped[str] = mapped_column(
        String(255), 
        nullable=False,
        index=True,
        comment="Original filename from upload"
    )
    
    # File properties
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True
    )
    
    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hash of file content"
    )
    
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )
    
    # Project association
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # User who uploaded the file
    uploaded_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True
    )
    
    # Relationships
    project = relationship(
        "Project",
        back_populates="uploads",
        foreign_keys=[project_id]
    )
    
    uploaded_by_user = relationship(
        "User",
        back_populates="uploads",
        foreign_keys=[uploaded_by]
    )
    
    jobs = relationship(
        "Job",
        back_populates="upload",
        cascade="all, delete-orphan"
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_upload_project_created", "project_id", "created_at"),
        Index("idx_upload_uploader", "uploaded_by", "created_at"),
        Index("idx_upload_file_size", "file_size"),
        Index("idx_upload_mime_type", "mime_type"),
        Index("idx_upload_hash", "file_hash"),
        Index("idx_upload_filename", "filename"),
    )
    
    def __repr__(self) -> str:
        return f"<Upload(id={self.id}, filename={self.original_filename}, size={self.file_size})>"
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes"""
        return round(self.file_size / (1024 * 1024), 2)
    
    @property
    def file_extension(self) -> str:
        """Get file extension from original filename"""
        return self.original_filename.split('.')[-1].lower() if '.' in self.original_filename else ''
    
    def is_text_file(self) -> bool:
        """Check if upload is a text-based hash file"""
        text_mime_types = [
            'text/plain',
            'application/octet-stream',  # Often used for hash files
            'text/csv'
        ]
        text_extensions = ['txt', 'hash', 'lst', 'csv']
        
        return (
            self.mime_type in text_mime_types or 
            self.file_extension in text_extensions
        )