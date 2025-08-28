"""
Resource management for preventing resource exhaustion attacks.
Provides thread pooling, rate limiting, and resource monitoring.
"""

import os
import sys
import time
import threading
import psutil
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Dict, Any, Optional, Callable, Union
from functools import wraps
from collections import deque
from datetime import datetime, timedelta

from .logger import get_logger


class ResourceLimits:
    """Configuration for resource limits."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        
        # Thread pool limits
        self.max_worker_threads = config.get('max_worker_threads', min(32, os.cpu_count() * 2))
        self.max_process_workers = config.get('max_process_workers', os.cpu_count())
        
        # Memory limits
        self.max_memory_percent = config.get('max_memory_percent', 75)  # Max 75% of system RAM
        self.max_memory_gb = config.get('max_memory_gb', 8)  # Max 8GB
        
        # File handle limits
        self.max_open_files = config.get('max_open_files', 1000)
        
        # Rate limiting
        self.max_requests_per_minute = config.get('max_requests_per_minute', 600)
        self.max_concurrent_operations = config.get('max_concurrent_operations', 10)
        
        # CPU limits
        self.max_cpu_percent = config.get('max_cpu_percent', 90)


class RateLimiter:
    """Token bucket rate limiter for preventing DoS."""
    
    def __init__(self, max_requests: int, time_window: timedelta):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = threading.Lock()
    
    def acquire(self) -> bool:
        """Try to acquire a token. Returns True if allowed, False if rate limited."""
        with self.lock:
            now = datetime.now()
            
            # Remove old requests outside the time window
            while self.requests and (now - self.requests[0]) > self.time_window:
                self.requests.popleft()
            
            # Check if we can make a new request
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            
            return False
    
    def wait_time(self) -> float:
        """Get seconds to wait before next request is allowed."""
        with self.lock:
            if not self.requests:
                return 0.0
            
            oldest_request = self.requests[0]
            wait_until = oldest_request + self.time_window
            wait_seconds = (wait_until - datetime.now()).total_seconds()
            
            return max(0.0, wait_seconds)


class ResourceMonitor:
    """Monitor system resources and enforce limits."""
    
    def __init__(self, limits: ResourceLimits):
        self.limits = limits
        self.logger = get_logger('resource_monitor')
        self._monitoring = False
        self._monitor_thread = None
        self._resource_alerts = deque(maxlen=100)
    
    def start_monitoring(self):
        """Start background resource monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop resource monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                # Check memory usage
                memory_percent = psutil.virtual_memory().percent
                if memory_percent > self.limits.max_memory_percent:
                    self._alert('memory', f"Memory usage at {memory_percent}%")
                
                # Check CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                if cpu_percent > self.limits.max_cpu_percent:
                    self._alert('cpu', f"CPU usage at {cpu_percent}%")
                
                # Check open file handles
                process = psutil.Process()
                open_files = len(process.open_files())
                if open_files > self.limits.max_open_files:
                    self._alert('files', f"Open files: {open_files}")
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error("Resource monitoring error", error=e)
                time.sleep(10)
    
    def _alert(self, resource_type: str, message: str):
        """Record resource alert."""
        alert = {
            'timestamp': datetime.now(),
            'type': resource_type,
            'message': message
        }
        self._resource_alerts.append(alert)
        self.logger.warning(f"Resource alert: {message}")
    
    def check_memory_available(self, required_mb: int) -> bool:
        """Check if enough memory is available."""
        available_mb = psutil.virtual_memory().available / (1024 * 1024)
        return available_mb >= required_mb
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage statistics."""
        memory = psutil.virtual_memory()
        cpu_freq = psutil.cpu_freq()
        
        return {
            'memory': {
                'percent': memory.percent,
                'used_gb': memory.used / (1024**3),
                'available_gb': memory.available / (1024**3)
            },
            'cpu': {
                'percent': psutil.cpu_percent(interval=0.1),
                'count': psutil.cpu_count(),
                'frequency_mhz': cpu_freq.current if cpu_freq else None
            },
            'process': {
                'memory_mb': psutil.Process().memory_info().rss / (1024**2),
                'threads': threading.active_count(),
                'open_files': len(psutil.Process().open_files())
            }
        }


class ManagedThreadPool:
    """Thread pool with resource management and monitoring."""
    
    def __init__(self, name: str, max_workers: int, limits: ResourceLimits):
        self.name = name
        self.max_workers = max_workers
        self.limits = limits
        self.logger = get_logger(f'thread_pool_{name}')
        
        # Create thread pool
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=f"hashwrap_{name}_"
        )
        
        # Tracking
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self._lock = threading.Lock()
        
        # Rate limiting
        self.rate_limiter = RateLimiter(
            limits.max_requests_per_minute,
            timedelta(minutes=1)
        )
    
    def submit(self, fn: Callable, *args, **kwargs):
        """Submit a task to the thread pool with rate limiting."""
        # Check rate limit
        if not self.rate_limiter.acquire():
            wait_time = self.rate_limiter.wait_time()
            raise RuntimeError(f"Rate limited. Try again in {wait_time:.1f} seconds")
        
        # Check concurrent operations limit
        with self._lock:
            if self.active_tasks >= self.limits.max_concurrent_operations:
                raise RuntimeError(f"Too many concurrent operations: {self.active_tasks}")
            self.active_tasks += 1
        
        # Wrap function to track completion
        def wrapped_fn():
            try:
                result = fn(*args, **kwargs)
                with self._lock:
                    self.completed_tasks += 1
                return result
            except Exception as e:
                with self._lock:
                    self.failed_tasks += 1
                raise
            finally:
                with self._lock:
                    self.active_tasks -= 1
        
        return self.executor.submit(wrapped_fn)
    
    def shutdown(self, wait: bool = True):
        """Shutdown the thread pool."""
        self.logger.info(f"Shutting down thread pool '{self.name}'",
                        completed=self.completed_tasks,
                        failed=self.failed_tasks)
        self.executor.shutdown(wait=wait)
    
    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics."""
        with self._lock:
            return {
                'active': self.active_tasks,
                'completed': self.completed_tasks,
                'failed': self.failed_tasks,
                'max_workers': self.max_workers
            }


