"""
Celery tasks for system cleanup and maintenance.
Handles cleanup of old files, logs, and database records.
"""

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from sqlalchemy import func

from worker.celery_app import celery
from worker.utils.database import get_db_session
from worker.utils.logging import get_task_logger
from backend.app.models.job import Job, JobStatus, JobEvent
from backend.app.models.system_metric import SystemMetric
from backend.app.models.audit import AuditLog
from backend.app.core.config import get_settings


logger = get_task_logger(__name__)


@celery.task(bind=True, name='worker.tasks.cleanup_tasks.cleanup_old_files')
def cleanup_old_files(self) -> Dict[str, any]:
    """
    Clean up old job files and temporary data.
    This task runs daily at 2 AM to clean up old files.
    """
    logger.info("Starting cleanup of old files")
    
    settings = get_settings()
    cleaned_files = 0
    cleaned_directories = 0
    errors = []
    
    try:
        # Clean up old job result directories
        results_dir = Path(settings.RESULTS_DIR)
        if results_dir.exists():
            result = _cleanup_old_job_directories(results_dir, days_old=7)
            cleaned_directories += result['cleaned_directories']
            errors.extend(result['errors'])
        
        # Clean up temporary upload files
        upload_dir = Path(settings.UPLOAD_DIR)
        processed_dir = upload_dir / "processed"
        if processed_dir.exists():
            result = _cleanup_old_processed_files(processed_dir, days_old=30)
            cleaned_files += result['cleaned_files']
            errors.extend(result['errors'])
        
        # Clean up old log files
        result = _cleanup_old_logs(days_old=30)
        cleaned_files += result['cleaned_files']
        errors.extend(result['errors'])
        
        # Clean up hashcat session files
        result = _cleanup_hashcat_sessions(days_old=7)
        cleaned_files += result['cleaned_files']
        errors.extend(result['errors'])
        
        logger.info(f"File cleanup completed: {cleaned_files} files, {cleaned_directories} directories")
        
        return {
            'success': True,
            'cleaned_files': cleaned_files,
            'cleaned_directories': cleaned_directories,
            'errors': errors,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during file cleanup: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'cleaned_files': cleaned_files,
            'cleaned_directories': cleaned_directories,
            'errors': errors
        }


@celery.task(bind=True, name='worker.tasks.cleanup_tasks.cleanup_old_database_records')
def cleanup_old_database_records(self) -> Dict[str, any]:
    """Clean up old database records based on retention policies."""
    logger.info("Starting cleanup of old database records")
    
    settings = get_settings()
    cleaned_records = {
        'job_events': 0,
        'system_metrics': 0,
        'audit_logs': 0
    }
    errors = []
    
    try:
        with get_db_session() as db:
            # Clean up old job events (keep last 90 days)
            job_events_cutoff = datetime.utcnow() - timedelta(days=90)
            deleted_events = db.query(JobEvent).filter(
                JobEvent.created_at < job_events_cutoff
            ).delete()
            cleaned_records['job_events'] = deleted_events
            
            # Clean up old system metrics (keep last 30 days of detailed data)
            metrics_cutoff = datetime.utcnow() - timedelta(days=30)
            deleted_metrics = db.query(SystemMetric).filter(
                SystemMetric.collected_at < metrics_cutoff
            ).delete()
            cleaned_records['system_metrics'] = deleted_metrics
            
            # Clean up old audit logs based on retention policy
            audit_cutoff = datetime.utcnow() - timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS)
            deleted_audit = db.query(AuditLog).filter(
                AuditLog.timestamp < audit_cutoff
            ).delete()
            cleaned_records['audit_logs'] = deleted_audit
            
            # Clean up completed job data older than data retention policy
            data_cutoff = datetime.utcnow() - timedelta(days=settings.DATA_RETENTION_DAYS)
            
            # Mark old completed jobs for cleanup (don't delete, just mark)
            old_jobs = db.query(Job).filter(
                Job.completed_at < data_cutoff,
                Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED])
            ).all()
            
            # For each old job, clean up associated files but keep record
            for job in old_jobs:
                try:
                    job_dir = Path(settings.RESULTS_DIR) / f"job_{job.id}"
                    if job_dir.exists():
                        shutil.rmtree(job_dir)
                        logger.debug(f"Cleaned up files for old job {job.id}")
                except Exception as e:
                    errors.append(f"Error cleaning job {job.id} files: {str(e)}")
            
            db.commit()
        
        total_cleaned = sum(cleaned_records.values())
        logger.info(f"Database cleanup completed: {total_cleaned} records cleaned")
        
        return {
            'success': True,
            'cleaned_records': cleaned_records,
            'total_cleaned': total_cleaned,
            'errors': errors,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during database cleanup: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'cleaned_records': cleaned_records,
            'errors': errors
        }


