#!/usr/bin/env python3
"""
HashWrap Production Configuration
Security and performance settings for production deployment
"""

import os
from datetime import timedelta

class ProductionConfig:
    """Production configuration settings"""
    
    # Security
    SECRET_KEY = os.environ.get('HASHWRAP_SECRET_KEY') or 'please-change-this-in-production'
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    
    # Database
    DATABASE_PATH = '/opt/hashwrap/webapp/data/hashwrap.db'
    DATABASE_TIMEOUT = 30.0
    
    # File handling
    UPLOAD_FOLDER = '/opt/hashwrap/webapp/data/uploads'
    RESULTS_FOLDER = '/opt/hashwrap/webapp/data/results'
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB for large hash files
    MAX_LINES_PER_FILE = 10_000_000  # 10M lines max
    ALLOWED_EXTENSIONS = {'txt', 'hash', 'lst', 'json'}
    
    # Session management
    SESSION_TIMEOUT = timedelta(hours=4)  # Shorter timeout for security
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4)
    SESSION_COOKIE_SECURE = True  # HTTPS only
    SESSION_COOKIE_HTTPONLY = True  # No JavaScript access
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Job management
    MAX_CONCURRENT_JOBS = 2  # Conservative for production
    JOB_TIMEOUT_HOURS = 24  # Kill jobs after 24 hours
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = '/var/log/hashwrap/hashwrap.log'
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB per log file
    LOG_BACKUP_COUNT = 5
    
    # Performance
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(hours=1)
    TEMPLATES_AUTO_RELOAD = False
    
    # Security headers (handled by Apache in production)
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    }
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = 'memory://'
    RATELIMIT_DEFAULT = '100 per hour'
    LOGIN_RATE_LIMIT = '5 per minute'
    UPLOAD_RATE_LIMIT = '10 per minute'
    
    # System monitoring
    SYSTEM_CHECK_INTERVAL = 300  # 5 minutes
    DISK_SPACE_WARNING_THRESHOLD = 1024 * 1024 * 1024  # 1GB
    MEMORY_WARNING_THRESHOLD = 90  # 90% usage
    
    # Hashcat settings
    HASHCAT_BINARY = 'hashcat'
    WORDLIST_DIR = '/opt/hashwrap/webapp/wordlists'
    DEFAULT_WORDLIST = 'rockyou.txt'
    HASHCAT_WORKLOAD_PROFILE = 3  # High performance
    
    # Backup settings
    BACKUP_ENABLED = True
    BACKUP_INTERVAL_HOURS = 24
    BACKUP_RETENTION_DAYS = 7
    BACKUP_DIR = '/opt/hashwrap/backups'
    
    @staticmethod
    def init_app(app):
        """Initialize application with production settings"""
        
        # Configure logging
        import logging
        from logging.handlers import RotatingFileHandler
        
        # Ensure log directory exists
        log_dir = os.path.dirname(ProductionConfig.LOG_FILE)
        os.makedirs(log_dir, exist_ok=True)
        
        # Set up rotating file handler
        file_handler = RotatingFileHandler(
            ProductionConfig.LOG_FILE,
            maxBytes=ProductionConfig.LOG_MAX_BYTES,
            backupCount=ProductionConfig.LOG_BACKUP_COUNT
        )
        
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        ))
        
        file_handler.setLevel(getattr(logging, ProductionConfig.LOG_LEVEL))
        app.logger.addHandler(file_handler)
        app.logger.setLevel(getattr(logging, ProductionConfig.LOG_LEVEL))
        
        # Set Flask to production mode
        app.config['ENV'] = 'production'
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        
        # Apply configuration
        for key, value in ProductionConfig.__dict__.items():
            if not key.startswith('_') and key.isupper():
                app.config[key] = value
        
        app.logger.info("Production configuration applied")


