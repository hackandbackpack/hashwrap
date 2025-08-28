"""
Base database models and mixins
"""

from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


class BaseModel(Base):
    """Base model with UUID primary key"""
    __abstract__ = True
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()::text")
    )


class UUIDMixin:
    """Mixin for UUID primary key (alias for backwards compatibility)"""
    
    @declared_attr
    def id(cls) -> Mapped[str]:
        return mapped_column(
            UUID(as_uuid=False),
            primary_key=True,
            default=lambda: str(uuid4()),
            server_default=text("gen_random_uuid()::text")
        )
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    
    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    
    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )


class AuditMixin:
    """Mixin for audit trail fields"""
    
    @declared_attr
    def created_by(cls) -> Mapped[str]:
        return mapped_column(
            UUID(as_uuid=False),
            nullable=True
        )
    
    @declared_attr
    def updated_by(cls) -> Mapped[str]:
        return mapped_column(
            UUID(as_uuid=False),
            nullable=True
        )