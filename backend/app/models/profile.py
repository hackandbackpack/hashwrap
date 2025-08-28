"""
Profile model for attack configuration management.
"""

from typing import Any, Dict, Optional

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, AuditMixin, TimestampMixin


class Profile(BaseModel, AuditMixin, TimestampMixin):
    """Attack profile model for hashcat configuration templates"""
    
    __tablename__ = "profiles"
    
    # Basic profile information
    name: Mapped[str] = mapped_column(
        String(100), 
        nullable=False,
        unique=True,
        index=True
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description of the attack profile and use cases"
    )
    
    # Profile configuration as JSON
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="JSON configuration for hashcat attacks and wordlists"
    )
    
    # Default profile flag
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether this is a default system profile"
    )
    
    # User who created the profile
    created_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True
    )
    
    # Relationships
    created_by_user = relationship(
        "User",
        back_populates="profiles",
        foreign_keys=[created_by]
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_profile_name", "name"),
        Index("idx_profile_default", "is_default", "name"),
        Index("idx_profile_creator", "created_by", "created_at"),
    )
    
    def __repr__(self) -> str:
        default_indicator = " (default)" if self.is_default else ""
        return f"<Profile(id={self.id}, name={self.name}{default_indicator})>"
    
    @property
    def attack_modes(self) -> list:
        """Get list of attack modes configured in this profile"""
        return self.config.get('attack_modes', [])
    
    @property
    def wordlists(self) -> list:
        """Get list of wordlists configured in this profile"""
        return self.config.get('wordlists', [])
    
    @property
    def rules(self) -> list:
        """Get list of rules configured in this profile"""
        return self.config.get('rules', [])
    
    @property
    def masks(self) -> list:
        """Get list of masks for mask attacks"""
        return self.config.get('masks', [])
    
    @property
    def has_dictionary_attacks(self) -> bool:
        """Check if profile includes dictionary attacks"""
        return 'dictionary' in self.attack_modes
    
    @property
    def has_brute_force_attacks(self) -> bool:
        """Check if profile includes brute force attacks"""
        return 'brute_force' in self.attack_modes or 'mask' in self.attack_modes
    
    @property
    def has_rule_based_attacks(self) -> bool:
        """Check if profile includes rule-based attacks"""
        return 'rule_based' in self.attack_modes and len(self.rules) > 0
    
    def get_hashcat_args(self, hash_type: str = None) -> list:
        """Generate hashcat command arguments based on profile config"""
        args = []
        
        # Add hash type if specified
        if hash_type:
            args.extend(['-m', str(hash_type)])
        
        # Add attack mode specific arguments
        attack_config = self.config.get('hashcat_args', {})
        
        for key, value in attack_config.items():
            if isinstance(value, bool) and value:
                args.append(f'--{key}')
            elif isinstance(value, (str, int)):
                args.extend([f'--{key}', str(value)])
            elif isinstance(value, list):
                for item in value:
                    args.extend([f'--{key}', str(item)])
        
        return args
    
    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate profile configuration"""
        required_fields = ['attack_modes']
        
        for field in required_fields:
            if field not in self.config:
                return False, f"Missing required field: {field}"
        
        if not isinstance(self.config['attack_modes'], list):
            return False, "attack_modes must be a list"
        
        if not self.config['attack_modes']:
            return False, "at least one attack mode must be specified"
        
        valid_modes = ['dictionary', 'brute_force', 'mask', 'rule_based', 'hybrid']
        for mode in self.config['attack_modes']:
            if mode not in valid_modes:
                return False, f"Invalid attack mode: {mode}. Valid modes: {valid_modes}"
        
        return True, None