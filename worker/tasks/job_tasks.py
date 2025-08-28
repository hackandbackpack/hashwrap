"""
Celery tasks for hashcat job execution and control.
Handles job lifecycle, real-time status monitoring, and control operations.
"""

import json
import os
import signal
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from celery import current_task
from celery.exceptions import Ignore, Retry
from sqlalchemy.orm import Session

from worker.celery_app import celery
from worker.services.hashcat_service import HashcatService, HashcatJobControl
from worker.services.notification_service import NotificationService
from worker.utils.database import get_db_session
from worker.utils.logging import get_task_logger
from backend.app.models.job import Job, JobStatus, JobEvent, JobEventType


logger = get_task_logger(__name__)


@celery.task(bind=True, name='worker.tasks.job_tasks.execute_hashcat_job')
def execute_hashcat_job(self, job_id: str) -> Dict[str, Any]:
    """
    Execute a hashcat job with real-time progress monitoring.
    This is the main worker task that handles the complete job lifecycle.
    """
    logger.info(f"Starting hashcat job execution for job_id: {job_id}")
    
    hashcat_service = None
    job_control = None
    notification_service = NotificationService()
    
    try:
        with get_db_session() as db:
            # Load job from database
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            # Initialize services
            hashcat_service = HashcatService(job, db)
            job_control = HashcatJobControl(job, db)
            
            # Update job status to preparing
            job.status = JobStatus.PREPARING
            job.started_at = datetime.utcnow()
            db.commit()
            
            # Create job started event
            _create_job_event(db, job, JobEventType.STARTED, "Job started preparing")
            
            # Send notification
            await notification_service.send_job_notification(
                job, 'job.started', {'message': 'Job preparation started'}
            )
            
            # Prepare hashcat execution
            logger.info(f"Preparing hashcat execution for job {job_id}")
            preparation_result = hashcat_service.prepare_execution()
            
            if not preparation_result['success']:
                raise Exception(f"Job preparation failed: {preparation_result['error']}")
            
            # Update job status to running
            job.status = JobStatus.RUNNING
            db.commit()
            
            _create_job_event(db, job, JobEventType.PROGRESS, "Job execution started")
            
            # Execute hashcat with real-time monitoring
            logger.info(f"Starting hashcat execution for job {job_id}")
            execution_result = hashcat_service.execute_with_monitoring(
                progress_callback=lambda progress: _handle_progress_update(
                    self, job_id, progress, notification_service
                ),
                job_control=job_control
            )
            
            # Process final results
            final_result = _process_job_completion(
                db, job, execution_result, notification_service
            )
            
            logger.info(f"Job {job_id} completed successfully")
            return final_result
            
    except Exception as e:
        logger.error(f"Error executing job {job_id}: {str(e)}", exc_info=True)
        
        try:
            with get_db_session() as db:
                job = db.query(Job).filter(Job.id == job_id).first()
                if job:
                    job.status = JobStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    db.commit()
                    
                    _create_job_event(db, job, JobEventType.FAILED, f"Job failed: {str(e)}")
                    
                    await notification_service.send_job_notification(
                        job, 'job.failed', {'error': str(e)}
                    )
        except Exception as cleanup_error:
            logger.error(f"Error during job cleanup: {cleanup_error}")
        
        raise
    
    finally:
        # Cleanup resources
        if hashcat_service:
            hashcat_service.cleanup()
        if job_control:
            job_control.cleanup()


