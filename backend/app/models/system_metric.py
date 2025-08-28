"""
SystemMetric model for performance monitoring and observability.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel, TimestampMixin


class SystemMetric(BaseModel, TimestampMixin):
    """System metric model for monitoring and observability"""
    
    __tablename__ = "system_metrics"
    
    # Metric identification
    metric_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Name of the metric being recorded"
    )
    
    # Metric value
    metric_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
        comment="Numeric value of the metric"
    )
    
    # Optional labels for metric dimensions
    labels: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Key-value labels for metric categorization and filtering"
    )
    
    
    # Indexes optimized for time-series queries
    __table_args__ = (
        # Primary time-series index
        Index("idx_metric_name_created", "metric_name", "created_at"),
        # For aggregations over time windows
        Index("idx_metric_created", "created_at"),
        # For filtering by metric name
        Index("idx_metric_name", "metric_name"),
        # For value-based queries (top N, thresholds)
        Index("idx_metric_name_value", "metric_name", "metric_value"),
    )
    
    def __repr__(self) -> str:
        return f"<SystemMetric(name={self.metric_name}, value={self.metric_value}, created_at={self.created_at})>"
    
    @classmethod
    def get_supported_metrics(cls) -> Dict[str, str]:
        """Get mapping of supported metric names to descriptions"""
        return {
            # System resources
            'system.cpu.usage': 'CPU usage percentage (0-100)',
            'system.memory.usage': 'Memory usage percentage (0-100)', 
            'system.disk.usage': 'Disk usage percentage (0-100)',
            'system.gpu.usage': 'GPU usage percentage (0-100)',
            'system.gpu.temperature': 'GPU temperature in Celsius',
            'system.load.average': 'System load average',
            
            # Application metrics
            'app.active_jobs': 'Number of currently running jobs',
            'app.queued_jobs': 'Number of jobs in queue',
            'app.active_users': 'Number of active user sessions',
            'app.total_projects': 'Total number of projects',
            'app.total_uploads': 'Total number of uploaded files',
            
            # Performance metrics  
            'hashcat.hashes_per_second': 'Hash cracking rate (H/s)',
            'hashcat.progress_percentage': 'Job completion percentage',
            'hashcat.runtime_seconds': 'Job runtime in seconds',
            'hashcat.cracked_hashes': 'Number of hashes cracked',
            
            # Database metrics
            'db.connection_pool.active': 'Active database connections',
            'db.connection_pool.idle': 'Idle database connections',
            'db.query.duration_ms': 'Database query duration in milliseconds',
            'db.table.size_mb': 'Database table size in megabytes',
            
            # HTTP metrics
            'http.requests.total': 'Total HTTP requests received',
            'http.requests.duration_ms': 'HTTP request duration in milliseconds',
            'http.response.status_2xx': 'Number of 2xx responses',
            'http.response.status_4xx': 'Number of 4xx responses',
            'http.response.status_5xx': 'Number of 5xx responses',
            
            # Business metrics
            'business.jobs.completed_per_hour': 'Jobs completed per hour',
            'business.hashes.cracked_per_hour': 'Hashes cracked per hour',
            'business.success_rate': 'Overall job success rate percentage',
            'business.average_crack_time': 'Average time to crack hashes (minutes)'
        }
    
    @property
    def metric_category(self) -> str:
        """Get the category of this metric based on its name"""
        if self.metric_name.startswith('system.'):
            return 'system'
        elif self.metric_name.startswith('app.'):
            return 'application'
        elif self.metric_name.startswith('hashcat.'):
            return 'hashcat'
        elif self.metric_name.startswith('db.'):
            return 'database'
        elif self.metric_name.startswith('http.'):
            return 'http'
        elif self.metric_name.startswith('business.'):
            return 'business'
        else:
            return 'unknown'
    
    @property
    def formatted_value(self) -> str:
        """Get formatted value based on metric type"""
        if 'percentage' in self.metric_name or 'usage' in self.metric_name:
            return f"{self.metric_value:.1f}%"
        elif 'duration_ms' in self.metric_name:
            return f"{self.metric_value:.0f}ms"
        elif 'temperature' in self.metric_name:
            return f"{self.metric_value:.1f}°C"
        elif 'per_second' in self.metric_name:
            return f"{self.metric_value:.0f}/s"
        elif 'size_mb' in self.metric_name:
            return f"{self.metric_value:.1f}MB"
        else:
            return f"{self.metric_value:.2f}"
    
    def get_label_value(self, label_key: str) -> Optional[str]:
        """Get value for a specific label key"""
        if not self.labels:
            return None
        return self.labels.get(label_key)
    
    def has_label(self, label_key: str, label_value: Optional[str] = None) -> bool:
        """Check if metric has a specific label, optionally with a specific value"""
        if not self.labels or label_key not in self.labels:
            return False
        
        if label_value is None:
            return True
        
        return self.labels[label_key] == label_value