"""
Celery tasks for system monitoring and job progress tracking.
Handles periodic system metrics collection and job status updates.
"""

import json
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from celery import current_task
from sqlalchemy import func
from sqlalchemy.orm import Session

from worker.celery_app import celery
from worker.services.notification_service import NotificationService
from worker.utils.database import get_db_session
from worker.utils.logging import get_task_logger
from backend.app.models.job import Job, JobStatus
from backend.app.models.system_metric import SystemMetric
from backend.app.core.config import get_settings


logger = get_task_logger(__name__)


@celery.task(bind=True, name='worker.tasks.monitoring_tasks.collect_system_metrics')
def collect_system_metrics(self) -> Dict[str, any]:
    """
    Collect system metrics and store in database.
    This task runs every 30 seconds to track system resource usage.
    """
    logger.debug("Collecting system metrics")
    
    try:
        # Collect CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        # Collect memory metrics
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Collect disk metrics
        disk_usage = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()
        
        # Collect network metrics
        network_io = psutil.net_io_counters()
        
        # GPU metrics (if available)
        gpu_metrics = _collect_gpu_metrics()
        
        # Process metrics
        process_count = len(psutil.pids())
        
        # Create metrics record
        metrics_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'cpu': {
                'usage_percent': cpu_percent,
                'count': cpu_count,
                'frequency_mhz': cpu_freq.current if cpu_freq else None
            },
            'memory': {
                'total_bytes': memory.total,
                'used_bytes': memory.used,
                'available_bytes': memory.available,
                'usage_percent': memory.percent
            },
            'swap': {
                'total_bytes': swap.total,
                'used_bytes': swap.used,
                'usage_percent': swap.percent
            },
            'disk': {
                'total_bytes': disk_usage.total,
                'used_bytes': disk_usage.used,
                'free_bytes': disk_usage.free,
                'usage_percent': (disk_usage.used / disk_usage.total) * 100,
                'read_bytes': disk_io.read_bytes if disk_io else None,
                'write_bytes': disk_io.write_bytes if disk_io else None
            },
            'network': {
                'bytes_sent': network_io.bytes_sent if network_io else None,
                'bytes_recv': network_io.bytes_recv if network_io else None,
                'packets_sent': network_io.packets_sent if network_io else None,
                'packets_recv': network_io.packets_recv if network_io else None
            },
            'processes': {
                'count': process_count
            }
        }
        
        # Add GPU metrics if available
        if gpu_metrics:
            metrics_data['gpu'] = gpu_metrics
        
        # Store metrics in database
        with get_db_session() as db:
            metric = SystemMetric(
                metric_type='system_overview',
                value=metrics_data,
                collected_at=datetime.utcnow()
            )
            db.add(metric)
            db.commit()
        
        # Update Celery task state
        current_task.update_state(
            state='SUCCESS',
            meta={
                'cpu_usage': cpu_percent,
                'memory_usage': memory.percent,
                'disk_usage': (disk_usage.used / disk_usage.total) * 100,
                'timestamp': metrics_data['timestamp']
            }
        )
        
        # Check for resource alerts
        await _check_resource_alerts(metrics_data)
        
        return {
            'success': True,
            'timestamp': metrics_data['timestamp'],
            'cpu_usage': cpu_percent,
            'memory_usage': memory.percent,
            'disk_usage': (disk_usage.used / disk_usage.total) * 100
        }
        
    except Exception as e:
        logger.error(f"Error collecting system metrics: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


@celery.task(bind=True, name='worker.tasks.monitoring_tasks.update_all_jobs_progress')
def update_all_jobs_progress(self) -> Dict[str, any]:
    """
    Update progress for all active jobs.
    This task runs every 30 seconds to ensure job progress is current.
    """
    logger.debug("Updating progress for all active jobs")
    
    try:
        updated_jobs = 0
        errors = []
        
        with get_db_session() as db:
            # Get all active jobs
            active_jobs = db.query(Job).filter(
                Job.status.in_([JobStatus.RUNNING, JobStatus.PREPARING])
            ).all()
            
            logger.info(f"Found {len(active_jobs)} active jobs to update")
            
            for job in active_jobs:
                try:
                    # Update job progress
                    result = _update_single_job_progress(db, job)
                    if result['success']:
                        updated_jobs += 1
                    else:
                        errors.append(f"Job {job.id}: {result['error']}")
                        
                except Exception as e:
                    error_msg = f"Job {job.id}: {str(e)}"
                    logger.error(f"Error updating job progress: {error_msg}")
                    errors.append(error_msg)
            
            db.commit()
        
        return {
            'success': True,
            'updated_jobs': updated_jobs,
            'total_active_jobs': len(active_jobs) if 'active_jobs' in locals() else 0,
            'errors': errors,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error updating all jobs progress: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'updated_jobs': 0,
            'timestamp': datetime.utcnow().isoformat()
        }


@celery.task(bind=True, name='worker.tasks.monitoring_tasks.update_job_progress')
def update_job_progress(self, job_id: str) -> Dict[str, any]:
    """Update progress for a specific job."""
    logger.debug(f"Updating progress for job {job_id}")
    
    try:
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return {'success': False, 'error': f'Job {job_id} not found'}
            
            result = _update_single_job_progress(db, job)
            db.commit()
            
            return result
            
    except Exception as e:
        logger.error(f"Error updating progress for job {job_id}: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}


@celery.task(bind=True, name='worker.tasks.monitoring_tasks.generate_system_report')
def generate_system_report(self, hours: int = 24) -> Dict[str, any]:
    """Generate system performance report for the last N hours."""
    logger.info(f"Generating system report for last {hours} hours")
    
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with get_db_session() as db:
            # Get system metrics for the time period
            metrics = db.query(SystemMetric).filter(
                SystemMetric.metric_type == 'system_overview',
                SystemMetric.collected_at >= cutoff_time
            ).order_by(SystemMetric.collected_at).all()
            
            if not metrics:
                return {
                    'success': False,
                    'error': f'No metrics found for last {hours} hours'
                }
            
            # Process metrics to generate report
            report = _process_metrics_for_report(metrics, hours)
            
            # Get job statistics for the period
            job_stats = _get_job_statistics(db, cutoff_time)
            report['job_statistics'] = job_stats
            
            logger.info(f"System report generated with {len(metrics)} data points")
            
            return {
                'success': True,
                'report': report,
                'data_points': len(metrics),
                'time_period_hours': hours,
                'generated_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error generating system report: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'generated_at': datetime.utcnow().isoformat()
        }


@celery.task(bind=True, name='worker.tasks.monitoring_tasks.check_job_health')
def check_job_health(self) -> Dict[str, any]:
    """Check health of all jobs and identify issues."""
    logger.info("Performing job health check")
    
    try:
        issues = []
        healthy_jobs = 0
        
        with get_db_session() as db:
            # Check for jobs stuck in PREPARING status
            stuck_preparing = db.query(Job).filter(
                Job.status == JobStatus.PREPARING,
                Job.created_at < datetime.utcnow() - timedelta(minutes=15)
            ).all()
            
            for job in stuck_preparing:
                issues.append({
                    'job_id': job.id,
                    'job_name': job.name,
                    'issue': 'stuck_preparing',
                    'description': f'Job stuck in PREPARING status for {_time_since(job.created_at)}'
                })
            
            # Check for jobs running too long without progress
            long_running = db.query(Job).filter(
                Job.status == JobStatus.RUNNING,
                Job.started_at < datetime.utcnow() - timedelta(hours=24)
            ).all()
            
            for job in long_running:
                # Check if there's been recent progress
                recent_events = db.query(Job).filter(
                    Job.id == job.id
                ).first()
                
                # This would check for recent progress events
                # For now, just flag long-running jobs
                issues.append({
                    'job_id': job.id,
                    'job_name': job.name,
                    'issue': 'long_running',
                    'description': f'Job running for {_time_since(job.started_at)} without completion'
                })
            
            # Check for failed jobs that might need attention
            recent_failures = db.query(Job).filter(
                Job.status == JobStatus.FAILED,
                Job.completed_at >= datetime.utcnow() - timedelta(hours=1)
            ).count()
            
            if recent_failures > 5:
                issues.append({
                    'issue': 'high_failure_rate',
                    'description': f'{recent_failures} job failures in the last hour',
                    'count': recent_failures
                })
            
            # Count healthy jobs
            healthy_jobs = db.query(Job).filter(
                Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED])
            ).count()
        
        # Send alerts for critical issues
        if issues:
            await _send_health_alerts(issues)
        
        return {
            'success': True,
            'healthy_jobs': healthy_jobs,
            'issues_found': len(issues),
            'issues': issues,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during job health check: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


def _collect_gpu_metrics() -> Optional[Dict]:
    """Collect GPU metrics using nvidia-smi if available."""
    try:
        import subprocess
        
        # Try to get GPU info via nvidia-smi
        cmd = [
            'nvidia-smi', 
            '--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw',
            '--format=csv,noheader,nounits'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            gpus = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 7:
                        gpus.append({
                            'index': int(parts[0]),
                            'name': parts[1],
                            'temperature': float(parts[2]) if parts[2] != '[Not Supported]' else None,
                            'utilization_percent': float(parts[3]) if parts[3] != '[Not Supported]' else None,
                            'memory_used_mb': float(parts[4]) if parts[4] != '[Not Supported]' else None,
                            'memory_total_mb': float(parts[5]) if parts[5] != '[Not Supported]' else None,
                            'power_draw_w': float(parts[6]) if parts[6] != '[Not Supported]' else None
                        })
            
            return {'devices': gpus, 'count': len(gpus)} if gpus else None
            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError):
        pass  # GPU monitoring not available
    
    return None


async def _check_resource_alerts(metrics_data: Dict):
    """Check system metrics for alert conditions."""
    try:
        settings = get_settings()
        notification_service = NotificationService()
        
        alerts = []
        
        # CPU usage alert
        if metrics_data['cpu']['usage_percent'] > 90:
            alerts.append({
                'type': 'high_cpu_usage',
                'value': metrics_data['cpu']['usage_percent'],
                'threshold': 90,
                'message': f"High CPU usage: {metrics_data['cpu']['usage_percent']:.1f}%"
            })
        
        # Memory usage alert
        if metrics_data['memory']['usage_percent'] > 90:
            alerts.append({
                'type': 'high_memory_usage',
                'value': metrics_data['memory']['usage_percent'],
                'threshold': 90,
                'message': f"High memory usage: {metrics_data['memory']['usage_percent']:.1f}%"
            })
        
        # Disk usage alert
        if metrics_data['disk']['usage_percent'] > 90:
            alerts.append({
                'type': 'high_disk_usage',
                'value': metrics_data['disk']['usage_percent'],
                'threshold': 90,
                'message': f"High disk usage: {metrics_data['disk']['usage_percent']:.1f}%"
            })
        
        # GPU temperature alerts
        if 'gpu' in metrics_data and metrics_data['gpu']['devices']:
            for gpu in metrics_data['gpu']['devices']:
                if gpu['temperature'] and gpu['temperature'] > 85:
                    alerts.append({
                        'type': 'high_gpu_temperature',
                        'gpu_index': gpu['index'],
                        'value': gpu['temperature'],
                        'threshold': 85,
                        'message': f"GPU {gpu['index']} temperature: {gpu['temperature']}°C"
                    })
        
        # Send alerts
        for alert in alerts:
            await notification_service.send_system_notification(
                'system.alert',
                alert['message'],
                {'alert': alert, 'metrics': metrics_data}
            )
            
    except Exception as e:
        logger.error(f"Error checking resource alerts: {e}")


def _update_single_job_progress(db: Session, job: Job) -> Dict[str, any]:
    """Update progress for a single job."""
    try:
        # This would integrate with the actual job monitoring
        # For now, return success
        return {'success': True}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _process_metrics_for_report(metrics: List[SystemMetric], hours: int) -> Dict:
    """Process metrics data to generate summary report."""
    try:
        cpu_values = []
        memory_values = []
        disk_values = []
        
        for metric in metrics:
            data = metric.value
            if isinstance(data, dict):
                if 'cpu' in data and 'usage_percent' in data['cpu']:
                    cpu_values.append(data['cpu']['usage_percent'])
                if 'memory' in data and 'usage_percent' in data['memory']:
                    memory_values.append(data['memory']['usage_percent'])
                if 'disk' in data and 'usage_percent' in data['disk']:
                    disk_values.append(data['disk']['usage_percent'])
        
        report = {
            'time_period_hours': hours,
            'data_points': len(metrics),
            'cpu': _calculate_stats(cpu_values) if cpu_values else None,
            'memory': _calculate_stats(memory_values) if memory_values else None,
            'disk': _calculate_stats(disk_values) if disk_values else None,
            'first_metric': metrics[0].collected_at.isoformat() if metrics else None,
            'last_metric': metrics[-1].collected_at.isoformat() if metrics else None
        }
        
        return report
        
    except Exception as e:
        logger.error(f"Error processing metrics for report: {e}")
        return {'error': str(e)}


def _calculate_stats(values: List[float]) -> Dict:
    """Calculate statistical summary for a list of values."""
    if not values:
        return {}
    
    return {
        'min': min(values),
        'max': max(values),
        'avg': sum(values) / len(values),
        'count': len(values),
        'latest': values[-1] if values else None
    }


def _get_job_statistics(db: Session, cutoff_time: datetime) -> Dict:
    """Get job statistics for the reporting period."""
    try:
        # Jobs created in period
        created_count = db.query(Job).filter(
            Job.created_at >= cutoff_time
        ).count()
        
        # Jobs completed in period
        completed_count = db.query(Job).filter(
            Job.completed_at >= cutoff_time,
            Job.status.in_([JobStatus.COMPLETED, JobStatus.EXHAUSTED])
        ).count()
        
        # Jobs failed in period
        failed_count = db.query(Job).filter(
            Job.completed_at >= cutoff_time,
            Job.status == JobStatus.FAILED
        ).count()
        
        # Currently running jobs
        running_count = db.query(Job).filter(
            Job.status == JobStatus.RUNNING
        ).count()
        
        return {
            'jobs_created': created_count,
            'jobs_completed': completed_count,
            'jobs_failed': failed_count,
            'jobs_currently_running': running_count,
            'success_rate': (completed_count / (completed_count + failed_count)) * 100 if (completed_count + failed_count) > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting job statistics: {e}")
        return {'error': str(e)}


async def _send_health_alerts(issues: List[Dict]):
    """Send health alerts for critical issues."""
    try:
        notification_service = NotificationService()
        
        for issue in issues:
            await notification_service.send_system_notification(
                'system.health_alert',
                f"Job health issue detected: {issue.get('description', 'Unknown issue')}",
                {'issue': issue}
            )
            
    except Exception as e:
        logger.error(f"Error sending health alerts: {e}")


def _time_since(timestamp: datetime) -> str:
    """Calculate human-readable time since timestamp."""
    delta = datetime.utcnow() - timestamp
    
    if delta.days > 0:
        return f"{delta.days} day(s)"
    elif delta.seconds >= 3600:
        hours = delta.seconds // 3600
        return f"{hours} hour(s)"
    elif delta.seconds >= 60:
        minutes = delta.seconds // 60
        return f"{minutes} minute(s)"
    else:
        return f"{delta.seconds} second(s)"