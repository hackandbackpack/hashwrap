"""
Comprehensive error handling and recovery system for hashwrap.
Provides robust error recovery, retry logic, and graceful degradation.
"""

import sys
import time
import traceback
import os
import tempfile
from typing import Dict, Any, Optional, Callable, List, Type, Union
from dataclasses import dataclass
from enum import Enum
from contextlib import contextmanager
from functools import wraps

from .logger import get_logger


class ErrorSeverity(Enum):
    """Error severity levels."""
    RECOVERABLE = "recoverable"      # Can retry or continue
    DEGRADED = "degraded"           # Continue with reduced functionality
    CRITICAL = "critical"           # Must stop current operation
    FATAL = "fatal"                 # Must terminate application


class ErrorCategory(Enum):
    """Error categories for handling strategies."""
    FILE_ACCESS = "file_access"
    NETWORK = "network"
    PROCESS = "process"
    RESOURCE = "resource"
    VALIDATION = "validation"
    SECURITY = "security"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for error handling."""
    error: Exception
    severity: ErrorSeverity
    category: ErrorCategory
    operation: str
    retry_count: int = 0
    max_retries: int = 3
    context_data: Dict[str, Any] = None
    recovery_attempted: bool = False


class HashwrapError(Exception):
    """Base exception for hashwrap errors."""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.CRITICAL,
                 category: ErrorCategory = ErrorCategory.UNKNOWN,
                 context: Dict[str, Any] = None):
        super().__init__(message)
        self.severity = severity
        self.category = category
        self.context = context or {}


class FileAccessError(HashwrapError):
    """File access related errors."""
    
    def __init__(self, message: str, file_path: str = None, **kwargs):
        super().__init__(message, 
                        severity=ErrorSeverity.RECOVERABLE,
                        category=ErrorCategory.FILE_ACCESS,
                        context={'file_path': file_path, **kwargs})


class ProcessError(HashwrapError):
    """Process execution errors."""
    
    def __init__(self, message: str, process_name: str = None, 
                 return_code: int = None, **kwargs):
        super().__init__(message,
                        severity=ErrorSeverity.CRITICAL,
                        category=ErrorCategory.PROCESS,
                        context={'process_name': process_name, 
                                'return_code': return_code, **kwargs})


class ResourceError(HashwrapError):
    """Resource availability errors."""
    
    def __init__(self, message: str, resource_type: str = None, **kwargs):
        super().__init__(message,
                        severity=ErrorSeverity.DEGRADED,
                        category=ErrorCategory.RESOURCE,
                        context={'resource_type': resource_type, **kwargs})


class ValidationError(HashwrapError):
    """Input validation errors."""
    
    def __init__(self, message: str, field: str = None, value: Any = None, **kwargs):
        super().__init__(message,
                        severity=ErrorSeverity.CRITICAL,
                        category=ErrorCategory.VALIDATION,
                        context={'field': field, 'value': value, **kwargs})


class SecurityError(HashwrapError):
    """Security related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message,
                        severity=ErrorSeverity.FATAL,
                        category=ErrorCategory.SECURITY,
                        context=kwargs)