class ResourceManager:
    """Central resource management for the application."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, config: Optional[Dict[str, Any]] = None):
        """Singleton pattern for resource manager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize resource manager."""
        if hasattr(self, '_initialized'):
            return
        
        self.config = config or {}
        self.limits = ResourceLimits(self.config)
        self.logger = get_logger('resource_manager')
        
        # Resource monitor
        self.monitor = ResourceMonitor(self.limits)
        self.monitor.start_monitoring()
        
        # Thread pools
        self._thread_pools: Dict[str, ManagedThreadPool] = {}
        
        # Global rate limiter
        self.global_rate_limiter = RateLimiter(
            self.limits.max_requests_per_minute * 2,  # Allow burst
            timedelta(minutes=1)
        )
        
        self._initialized = True
        self.logger.info("Resource manager initialized", limits=vars(self.limits))
    
    def get_thread_pool(self, name: str, max_workers: Optional[int] = None) -> ManagedThreadPool:
        """Get or create a named thread pool."""
        if name not in self._thread_pools:
            if max_workers is None:
                max_workers = self.limits.max_worker_threads
            
            self._thread_pools[name] = ManagedThreadPool(
                name, 
                min(max_workers, self.limits.max_worker_threads),
                self.limits
            )
            
            self.logger.info(f"Created thread pool '{name}'", max_workers=max_workers)
        
        return self._thread_pools[name]
    
    def check_resources(self, memory_mb: Optional[int] = None) -> bool:
        """Check if resources are available for an operation."""
        # Check memory if specified
        if memory_mb and not self.monitor.check_memory_available(memory_mb):
            self.logger.warning("Insufficient memory", required_mb=memory_mb)
            return False
        
        # Check global rate limit
        if not self.global_rate_limiter.acquire():
            self.logger.warning("Global rate limit exceeded")
            return False
        
        return True
    
    def with_resource_limit(self, memory_mb: Optional[int] = None):
        """Decorator to enforce resource limits on a function."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.check_resources(memory_mb):
                    raise RuntimeError("Insufficient resources available")
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def cleanup(self):
        """Clean up all resources."""
        self.logger.info("Cleaning up resource manager")
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        
        # Shutdown all thread pools
        for name, pool in self._thread_pools.items():
            pool.shutdown(wait=True)
        
        self._thread_pools.clear()
    
    def get_status(self) -> Dict[str, Any]:
        """Get overall resource status."""
        return {
            'resource_usage': self.monitor.get_resource_usage(),
            'thread_pools': {
                name: pool.get_stats() 
                for name, pool in self._thread_pools.items()
            },
            'limits': vars(self.limits)
        }


# Global resource manager instance
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager(config: Optional[Dict[str, Any]] = None) -> ResourceManager:
    """Get the global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager(config)
    return _resource_manager


def cleanup_resources():
    """Clean up global resources."""
    global _resource_manager
    if _resource_manager:
        _resource_manager.cleanup()
        _resource_manager = None