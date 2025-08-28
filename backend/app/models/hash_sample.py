"""
HashSample and CrackResult models for hash tracking and results.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, TimestampMixin


class HashSample(BaseModel, TimestampMixin):
    """Individual hash sample within a cracking job"""
    
    __tablename__ = "hash_samples"
    
    # Job association
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Hash data
    hash_value: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        index=True,
        comment="The actual hash value to crack"
    )
    
    salt: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        index=True,
        comment="Salt value if hash is salted"
    )
    
    # Cracking results (denormalized for performance)
    cracked_password: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="The cracked password if found"
    )
    
    cracked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Timestamp when hash was cracked"
    )
    
    # Relationships
    job = relationship(
        "Job",
        back_populates="hash_samples",
        foreign_keys=[job_id]
    )
    
    crack_result = relationship(
        "CrackResult",
        back_populates="hash_sample",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_hash_sample_job", "job_id", "created_at"),
        Index("idx_hash_sample_hash", "hash_value"),
        Index("idx_hash_sample_salt", "salt"),
        Index("idx_hash_sample_cracked", "cracked_at"),
        Index("idx_hash_sample_job_cracked", "job_id", "cracked_at"),
        # Composite index for finding uncracked hashes
        Index("idx_hash_sample_uncracked", "job_id", "cracked_password"),
    )
    
    def __repr__(self) -> str:
        status = "cracked" if self.is_cracked else "uncracked"
        return f"<HashSample(id={self.id}, hash={self.hash_value[:16]}..., {status})>"
    
    @property
    def is_cracked(self) -> bool:
        """Check if this hash has been cracked"""
        return self.cracked_password is not None
    
    @property
    def hash_preview(self) -> str:
        """Get a preview of the hash for display purposes"""
        if len(self.hash_value) <= 32:
            return self.hash_value
        return f"{self.hash_value[:16]}...{self.hash_value[-8:]}"
    
    @property
    def has_salt(self) -> bool:
        """Check if this hash has an associated salt"""
        return self.salt is not None and len(self.salt) > 0


class CrackResult(BaseModel, TimestampMixin):
    """Detailed crack result information"""
    
    __tablename__ = "crack_results"
    
    # Job association
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Hash sample association
    hash_sample_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("hash_samples.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One result per hash sample
        index=True
    )
    
    # Crack details
    password: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The successfully cracked password"
    )
    
    cracked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Timestamp when password was cracked"
    )
    
    method_used: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Attack method that cracked this password (dictionary, brute-force, etc.)"
    )
    
    # Relationships
    job = relationship(
        "Job",
        back_populates="crack_results",
        foreign_keys=[job_id]
    )
    
    hash_sample = relationship(
        "HashSample",
        back_populates="crack_result",
        foreign_keys=[hash_sample_id]
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_crack_result_job", "job_id", "cracked_at"),
        Index("idx_crack_result_method", "method_used", "cracked_at"),
        Index("idx_crack_result_password", "password"),  # For pattern analysis
        Index("idx_crack_result_hash_sample", "hash_sample_id"),
    )
    
    def __repr__(self) -> str:
        return f"<CrackResult(id={self.id}, job_id={self.job_id}, method={self.method_used})>"
    
    @property
    def password_length(self) -> int:
        """Get the length of the cracked password"""
        return len(self.password)
    
    @property
    def password_complexity_score(self) -> int:
        """Simple password complexity scoring (0-4)"""
        score = 0
        if any(c.islower() for c in self.password):
            score += 1
        if any(c.isupper() for c in self.password):
            score += 1
        if any(c.isdigit() for c in self.password):
            score += 1
        if any(not c.isalnum() for c in self.password):
            score += 1
        return score