"""
Structured logging system for hashwrap operations.
Provides comprehensive logging with context, performance tracking, and debugging support.
"""

import logging
import logging.handlers
import json
import traceback
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union
from functools import wraps
import threading


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured log messages."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured output."""
        # Base log structure
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': threading.current_thread().name,
            'thread_id': threading.get_ident()
        }
        
        # Add extra fields if present
        if hasattr(record, 'context') and record.context:
            # Merge context fields into log_data
            log_data.update(record.context)
            
        if hasattr(record, 'performance'):
            log_data['performance'] = record.performance
            
        if hasattr(record, 'error_details'):
            log_data['error_details'] = record.error_details
            
        # Include exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format with colors for console."""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # Build message
        msg = f"{color}[{timestamp} {record.levelname:8}]{reset} {record.name}: {record.getMessage()}"
        
        # Add context if present
        if hasattr(record, 'context') and record.context:
            context_str = " | ".join(f"{k}={v}" for k, v in record.context.items())
            msg += f" | {context_str}"
            
        # Add exception if present
        if record.exc_info:
            msg += f"\n{color}{''.join(traceback.format_exception(*record.exc_info))}{reset}"
            
        return msg


class LoggerWrapper:
    """Wrapper around Python logger to support context parameters."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def _log_with_context(self, level: str, message: str, **context):
        """Log with context support."""
        extra = {'context': context} if context else {}
        getattr(self.logger, level)(message, extra=extra)
    
    def debug(self, message: str, **context):
        self._log_with_context('debug', message, **context)
    
    def info(self, message: str, **context):
        self._log_with_context('info', message, **context)
    
    def warning(self, message: str, **context):
        self._log_with_context('warning', message, **context)
    
    def error(self, message: str, error: Optional[Exception] = None, **context):
        extra = {'context': context}
        if error:
            extra['error_details'] = {
                'type': type(error).__name__,
                'message': str(error)
            }
        self.logger.error(message, exc_info=error, extra=extra)
    
    def critical(self, message: str, error: Optional[Exception] = None, **context):
        extra = {'context': context}
        if error:
            extra['error_details'] = {
                'type': type(error).__name__,
                'message': str(error)
            }
        self.logger.critical(message, exc_info=error, extra=extra)


class HashwrapLogger:
    """Main logger class for hashwrap with structured logging support."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure single logger instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the logger system."""
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self.logger = logging.getLogger('hashwrap')
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Performance tracking
        self._operation_starts = {}
        
    def setup(self, log_level: str = 'INFO', log_file: Optional[str] = None,
              console: bool = True, json_format: bool = False) -> None:
        """
        Setup logging configuration.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to log file (optional)
            console: Enable console output
            json_format: Use JSON format for file logs
        """
        # Set log level
        level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        if console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(ConsoleFormatter())
            console_handler.setLevel(level)
            self.logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            # Create log directory if needed
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Rotating file handler (10MB max, keep 5 backups)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            
            # Use JSON or human-readable format
            if json_format:
                file_handler.setFormatter(StructuredFormatter())
            else:
                file_handler.setFormatter(logging.Formatter(
                    '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s'
                ))
            
            file_handler.setLevel(level)
            self.logger.addHandler(file_handler)
    
    def get_logger(self, name: str) -> 'LoggerWrapper':
        """Get a named logger instance."""
        return LoggerWrapper(logging.getLogger(f'hashwrap.{name}'))
    
    def log(self, level: str, message: str, **context) -> None:
        """
        Log a message with optional context.
        
        Args:
            level: Log level
            message: Log message
            **context: Additional context as key-value pairs
        """
        log_method = getattr(self.logger, level.lower())
        extra = {'context': context} if context else {}
        log_method(message, extra=extra)
    
    def debug(self, message: str, **context) -> None:
        """Log debug message."""
        self.log('debug', message, **context)
    
    def info(self, message: str, **context) -> None:
        """Log info message."""
        self.log('info', message, **context)
    
    def warning(self, message: str, **context) -> None:
        """Log warning message."""
        self.log('warning', message, **context)
    
    def error(self, message: str, error: Optional[Exception] = None, **context) -> None:
        """Log error message with optional exception."""
        extra = {'context': context}
        
        if error:
            extra['error_details'] = {
                'type': type(error).__name__,
                'message': str(error),
                'args': error.args
            }
            
        self.logger.error(message, exc_info=error, extra=extra)
    
    def critical(self, message: str, error: Optional[Exception] = None, **context) -> None:
        """Log critical message."""
        extra = {'context': context}
        
        if error:
            extra['error_details'] = {
                'type': type(error).__name__,
                'message': str(error)
            }
            
        self.logger.critical(message, exc_info=error, extra=extra)
    
    def start_operation(self, operation_id: str, operation_type: str, **details) -> None:
        """
        Start tracking an operation for performance monitoring.
        
        Args:
            operation_id: Unique identifier for the operation
            operation_type: Type of operation (e.g., 'attack', 'hash_load')
            **details: Additional operation details
        """
        self._operation_starts[operation_id] = {
            'start_time': time.time(),
            'type': operation_type,
            'details': details
        }
        
        self.info(f"Started {operation_type}", 
                 operation_id=operation_id,
                 operation_type=operation_type,
                 **details)
    
    def end_operation(self, operation_id: str, success: bool = True, **results) -> None:
        """
        End tracking an operation and log performance metrics.
        
        Args:
            operation_id: Operation identifier
            success: Whether operation succeeded
            **results: Operation results
        """
        if operation_id not in self._operation_starts:
            self.warning(f"Unknown operation ended: {operation_id}")
            return
            
        start_info = self._operation_starts.pop(operation_id)
        duration = time.time() - start_info['start_time']
        
        performance_data = {
            'duration_seconds': round(duration, 3),
            'success': success
        }
        
        self.info(
            f"Completed {start_info['type']}",
            operation_id=operation_id,
            operation_type=start_info['type'],
            performance=performance_data,
            **results
        )
    
    def log_attack(self, attack_name: str, status: str, **details) -> None:
        """Log attack-specific information."""
        self.info(
            f"Attack {attack_name}: {status}",
            attack_name=attack_name,
            status=status,
            **details
        )
    
    def log_hash_operation(self, operation: str, count: int, **details) -> None:
        """Log hash-related operations."""
        self.info(
            f"Hash operation: {operation}",
            operation=operation,
            count=count,
            **details
        )
    
    def log_session(self, session_id: str, action: str, **details) -> None:
        """Log session-related events."""
        self.info(
            f"Session {action}",
            session_id=session_id,
            action=action,
            **details
        )