@celery.task(bind=True, name='worker.tasks.cleanup_tasks.vacuum_database')
def vacuum_database(self) -> Dict[str, any]:
    """Vacuum database to reclaim space and optimize performance."""
    logger.info("Starting database vacuum operation")
    
    try:
        with get_db_session() as db:
            # For SQLite databases
            if 'sqlite' in str(db.bind.url):
                db.execute('VACUUM;')
                db.commit()
                
                # Also run ANALYZE to update statistics
                db.execute('ANALYZE;')
                db.commit()
                
            # For PostgreSQL databases
            elif 'postgresql' in str(db.bind.url):
                # Note: VACUUM cannot be run inside a transaction
                # This would need to be handled differently in production
                logger.info("PostgreSQL VACUUM should be run outside of transaction")
            
        logger.info("Database vacuum completed")
        
        return {
            'success': True,
            'operation': 'vacuum',
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during database vacuum: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


@celery.task(bind=True, name='worker.tasks.cleanup_tasks.cleanup_failed_jobs')
def cleanup_failed_jobs(self, older_than_hours: int = 24) -> Dict[str, any]:
    """Clean up resources from failed jobs."""
    logger.info(f"Cleaning up failed jobs older than {older_than_hours} hours")
    
    settings = get_settings()
    cleaned_jobs = 0
    errors = []
    
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
        
        with get_db_session() as db:
            # Find failed jobs older than cutoff
            failed_jobs = db.query(Job).filter(
                Job.status == JobStatus.FAILED,
                Job.completed_at < cutoff_time
            ).all()
            
            logger.info(f"Found {len(failed_jobs)} failed jobs to clean up")
            
            for job in failed_jobs:
                try:
                    # Clean up job files
                    job_dir = Path(settings.RESULTS_DIR) / f"job_{job.id}"
                    if job_dir.exists():
                        shutil.rmtree(job_dir)
                        logger.debug(f"Cleaned up files for failed job {job.id}")
                    
                    cleaned_jobs += 1
                    
                except Exception as e:
                    error_msg = f"Error cleaning failed job {job.id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        
        logger.info(f"Failed job cleanup completed: {cleaned_jobs} jobs processed")
        
        return {
            'success': True,
            'cleaned_jobs': cleaned_jobs,
            'errors': errors,
            'cutoff_hours': older_than_hours,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during failed job cleanup: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'cleaned_jobs': cleaned_jobs,
            'errors': errors
        }


@celery.task(bind=True, name='worker.tasks.cleanup_tasks.generate_cleanup_report')
def generate_cleanup_report(self) -> Dict[str, any]:
    """Generate a report on cleanup activities and storage usage."""
    logger.info("Generating cleanup report")
    
    settings = get_settings()
    
    try:
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'storage_usage': {},
            'database_stats': {},
            'cleanup_recommendations': []
        }
        
        # Get storage usage for key directories
        for dir_name, dir_path in [
            ('results', settings.RESULTS_DIR),
            ('uploads', settings.UPLOAD_DIR),
            ('wordlists', settings.WORDLISTS_DIR),
            ('rules', settings.RULES_DIR)
        ]:
            try:
                path = Path(dir_path)
                if path.exists():
                    usage = _get_directory_usage(path)
                    report['storage_usage'][dir_name] = usage
            except Exception as e:
                report['storage_usage'][dir_name] = {'error': str(e)}
        
        # Get database statistics
        with get_db_session() as db:
            report['database_stats'] = {
                'total_jobs': db.query(Job).count(),
                'active_jobs': db.query(Job).filter(
                    Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED, JobStatus.PREPARING])
                ).count(),
                'completed_jobs': db.query(Job).filter(
                    Job.status == JobStatus.COMPLETED
                ).count(),
                'failed_jobs': db.query(Job).filter(
                    Job.status == JobStatus.FAILED
                ).count(),
                'job_events_count': db.query(JobEvent).count(),
                'system_metrics_count': db.query(SystemMetric).count()
            }
        
        # Generate cleanup recommendations
        recommendations = []
        
        # Check for large result directories
        results_usage = report['storage_usage'].get('results', {})
        if results_usage.get('total_size_gb', 0) > 10:
            recommendations.append({
                'type': 'storage',
                'priority': 'medium',
                'description': f"Results directory is {results_usage['total_size_gb']:.1f}GB - consider cleaning old job files"
            })
        
        # Check for old jobs that could be cleaned
        if report['database_stats']['failed_jobs'] > 100:
            recommendations.append({
                'type': 'database',
                'priority': 'low',
                'description': f"{report['database_stats']['failed_jobs']} failed jobs in database - consider cleanup"
            })
        
        report['cleanup_recommendations'] = recommendations
        
        logger.info("Cleanup report generated successfully")
        
        return {
            'success': True,
            'report': report
        }
        
    except Exception as e:
        logger.error(f"Error generating cleanup report: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


def _cleanup_old_job_directories(results_dir: Path, days_old: int) -> Dict[str, any]:
    """Clean up old job result directories."""
    cleaned_directories = 0
    errors = []
    cutoff_time = datetime.now() - timedelta(days=days_old)
    
    try:
        for job_dir in results_dir.iterdir():
            if not job_dir.is_dir() or not job_dir.name.startswith('job_'):
                continue
            
            try:
                # Check directory modification time
                dir_mtime = datetime.fromtimestamp(job_dir.stat().st_mtime)
                
                if dir_mtime < cutoff_time:
                    shutil.rmtree(job_dir)
                    cleaned_directories += 1
                    logger.debug(f"Removed old job directory: {job_dir}")
                    
            except Exception as e:
                errors.append(f"Error removing directory {job_dir}: {str(e)}")
    
    except Exception as e:
        errors.append(f"Error accessing results directory: {str(e)}")
    
    return {
        'cleaned_directories': cleaned_directories,
        'errors': errors
    }


def _cleanup_old_processed_files(processed_dir: Path, days_old: int) -> Dict[str, any]:
    """Clean up old processed upload files."""
    cleaned_files = 0
    errors = []
    cutoff_time = datetime.now() - timedelta(days=days_old)
    
    try:
        for file_path in processed_dir.iterdir():
            if not file_path.is_file():
                continue
            
            try:
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_mtime < cutoff_time:
                    file_path.unlink()
                    cleaned_files += 1
                    logger.debug(f"Removed old processed file: {file_path}")
                    
            except Exception as e:
                errors.append(f"Error removing file {file_path}: {str(e)}")
    
    except Exception as e:
        errors.append(f"Error accessing processed directory: {str(e)}")
    
    return {
        'cleaned_files': cleaned_files,
        'errors': errors
    }


def _cleanup_old_logs(days_old: int) -> Dict[str, any]:
    """Clean up old log files."""
    cleaned_files = 0
    errors = []
    
    # Common log directories to check
    log_dirs = [
        Path('/var/log/hashwrap'),
        Path('./logs'),
        Path('../logs'),
    ]
    
    cutoff_time = datetime.now() - timedelta(days=days_old)
    
    for log_dir in log_dirs:
        if not log_dir.exists():
            continue
        
        try:
            for log_file in log_dir.glob('*.log*'):
                if log_file.is_file():
                    try:
                        file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                        
                        if file_mtime < cutoff_time:
                            log_file.unlink()
                            cleaned_files += 1
                            logger.debug(f"Removed old log file: {log_file}")
                            
                    except Exception as e:
                        errors.append(f"Error removing log file {log_file}: {str(e)}")
        
        except Exception as e:
            errors.append(f"Error accessing log directory {log_dir}: {str(e)}")
    
    return {
        'cleaned_files': cleaned_files,
        'errors': errors
    }


def _cleanup_hashcat_sessions(days_old: int) -> Dict[str, any]:
    """Clean up old hashcat session files."""
    cleaned_files = 0
    errors = []
    
    # Look for .restore, .session, and other hashcat temporary files
    session_patterns = ['*.restore', '*.session', '*.dictstat', '*.log']
    cutoff_time = datetime.now() - timedelta(days=days_old)
    
    # Check current directory and common hashcat locations
    search_dirs = [
        Path('.'),
        Path('/tmp'),
        Path('./sessions'),
    ]
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        
        for pattern in session_patterns:
            try:
                for session_file in search_dir.glob(pattern):
                    if session_file.is_file():
                        try:
                            file_mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
                            
                            if file_mtime < cutoff_time:
                                session_file.unlink()
                                cleaned_files += 1
                                logger.debug(f"Removed old session file: {session_file}")
                                
                        except Exception as e:
                            errors.append(f"Error removing session file {session_file}: {str(e)}")
            
            except Exception as e:
                errors.append(f"Error searching for pattern {pattern} in {search_dir}: {str(e)}")
    
    return {
        'cleaned_files': cleaned_files,
        'errors': errors
    }


def _get_directory_usage(directory: Path) -> Dict[str, any]:
    """Get directory usage statistics."""
    try:
        total_size = 0
        file_count = 0
        
        for item in directory.rglob('*'):
            if item.is_file():
                try:
                    size = item.stat().st_size
                    total_size += size
                    file_count += 1
                except (OSError, PermissionError):
                    pass  # Skip files we can't read
        
        return {
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'total_size_gb': round(total_size / (1024 * 1024 * 1024), 2),
            'file_count': file_count,
            'directory_path': str(directory)
        }
        
    except Exception as e:
        return {
            'error': str(e),
            'directory_path': str(directory)
        }