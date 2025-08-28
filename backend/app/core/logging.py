"""
Structured logging configuration
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.processors import JSONRenderer, TimeStamper


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structured logging for the application"""
    
    # Set log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        TimeStamper(fmt="iso"),
    ]
    
    if log_format == "json":
        processors.append(JSONRenderer())
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=JSONRenderer(),
            foreign_pre_chain=processors,
        )
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(colors=True)
        )
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=processors,
        )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    
    # Add formatter to root logger
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.handlers[0].setFormatter(formatter)
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_request_logger(request_id: str = None, user_id: str = None) -> Any:
    """Get logger with request context"""
    logger = structlog.get_logger()
    
    if request_id:
        logger = logger.bind(request_id=request_id)
    
    if user_id:
        logger = logger.bind(user_id=user_id)
    
    return logger


def log_security_event(
    event_type: str,
    user_id: str = None,
    ip_address: str = None,
    details: Dict[str, Any] = None
) -> None:
    """Log security-related events"""
    logger = structlog.get_logger("security")
    logger.warning(
        "Security event",
        event_type=event_type,
        user_id=user_id,
        ip_address=ip_address,
        details=details or {}
    )