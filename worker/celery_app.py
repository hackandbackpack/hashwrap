"""
Celery application configuration for HashWrap workers.
Handles task distribution, monitoring, and Redis broker connectivity.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.core.config import get_settings


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    settings = get_settings()
    
    # Create Celery instance
    celery_app = Celery(
        "hashwrap_worker",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
        include=[
            'worker.tasks.job_tasks',
            'worker.tasks.monitoring_tasks',
            'worker.tasks.cleanup_tasks',
            'worker.tasks.directory_watcher'
        ]
    )
    
    # Configure Celery settings
    celery_app.conf.update(
        # Task routing configuration
        task_routes={
            'worker.tasks.job_tasks.execute_hashcat_job': {'queue': 'hashcat'},
            'worker.tasks.job_tasks.pause_job': {'queue': 'control'},
            'worker.tasks.job_tasks.resume_job': {'queue': 'control'},
            'worker.tasks.job_tasks.cancel_job': {'queue': 'control'},
            'worker.tasks.monitoring_tasks.update_job_progress': {'queue': 'monitoring'},
            'worker.tasks.monitoring_tasks.collect_system_metrics': {'queue': 'monitoring'},
            'worker.tasks.cleanup_tasks.cleanup_old_files': {'queue': 'maintenance'},
            'worker.tasks.directory_watcher.scan_upload_directory': {'queue': 'watcher'},
        },
        
        # Queue configuration
        task_default_queue='default',
        task_queues=(
            Queue('default', Exchange('default'), routing_key='default'),
            Queue('hashcat', Exchange('hashcat'), routing_key='hashcat'),
            Queue('control', Exchange('control'), routing_key='control'),
            Queue('monitoring', Exchange('monitoring'), routing_key='monitoring'),
            Queue('maintenance', Exchange('maintenance'), routing_key='maintenance'),
            Queue('watcher', Exchange('watcher'), routing_key='watcher'),
        ),
        
        # Worker configuration
        worker_prefetch_multiplier=1,  # Only fetch one task at a time for long-running jobs
        worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
        worker_disable_rate_limits=True,
        
        # Task execution settings
        task_serializer='json',
        result_serializer='json',
        accept_content=['json'],
        result_expires=3600,  # Results expire after 1 hour
        timezone='UTC',
        enable_utc=True,
        
        # Task time limits
        task_soft_time_limit=300,  # 5 minutes soft limit for most tasks
        task_time_limit=600,  # 10 minutes hard limit for most tasks
        
        # Long-running job tasks get special treatment
        task_annotations={
            'worker.tasks.job_tasks.execute_hashcat_job': {
                'time_limit': None,  # No time limit for hashcat jobs
                'soft_time_limit': None,
                'acks_late': True,  # Acknowledge after completion
                'reject_on_worker_lost': True,
            },
            'worker.tasks.directory_watcher.scan_upload_directory': {
                'time_limit': 300,
                'soft_time_limit': 240,
            }
        },
        
        # Beat schedule for periodic tasks
        beat_schedule={
            'scan-upload-directory': {
                'task': 'worker.tasks.directory_watcher.scan_upload_directory',
                'schedule': timedelta(seconds=settings.DIRECTORY_SCAN_INTERVAL),
                'options': {'queue': 'watcher'}
            },
            'collect-system-metrics': {
                'task': 'worker.tasks.monitoring_tasks.collect_system_metrics',
                'schedule': timedelta(seconds=30),
                'options': {'queue': 'monitoring'}
            },
            'cleanup-old-files': {
                'task': 'worker.tasks.cleanup_tasks.cleanup_old_files',
                'schedule': crontab(minute=0, hour=2),  # Daily at 2 AM
                'options': {'queue': 'maintenance'}
            },
            'update-job-progress': {
                'task': 'worker.tasks.monitoring_tasks.update_all_jobs_progress',
                'schedule': timedelta(seconds=settings.PROGRESS_UPDATE_INTERVAL),
                'options': {'queue': 'monitoring'}
            }
        },
        
        # Result backend settings
        result_backend_transport_options={
            'master_name': 'hashwrap',
            'visibility_timeout': 3600,
            'retry_policy': {
                'timeout': 5.0
            }
        },
        
        # Broker settings
        broker_transport_options={
            'master_name': 'hashwrap',
            'visibility_timeout': 3600,
            'fanout_prefix': True,
            'fanout_patterns': True
        },
        
        # Error handling
        task_reject_on_worker_lost=True,
        task_acks_late=True,
        
        # Monitoring
        worker_send_task_events=True,
        task_send_sent_event=True,
        
        # Security
        worker_hijack_root_logger=False,
        worker_log_color=False,
        
        # Performance tuning
        broker_pool_limit=10,
        broker_connection_retry_on_startup=True,
        broker_connection_retry=True,
        broker_connection_max_retries=None,
        
        # Custom settings for HashWrap
        hashwrap_settings={
            'max_concurrent_jobs': settings.MAX_CONCURRENT_JOBS,
            'upload_dir': settings.UPLOAD_DIR,
            'results_dir': settings.RESULTS_DIR,
            'wordlists_dir': settings.WORDLISTS_DIR,
            'rules_dir': settings.RULES_DIR,
        }
    )
    
    return celery_app


# Create the Celery app instance
celery = create_celery_app()


class CeleryConfig:
    """Celery configuration class for external use."""
    
    @staticmethod
    def get_active_queues():
        """Get list of active queue names."""
        return ['default', 'hashcat', 'control', 'monitoring', 'maintenance', 'watcher']
    
    @staticmethod
    def get_queue_info():
        """Get detailed queue configuration information."""
        return {
            'default': {
                'description': 'Default queue for general tasks',
                'concurrency': 4,
                'prefetch': 1
            },
            'hashcat': {
                'description': 'Long-running hashcat job execution',
                'concurrency': 2,  # Limit concurrent hashcat jobs
                'prefetch': 1
            },
            'control': {
                'description': 'Job control operations (pause, resume, cancel)',
                'concurrency': 10,
                'prefetch': 4
            },
            'monitoring': {
                'description': 'Progress updates and metrics collection',
                'concurrency': 4,
                'prefetch': 2
            },
            'maintenance': {
                'description': 'System maintenance and cleanup',
                'concurrency': 2,
                'prefetch': 1
            },
            'watcher': {
                'description': 'Directory monitoring and file processing',
                'concurrency': 2,
                'prefetch': 1
            }
        }
    
    @staticmethod
    def get_recommended_worker_command(queue_name: str = None) -> str:
        """Get recommended worker startup command."""
        base_cmd = "celery -A worker.celery_app worker"
        
        if queue_name:
            queue_info = CeleryConfig.get_queue_info()
            if queue_name in queue_info:
                info = queue_info[queue_name]
                return f"{base_cmd} -Q {queue_name} --concurrency={info['concurrency']} --prefetch-multiplier={info['prefetch']}"
        
        return f"{base_cmd} --concurrency=4 --prefetch-multiplier=1"


if __name__ == "__main__":
    # Allow running this module for testing
    print("HashWrap Celery Configuration")
    print(f"Broker URL: {celery.conf.broker_url}")
    print(f"Result Backend: {celery.conf.result_backend}")
    print("\nActive Queues:")
    for queue, info in CeleryConfig.get_queue_info().items():
        print(f"  {queue}: {info['description']}")
    
    print("\nRecommended worker commands:")
    for queue in CeleryConfig.get_active_queues():
        print(f"  {CeleryConfig.get_recommended_worker_command(queue)}")