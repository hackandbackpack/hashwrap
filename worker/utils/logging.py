"""
Logging utilities for worker tasks.
Provides structured logging with task context and performance tracking.
"""

import logging
import sys
from typing import Optional
from datetime import datetime

from celery import current_task
import structlog


def get_task_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger for a task with context.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured structured logger with task context
    """
    # Configure structlog if not already done
    if not structlog.is_configured():
        configure_structlog()
    
    logger = structlog.get_logger(name)
    
    # Add task context if available
    if current_task:
        logger = logger.bind(
            task_id=current_task.request.id if current_task.request else None,
            task_name=current_task.name if hasattr(current_task, 'name') else None,
            worker_id=current_task.request.hostname if current_task.request else None
        )
    
    return logger


def configure_structlog():
    """Configure structlog for worker processes."""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            add_task_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def add_task_context(logger, method_name, event_dict):
    """Add Celery task context to log entries."""
    if current_task and current_task.request:
        event_dict['task'] = {
            'id': current_task.request.id,
            'name': getattr(current_task, 'name', 'unknown'),
            'retries': current_task.request.retries,
            'eta': current_task.request.eta.isoformat() if current_task.request.eta else None,
        }
    
    return event_dict


class TaskPerformanceLogger:
    """Context manager for logging task performance metrics."""
    
    def __init__(self, logger: structlog.stdlib.BoundLogger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        self.logger.info(f"Starting {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        
        if exc_type is None:
            self.logger.info(
                f"Completed {self.operation}",
                duration_seconds=duration,
                status="success"
            )
        else:
            self.logger.error(
                f"Failed {self.operation}",
                duration_seconds=duration,
                status="error",
                error_type=exc_type.__name__ if exc_type else None,
                error_message=str(exc_val) if exc_val else None
            )


class ProgressLogger:
    """Helper for logging progress updates in long-running tasks."""
    
    def __init__(self, logger: structlog.stdlib.BoundLogger, total: int, 
                 update_interval: int = 100):
        self.logger = logger
        self.total = total
        self.update_interval = update_interval
        self.processed = 0
        self.last_update = 0
    
    def update(self, count: int = 1):
        """Update progress counter and log if interval reached."""
        self.processed += count
        
        if self.processed - self.last_update >= self.update_interval:
            self.log_progress()
            self.last_update = self.processed
    
    def log_progress(self):
        """Log current progress."""
        percentage = (self.processed / self.total) * 100 if self.total > 0 else 0
        
        self.logger.info(
            "Progress update",
            processed=self.processed,
            total=self.total,
            percentage=round(percentage, 2)
        )
        
        # Update Celery task state if available
        if current_task:
            current_task.update_state(
                state='PROGRESS',
                meta={
                    'current': self.processed,
                    'total': self.total,
                    'percentage': percentage
                }
            )
    
    def finish(self):
        """Log completion."""
        self.processed = self.total
        self.log_progress()
        
        self.logger.info(
            "Operation completed",
            total_processed=self.processed
        )


def log_task_error(logger: structlog.stdlib.BoundLogger, error: Exception, 
                   context: Optional[dict] = None):
    """Log task error with full context."""
    error_context = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'error_module': getattr(error, '__module__', None)
    }
    
    if context:
        error_context.update(context)
    
    logger.error(
        "Task error occurred",
        **error_context,
        exc_info=True
    )


def log_task_retry(logger: structlog.stdlib.BoundLogger, error: Exception, 
                   retry_count: int, max_retries: int):
    """Log task retry attempt."""
    logger.warning(
        "Task retry",
        error_type=type(error).__name__,
        error_message=str(error),
        retry_count=retry_count,
        max_retries=max_retries,
        retries_remaining=max_retries - retry_count
    )


class SecurityAuditLogger:
    """Logger for security-related events in worker tasks."""
    
    def __init__(self, logger: structlog.stdlib.BoundLogger):
        self.logger = logger.bind(category="security_audit")
    
    def log_file_access(self, file_path: str, operation: str, success: bool):
        """Log file access attempt."""
        self.logger.info(
            "File access",
            file_path=file_path,
            operation=operation,
            success=success,
            event_type="file_access"
        )
    
    def log_command_execution(self, command: str, success: bool, 
                            exit_code: Optional[int] = None):
        """Log command execution."""
        self.logger.info(
            "Command execution",
            command=command,
            success=success,
            exit_code=exit_code,
            event_type="command_execution"
        )
    
    def log_security_violation(self, violation_type: str, details: dict):
        """Log security violation."""
        self.logger.warning(
            "Security violation detected",
            violation_type=violation_type,
            details=details,
            event_type="security_violation"
        )


# Initialize structlog configuration when module is imported
if not structlog.is_configured():
    configure_structlog()