@celery.task(bind=True, name='worker.tasks.job_tasks.pause_job')
def pause_job(self, job_id: str) -> Dict[str, Any]:
    """Pause a running hashcat job."""
    logger.info(f"Pausing job {job_id}")
    
    try:
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return {'success': False, 'error': f'Job {job_id} not found'}
            
            if job.status != JobStatus.RUNNING:
                return {'success': False, 'error': f'Job {job_id} is not running (status: {job.status})'}
            
            # Create job control instance
            job_control = HashcatJobControl(job, db)
            result = job_control.pause()
            
            if result['success']:
                job.status = JobStatus.PAUSED
                db.commit()
                
                _create_job_event(db, job, JobEventType.PAUSED, "Job paused by user request")
                
                notification_service = NotificationService()
                await notification_service.send_job_notification(
                    job, 'job.paused', {'message': 'Job paused successfully'}
                )
            
            return result
            
    except Exception as e:
        logger.error(f"Error pausing job {job_id}: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}


@celery.task(bind=True, name='worker.tasks.job_tasks.resume_job')
def resume_job(self, job_id: str) -> Dict[str, Any]:
    """Resume a paused hashcat job."""
    logger.info(f"Resuming job {job_id}")
    
    try:
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return {'success': False, 'error': f'Job {job_id} not found'}
            
            if job.status != JobStatus.PAUSED:
                return {'success': False, 'error': f'Job {job_id} is not paused (status: {job.status})'}
            
            # Create job control instance
            job_control = HashcatJobControl(job, db)
            result = job_control.resume()
            
            if result['success']:
                job.status = JobStatus.RUNNING
                db.commit()
                
                _create_job_event(db, job, JobEventType.RESUMED, "Job resumed by user request")
                
                notification_service = NotificationService()
                await notification_service.send_job_notification(
                    job, 'job.resumed', {'message': 'Job resumed successfully'}
                )
            
            return result
            
    except Exception as e:
        logger.error(f"Error resuming job {job_id}: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}


@celery.task(bind=True, name='worker.tasks.job_tasks.cancel_job')
def cancel_job(self, job_id: str) -> Dict[str, Any]:
    """Cancel a running or paused hashcat job."""
    logger.info(f"Cancelling job {job_id}")
    
    try:
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return {'success': False, 'error': f'Job {job_id} not found'}
            
            if job.is_completed:
                return {'success': False, 'error': f'Job {job_id} is already completed (status: {job.status})'}
            
            # Create job control instance
            job_control = HashcatJobControl(job, db)
            result = job_control.cancel()
            
            if result['success']:
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.utcnow()
                db.commit()
                
                _create_job_event(db, job, JobEventType.CANCELLED, "Job cancelled by user request")
                
                notification_service = NotificationService()
                await notification_service.send_job_notification(
                    job, 'job.cancelled', {'message': 'Job cancelled successfully'}
                )
            
            return result
            
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}


@celery.task(bind=True, name='worker.tasks.job_tasks.get_job_status')
def get_job_status(self, job_id: str) -> Dict[str, Any]:
    """Get real-time status of a hashcat job."""
    try:
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return {'success': False, 'error': f'Job {job_id} not found'}
            
            # Get basic job information
            status_info = {
                'success': True,
                'job_id': job.id,
                'name': job.name,
                'status': job.status.value,
                'total_hashes': job.total_hashes,
                'cracked_count': job.cracked_count,
                'progress_percentage': job.progress_percentage,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'runtime_seconds': job.runtime_seconds,
            }
            
            # Get real-time hashcat status if job is active
            if job.is_active:
                try:
                    job_control = HashcatJobControl(job, db)
                    live_status = job_control.get_live_status()
                    if live_status['success']:
                        status_info.update(live_status['data'])
                except Exception as e:
                    logger.warning(f"Could not get live status for job {job_id}: {e}")
            
            return status_info
            
    except Exception as e:
        logger.error(f"Error getting job status {job_id}: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}


def _handle_progress_update(task_instance, job_id: str, progress_data: Dict, 
                          notification_service: NotificationService):
    """Handle real-time progress updates from hashcat."""
    try:
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return
            
            # Update job progress in database
            if 'cracked_count' in progress_data:
                job.cracked_count = progress_data['cracked_count']
            
            # Store progress event
            _create_job_event(
                db, job, JobEventType.PROGRESS, 
                "Progress update", 
                metadata=progress_data
            )
            
            # Update Celery task state
            task_instance.update_state(
                state='PROGRESS',
                meta={
                    'current': progress_data.get('progress_percentage', 0),
                    'total': 100,
                    'status': f"Progress: {progress_data.get('progress_percentage', 0)}%"
                }
            )
            
            # Check if we should send notification
            last_notification = getattr(task_instance, '_last_notification_time', 0)
            current_time = time.time()
            
            # Send progress notifications every 5 minutes
            if current_time - last_notification > 300:
                notification_service.send_job_notification(
                    job, 'job.progress', progress_data
                )
                task_instance._last_notification_time = current_time
            
            # Check for cracked hashes
            if progress_data.get('newly_cracked', 0) > 0:
                _create_job_event(
                    db, job, JobEventType.HASH_CRACKED,
                    f"{progress_data['newly_cracked']} new hashes cracked",
                    metadata={'newly_cracked': progress_data['newly_cracked']}
                )
                
                notification_service.send_job_notification(
                    job, 'hash.cracked', {
                        'newly_cracked': progress_data['newly_cracked'],
                        'total_cracked': progress_data.get('cracked_count', 0)
                    }
                )
            
            db.commit()
            
    except Exception as e:
        logger.error(f"Error handling progress update for job {job_id}: {e}", exc_info=True)


def _process_job_completion(db: Session, job: Job, execution_result: Dict, 
                          notification_service: NotificationService) -> Dict[str, Any]:
    """Process job completion and update database."""
    try:
        # Update job status based on execution result
        if execution_result['success']:
            if execution_result.get('exhausted', False):
                job.status = JobStatus.EXHAUSTED
                event_type = JobEventType.COMPLETED
                message = "Job completed - all attacks exhausted"
            else:
                job.status = JobStatus.COMPLETED
                event_type = JobEventType.COMPLETED
                message = "Job completed successfully"
        else:
            job.status = JobStatus.FAILED
            event_type = JobEventType.FAILED
            message = f"Job failed: {execution_result.get('error', 'Unknown error')}"
        
        # Set completion time
        job.completed_at = datetime.utcnow()
        
        # Update final crack count if available
        if 'final_cracked_count' in execution_result:
            job.cracked_count = execution_result['final_cracked_count']
        
        # Create completion event
        _create_job_event(db, job, event_type, message, metadata=execution_result)
        
        # Commit changes
        db.commit()
        
        # Send completion notification
        notification_event = 'job.completed' if execution_result['success'] else 'job.failed'
        notification_service.send_job_notification(job, notification_event, execution_result)
        
        return {
            'success': True,
            'job_id': job.id,
            'status': job.status.value,
            'final_cracked_count': job.cracked_count,
            'total_hashes': job.total_hashes,
            'progress_percentage': job.progress_percentage,
            'runtime_seconds': job.runtime_seconds,
            'execution_result': execution_result
        }
        
    except Exception as e:
        logger.error(f"Error processing job completion for {job.id}: {e}", exc_info=True)
        raise


def _create_job_event(db: Session, job: Job, event_type: JobEventType, 
                     message: str, metadata: Optional[Dict] = None):
    """Create a job event record."""
    try:
        event = JobEvent(
            job_id=job.id,
            event_type=event_type,
            message=message,
            metadata=metadata
        )
        db.add(event)
        # Note: Not committing here - let caller handle transaction
        
    except Exception as e:
        logger.error(f"Error creating job event for {job.id}: {e}", exc_info=True)
        raise


# Task cleanup and monitoring functions
@celery.task(bind=True, name='worker.tasks.job_tasks.cleanup_job_resources')
def cleanup_job_resources(self, job_id: str) -> Dict[str, Any]:
    """Clean up resources associated with a completed job."""
    logger.info(f"Cleaning up resources for job {job_id}")
    
    try:
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return {'success': False, 'error': f'Job {job_id} not found'}
            
            # Initialize cleanup service
            hashcat_service = HashcatService(job, db)
            cleanup_result = hashcat_service.cleanup_job_files()
            
            logger.info(f"Cleanup completed for job {job_id}")
            return cleanup_result
            
    except Exception as e:
        logger.error(f"Error cleaning up job {job_id}: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}