def log_performance(operation_type: str = "function"):
    """
    Decorator to automatically log function performance.
    
    Args:
        operation_type: Type of operation being measured
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = HashwrapLogger()
            operation_id = f"{func.__name__}_{id(args)}_{time.time()}"
            
            # Start timing
            logger.start_operation(
                operation_id,
                operation_type,
                function=func.__name__,
                module=func.__module__
            )
            
            try:
                result = func(*args, **kwargs)
                logger.end_operation(operation_id, success=True)
                return result
                
            except Exception as e:
                logger.end_operation(
                    operation_id,
                    success=False,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise
                
        return wrapper
    return decorator


# Convenience functions for module-level logging
_logger_instance = HashwrapLogger()

def setup_logging(**kwargs):
    """Setup logging configuration."""
    _logger_instance.setup(**kwargs)

def get_logger(name: str) -> LoggerWrapper:
    """Get a named logger."""
    return _logger_instance.get_logger(name)

def debug(message: str, **context):
    """Log debug message."""
    _logger_instance.debug(message, **context)

def info(message: str, **context):
    """Log info message."""
    _logger_instance.info(message, **context)

def warning(message: str, **context):
    """Log warning message."""
    _logger_instance.warning(message, **context)

def error(message: str, error: Optional[Exception] = None, **context):
    """Log error message."""
    _logger_instance.error(message, error, **context)

def critical(message: str, error: Optional[Exception] = None, **context):
    """Log critical message."""
    _logger_instance.critical(message, error, **context)