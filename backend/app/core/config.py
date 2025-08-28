"""
Application configuration using Pydantic settings
"""

import secrets
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, BaseSettings, EmailStr, Field, validator


class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Basic app settings
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Security
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    JWT_SECRET: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    
    # CORS
    CORS_ORIGINS: List[AnyHttpUrl] = []
    ALLOWED_HOSTS: List[str] = ["*"]
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Database
    DATABASE_URL: str = "sqlite:///./hashwrap.db"
    
    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return "sqlite:///./hashwrap.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # File storage
    UPLOAD_DIR: str = "/data/uploads"
    RESULTS_DIR: str = "/data/results"
    WORDLISTS_DIR: str = "/wordlists"
    RULES_DIR: str = "/rules"
    
    # Upload limits
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    MAX_UPLOAD_LINES: int = 10_000_000  # 10M lines
    ALLOWED_EXTENSIONS: List[str] = [".txt", ".hash", ".lst", ".zip", ".gz"]
    
    # Job settings
    MAX_CONCURRENT_JOBS: int = 4
    DEFAULT_JOB_TIMEOUT: int = 86400  # 24 hours
    JOB_CLEANUP_INTERVAL: int = 3600  # 1 hour
    
    # GPU settings
    CUDA_VISIBLE_DEVICES: str = "0,1,2,3"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or human
    
    # Monitoring
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    
    # Legal/Compliance
    REQUIRE_LEGAL_BANNER: bool = True
    AUDIT_LOG_RETENTION_DAYS: int = 365
    DATA_RETENTION_DAYS: int = 90
    
    # Admin user (for initial setup)
    ADMIN_EMAIL: Optional[EmailStr] = None
    ADMIN_PASSWORD: Optional[str] = None
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 3600  # 1 hour
    
    # Session settings
    SESSION_COOKIE_NAME: str = "hashwrap_session"
    SESSION_COOKIE_DOMAIN: Optional[str] = None
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "lax"
    
    # TOTP settings
    TOTP_ISSUER: str = "HashWrap"
    TOTP_WINDOW: int = 2  # Allow 2 windows (±60 seconds)
    
    # Webhook settings
    WEBHOOK_TIMEOUT: int = 10
    WEBHOOK_RETRIES: int = 3
    WEBHOOK_RETRY_DELAY: int = 5
    
    # Background task settings
    DIRECTORY_SCAN_INTERVAL: int = 60  # seconds
    PROGRESS_UPDATE_INTERVAL: int = 30  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()