class SecurityConfig:
    """Additional security hardening settings"""
    
    # Password policy (if user management is expanded)
    PASSWORD_MIN_LENGTH = 12
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_NUMBERS = True
    PASSWORD_REQUIRE_SPECIAL = True
    
    # Account lockout
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    LOCKOUT_INCREASE_FACTOR = 2  # Double lockout time for repeated failures
    
    # File upload security
    SCAN_UPLOADS = True  # Enable if antivirus is available
    QUARANTINE_SUSPICIOUS = True
    ALLOWED_MIME_TYPES = {
        'text/plain',
        'application/octet-stream',
        'text/x-python'  # For hash files that might be detected as code
    }
    
    # Network security
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'hashwrap.local']
    PROXY_TRUSTED_IPS = ['127.0.0.1']
    
    # Data retention
    JOB_RETENTION_DAYS = 30  # Delete old jobs after 30 days
    LOG_RETENTION_DAYS = 90  # Keep logs for 90 days
    RESULT_CLEANUP_ENABLED = True
    
    @staticmethod
    def validate_security_settings():
        """Validate security configuration"""
        issues = []
        
        # Check secret key
        if ProductionConfig.SECRET_KEY == 'please-change-this-in-production':
            issues.append("SECRET_KEY must be changed for production")
        
        # Check SSL configuration
        if not ProductionConfig.SESSION_COOKIE_SECURE:
            issues.append("SESSION_COOKIE_SECURE should be True in production")
        
        # Check file permissions
        sensitive_paths = [
            ProductionConfig.DATABASE_PATH,
            ProductionConfig.LOG_FILE,
            ProductionConfig.UPLOAD_FOLDER
        ]
        
        for path in sensitive_paths:
            if os.path.exists(path):
                stat_info = os.stat(path)
                if stat_info.st_mode & 0o077:  # Check if group/other have any permissions
                    issues.append(f"Insecure permissions on {path}")
        
        return issues


class MonitoringConfig:
    """System monitoring configuration"""
    
    # Health check endpoints
    HEALTH_CHECK_ENABLED = True
    HEALTH_CHECK_PATH = '/health'
    METRICS_PATH = '/metrics'
    
    # Alerting thresholds
    ALERTS = {
        'disk_space_low': {'threshold': 90, 'severity': 'warning'},
        'memory_high': {'threshold': 90, 'severity': 'warning'},
        'job_failure_rate': {'threshold': 50, 'severity': 'critical'},
        'login_failures': {'threshold': 10, 'severity': 'warning'}
    }
    
    # Metrics collection
    COLLECT_METRICS = True
    METRICS_INTERVAL = 60  # seconds
    METRICS_RETENTION_DAYS = 7


def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'production')
    
    if env == 'production':
        return ProductionConfig
    else:
        # Fallback to production config for security
        return ProductionConfig


# Configuration validation
def validate_production_setup():
    """Validate production configuration and environment"""
    issues = []
    warnings = []
    
    # Check environment
    if os.getuid() == 0:
        issues.append("Application should not run as root")
    
    # Check file system permissions
    critical_dirs = [
        '/opt/hashwrap/webapp',
        '/var/log/hashwrap'
    ]
    
    for directory in critical_dirs:
        if not os.path.exists(directory):
            issues.append(f"Critical directory missing: {directory}")
        elif not os.access(directory, os.W_OK):
            issues.append(f"No write access to: {directory}")
    
    # Check security settings
    security_issues = SecurityConfig.validate_security_settings()
    issues.extend(security_issues)
    
    # Check system resources
    try:
        import psutil
        
        # Memory check
        memory = psutil.virtual_memory()
        if memory.total < 2 * 1024 * 1024 * 1024:  # Less than 2GB
            warnings.append("System has less than 2GB RAM")
        
        # Disk check
        disk = psutil.disk_usage('/')
        if disk.free < 5 * 1024 * 1024 * 1024:  # Less than 5GB
            warnings.append("System has less than 5GB free disk space")
    
    except ImportError:
        warnings.append("psutil not available for system monitoring")
    
    return {
        'issues': issues,
        'warnings': warnings,
        'ready': len(issues) == 0
    }


if __name__ == "__main__":
    # Run configuration validation
    result = validate_production_setup()
    
    print("Production Configuration Validation")
    print("=" * 40)
    
    if result['issues']:
        print("❌ CRITICAL ISSUES:")
        for issue in result['issues']:
            print(f"  - {issue}")
    
    if result['warnings']:
        print("\n⚠️ WARNINGS:")
        for warning in result['warnings']:
            print(f"  - {warning}")
    
    if result['ready']:
        print("\n✅ Configuration is ready for production")
    else:
        print("\n❌ Configuration has critical issues - fix before deployment")
    
    exit(0 if result['ready'] else 1)