class ErrorHandler:
    """Comprehensive error handling and recovery system."""
    
    def __init__(self):
        self.logger = get_logger('error_handler')
        self.recovery_strategies = self._init_recovery_strategies()
        self.error_history: List[ErrorContext] = []
        self.error_callbacks: Dict[ErrorCategory, List[Callable]] = {}
        
    def _init_recovery_strategies(self) -> Dict[ErrorCategory, Callable]:
        """Initialize recovery strategies for different error categories."""
        return {
            ErrorCategory.FILE_ACCESS: self._recover_file_access,
            ErrorCategory.PROCESS: self._recover_process,
            ErrorCategory.RESOURCE: self._recover_resource,
            ErrorCategory.NETWORK: self._recover_network,
            ErrorCategory.VALIDATION: self._recover_validation,
            ErrorCategory.CONFIGURATION: self._recover_configuration
        }
    
    def handle_error(self, error: Exception, operation: str = "Unknown",
                    context_data: Dict[str, Any] = None) -> Optional[Any]:
        """
        Handle an error with appropriate recovery strategy.
        
        Args:
            error: The exception to handle
            operation: Description of the operation that failed
            context_data: Additional context information
            
        Returns:
            Recovery result if successful, None otherwise
        """
        # Create error context
        error_context = self._create_error_context(error, operation, context_data)
        
        # Log the error
        self._log_error(error_context)
        
        # Add to history
        self.error_history.append(error_context)
        
        # Trigger callbacks
        self._trigger_callbacks(error_context)
        
        # Attempt recovery based on severity
        if error_context.severity == ErrorSeverity.FATAL:
            self._handle_fatal_error(error_context)
            return None
            
        elif error_context.severity in [ErrorSeverity.RECOVERABLE, ErrorSeverity.DEGRADED]:
            return self._attempt_recovery(error_context)
            
        else:  # CRITICAL
            self._handle_critical_error(error_context)
            return None
    
    def _create_error_context(self, error: Exception, operation: str,
                            context_data: Dict[str, Any] = None) -> ErrorContext:
        """Create error context from exception."""
        # Determine severity and category
        if isinstance(error, HashwrapError):
            severity = error.severity
            category = error.category
            if error.context:
                context_data = {**(context_data or {}), **error.context}
        else:
            severity, category = self._classify_error(error)
        
        return ErrorContext(
            error=error,
            severity=severity,
            category=category,
            operation=operation,
            context_data=context_data or {}
        )
    
    def _classify_error(self, error: Exception) -> tuple[ErrorSeverity, ErrorCategory]:
        """Classify generic exceptions."""
        error_classifications = {
            FileNotFoundError: (ErrorSeverity.RECOVERABLE, ErrorCategory.FILE_ACCESS),
            PermissionError: (ErrorSeverity.CRITICAL, ErrorCategory.FILE_ACCESS),
            IOError: (ErrorSeverity.RECOVERABLE, ErrorCategory.FILE_ACCESS),
            OSError: (ErrorSeverity.CRITICAL, ErrorCategory.RESOURCE),
            MemoryError: (ErrorSeverity.FATAL, ErrorCategory.RESOURCE),
            KeyboardInterrupt: (ErrorSeverity.CRITICAL, ErrorCategory.PROCESS),
            SystemExit: (ErrorSeverity.FATAL, ErrorCategory.PROCESS),
            ValueError: (ErrorSeverity.CRITICAL, ErrorCategory.VALIDATION),
            TypeError: (ErrorSeverity.CRITICAL, ErrorCategory.VALIDATION),
            TimeoutError: (ErrorSeverity.RECOVERABLE, ErrorCategory.PROCESS),
            ConnectionError: (ErrorSeverity.RECOVERABLE, ErrorCategory.NETWORK)
        }
        
        for error_type, (severity, category) in error_classifications.items():
            if isinstance(error, error_type):
                return severity, category
        
        return ErrorSeverity.CRITICAL, ErrorCategory.UNKNOWN
    
    def _log_error(self, context: ErrorContext):
        """Log error with full context."""
        self.logger.error(
            f"Error in {context.operation}",
            error=context.error,
            severity=context.severity.value,
            category=context.category.value,
            retry_count=context.retry_count,
            **context.context_data
        )
    
    def _trigger_callbacks(self, context: ErrorContext):
        """Trigger registered error callbacks."""
        callbacks = self.error_callbacks.get(context.category, [])
        for callback in callbacks:
            try:
                callback(context)
            except Exception as e:
                self.logger.error("Error in callback", error=e)
    
    def _attempt_recovery(self, context: ErrorContext) -> Optional[Any]:
        """Attempt to recover from an error."""
        if context.recovery_attempted:
            self.logger.warning("Recovery already attempted, skipping")
            return None
        
        context.recovery_attempted = True
        
        # Get recovery strategy
        recovery_strategy = self.recovery_strategies.get(context.category)
        if not recovery_strategy:
            self.logger.warning(f"No recovery strategy for {context.category.value}")
            return None
        
        try:
            self.logger.info(f"Attempting recovery for {context.category.value} error")
            result = recovery_strategy(context)
            
            if result is not None:
                self.logger.info("Recovery successful")
            else:
                self.logger.warning("Recovery failed")
                
            return result
            
        except Exception as e:
            self.logger.error("Recovery strategy failed", error=e)
            return None
    
    def _recover_file_access(self, context: ErrorContext) -> Optional[Any]:
        """Recover from file access errors."""
        file_path = context.context_data.get('file_path')
        
        if isinstance(context.error, FileNotFoundError) or context.error.category == ErrorCategory.FILE_ACCESS:
            # Try alternative paths
            alternatives = context.context_data.get('alternatives', [])
            for alt_path in alternatives:
                if os.path.exists(alt_path):
                    self.logger.info(f"Using alternative path: {alt_path}")
                    return alt_path
            
            # Try creating parent directory
            if file_path and context.context_data.get('create_if_missing'):
                try:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    self.logger.info(f"Created parent directory for {file_path}")
                    return file_path
                except Exception as e:
                    self.logger.error("Failed to create directory", error=e)
        
        elif isinstance(context.error, PermissionError):
            # Try with elevated permissions or alternative location
            if file_path:
                # Try temp directory
                import tempfile
                temp_path = os.path.join(tempfile.gettempdir(), os.path.basename(file_path))
                self.logger.info(f"Using temporary path: {temp_path}")
                return temp_path
        
        return None
    
    def _recover_process(self, context: ErrorContext) -> Optional[Any]:
        """Recover from process errors."""
        if isinstance(context.error, TimeoutError):
            # Retry with increased timeout
            if context.retry_count < context.max_retries:
                new_timeout = context.context_data.get('timeout', 60) * 2
                self.logger.info(f"Retrying with timeout: {new_timeout}s")
                return {'retry': True, 'timeout': new_timeout}
        
        elif context.context_data.get('return_code') in [-9, -15]:
            # Process was killed, check for partial results
            partial_results = context.context_data.get('partial_results')
            if partial_results:
                self.logger.info("Using partial results from killed process")
                return {'partial': True, 'results': partial_results}
        
        return None
    
    def _recover_resource(self, context: ErrorContext) -> Optional[Any]:
        """Recover from resource errors."""
        resource_type = context.context_data.get('resource_type')
        
        if resource_type == 'memory':
            # Try to free memory
            import gc
            gc.collect()
            self.logger.info("Performed garbage collection")
            
            # Suggest reduced operation
            return {'reduce_batch_size': True, 'factor': 0.5}
            
        elif resource_type == 'gpu':
            # Fall back to CPU
            self.logger.info("Falling back to CPU mode")
            return {'use_cpu': True}
        
        elif resource_type == 'disk':
            # Clean up temporary files
            temp_dir = context.context_data.get('temp_dir', tempfile.gettempdir())
            self._cleanup_temp_files(temp_dir)
            return {'cleaned': True}
        
        return None
    
    def _recover_network(self, context: ErrorContext) -> Optional[Any]:
        """Recover from network errors."""
        if context.retry_count < context.max_retries:
            # Exponential backoff
            wait_time = 2 ** context.retry_count
            self.logger.info(f"Waiting {wait_time}s before retry")
            time.sleep(wait_time)
            return {'retry': True, 'wait_time': wait_time}
        
        # Try offline mode
        return {'offline_mode': True}
    
    def _recover_validation(self, context: ErrorContext) -> Optional[Any]:
        """Recover from validation errors."""
        field = context.context_data.get('field')
        value = context.context_data.get('value')
        
        # Try to sanitize/fix the value
        if field and value is not None:
            sanitized = self._sanitize_value(field, value)
            if sanitized != value:
                self.logger.info(f"Sanitized {field}: {value} -> {sanitized}")
                return {'sanitized': sanitized}
        
        # Suggest defaults
        defaults = context.context_data.get('defaults', {})
        if field in defaults:
            self.logger.info(f"Using default for {field}: {defaults[field]}")
            return {'default': defaults[field]}
        
        return None
    
    def _recover_configuration(self, context: ErrorContext) -> Optional[Any]:
        """Recover from configuration errors."""
        # Try to load default configuration
        default_config = context.context_data.get('default_config')
        if default_config:
            self.logger.info("Using default configuration")
            return default_config
        
        # Try to repair configuration
        config = context.context_data.get('config')
        if config:
            repaired = self._repair_config(config)
            if repaired != config:
                self.logger.info("Configuration repaired")
                return repaired
        
        return None
    
    def _handle_fatal_error(self, context: ErrorContext):
        """Handle fatal errors that require termination."""
        self.logger.critical(
            f"Fatal error in {context.operation}: {str(context.error)}",
            severity="FATAL",
            category=context.category.value
        )
        
        # Save crash report
        self._save_crash_report(context)
        
        # Perform emergency cleanup if possible
        cleanup_func = context.context_data.get('cleanup')
        if cleanup_func:
            try:
                cleanup_func()
            except Exception as e:
                self.logger.error("Cleanup failed", error=e)
        
        # Exit
        sys.exit(1)
    
    def _handle_critical_error(self, context: ErrorContext):
        """Handle critical errors that stop current operation."""
        self.logger.error(
            f"Critical error in {context.operation}",
            severity="CRITICAL",
            error_type=type(context.error).__name__
        )
        
        # Notify user
        notify_func = context.context_data.get('notify')
        if notify_func:
            notify_func(context)
    
    def _save_crash_report(self, context: ErrorContext):
        """Save crash report for debugging."""
        import json
        from datetime import datetime
        
        crash_report = {
            'timestamp': datetime.now().isoformat(),
            'operation': context.operation,
            'error_type': type(context.error).__name__,
            'error_message': str(context.error),
            'severity': context.severity.value,
            'category': context.category.value,
            'traceback': traceback.format_exc(),
            'context': context.context_data,
            'error_history': [
                {
                    'operation': ec.operation,
                    'error': str(ec.error),
                    'category': ec.category.value
                }
                for ec in self.error_history[-10:]  # Last 10 errors
            ]
        }
        
        try:
            crash_file = f"hashwrap_crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(crash_file, 'w') as f:
                json.dump(crash_report, f, indent=2)
            self.logger.info(f"Crash report saved to {crash_file}")
        except Exception as e:
            self.logger.error("Failed to save crash report", error=e)
    
    def _cleanup_temp_files(self, temp_dir: str):
        """Clean up temporary files."""
        import os
        import shutil
        
        try:
            # Remove hashwrap temp files
            for file in os.listdir(temp_dir):
                if file.startswith('hashwrap_'):
                    file_path = os.path.join(temp_dir, file)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception:
                        pass
            
            self.logger.info("Cleaned up temporary files")
        except Exception as e:
            self.logger.error("Temp cleanup failed", error=e)
    
    def _sanitize_value(self, field: str, value: Any) -> Any:
        """Sanitize a value based on field type."""
        # Example sanitization logic
        if 'path' in field:
            # Remove dangerous characters from paths
            if isinstance(value, str):
                return value.replace('..', '').replace('~', '')
        
        elif 'count' in field or 'size' in field:
            # Ensure positive integers
            try:
                return max(0, int(value))
            except:
                return 0
        
        return value
    
    def _repair_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to repair a configuration."""
        repaired = config.copy()
        
        # Add missing required fields
        required_fields = {
            'hash_file': 'hashes.txt',
            'potfile': 'hashcat.potfile',
            'mode': 'auto'
        }
        
        for field, default in required_fields.items():
            if field not in repaired:
                repaired[field] = default
        
        return repaired
    
    def register_callback(self, category: ErrorCategory, callback: Callable):
        """Register an error callback for a specific category."""
        if category not in self.error_callbacks:
            self.error_callbacks[category] = []
        self.error_callbacks[category].append(callback)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors encountered."""
        summary = {
            'total_errors': len(self.error_history),
            'by_severity': {},
            'by_category': {},
            'recent_errors': []
        }
        
        for error_context in self.error_history:
            # Count by severity
            severity = error_context.severity.value
            summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
            
            # Count by category
            category = error_context.category.value
            summary['by_category'][category] = summary['by_category'].get(category, 0) + 1
        
        # Recent errors
        for error_context in self.error_history[-5:]:
            summary['recent_errors'].append({
                'operation': error_context.operation,
                'error': str(error_context.error),
                'severity': error_context.severity.value,
                'category': error_context.category.value
            })
        
        return summary


# Decorators for easy error handling

def with_error_handling(operation: str = None, 
                       reraise: bool = True,
                       default_return: Any = None):
    """Decorator for automatic error handling."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = ErrorHandler()
            op_name = operation or func.__name__
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context_data = {
                    'function': func.__name__,
                    'args': args,
                    'kwargs': kwargs
                }
                
                result = error_handler.handle_error(e, op_name, context_data)
                
                if result and isinstance(result, dict) and result.get('retry'):
                    # Retry the operation
                    try:
                        return func(*args, **kwargs)
                    except Exception as retry_error:
                        if reraise:
                            raise
                        return default_return
                
                if reraise:
                    raise
                    
                return default_return
        
        return wrapper
    return decorator


@contextmanager
def error_context(operation: str, handler: ErrorHandler = None, **context_data):
    """Context manager for error handling."""
    handler = handler or ErrorHandler()
    
    try:
        yield handler
    except Exception as e:
        handler.handle_error(e, operation, context_data)
        raise


# Global error handler instance
_global_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    return _global_error_handler