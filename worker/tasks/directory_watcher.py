"""
Celery Beat task for monitoring upload directory and auto-creating jobs.
Scans /data/uploads directory, detects hash types, and creates jobs automatically.
"""

import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

from celery import current_task
from sqlalchemy.orm import Session

from worker.celery_app import celery
from worker.services.hash_detection_service import HashDetectionService
from worker.services.notification_service import NotificationService
from worker.utils.database import get_db_session
from worker.utils.logging import get_task_logger
from worker.utils.file_utils import FileValidator, FileProcessor
from backend.app.models.job import Job, JobStatus
from backend.app.models.upload import Upload, UploadStatus
from backend.app.models.project import Project
from backend.app.core.config import get_settings


logger = get_task_logger(__name__)


@celery.task(bind=True, name='worker.tasks.directory_watcher.scan_upload_directory')
def scan_upload_directory(self) -> Dict[str, any]:
    """
    Scan the uploads directory for new hash files and create jobs automatically.
    This is a periodic task run by Celery Beat every 60 seconds.
    """
    logger.info("Starting upload directory scan")
    
    settings = get_settings()
    upload_dir = Path(settings.UPLOAD_DIR)
    processed_files = 0
    created_jobs = 0
    errors = []
    
    try:
        if not upload_dir.exists():
            logger.warning(f"Upload directory does not exist: {upload_dir}")
            return {
                'success': False,
                'error': f'Upload directory not found: {upload_dir}',
                'processed_files': 0,
                'created_jobs': 0
            }
        
        # Get list of files to process
        candidate_files = _get_candidate_files(upload_dir)
        logger.info(f"Found {len(candidate_files)} candidate files to process")
        
        # Initialize services
        hash_detection_service = HashDetectionService()
        notification_service = NotificationService()
        file_validator = FileValidator()
        
        with get_db_session() as db:
            for file_path in candidate_files:
                try:
                    result = _process_upload_file(
                        db, file_path, hash_detection_service, 
                        notification_service, file_validator
                    )
                    
                    if result['success']:
                        processed_files += 1
                        if result.get('job_created'):
                            created_jobs += 1
                    else:
                        errors.append(f"{file_path.name}: {result['error']}")
                        
                except Exception as e:
                    error_msg = f"Error processing {file_path.name}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
        
        # Update task progress
        current_task.update_state(
            state='SUCCESS',
            meta={
                'processed_files': processed_files,
                'created_jobs': created_jobs,
                'errors': len(errors),
                'scan_time': datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Directory scan completed: {processed_files} processed, {created_jobs} jobs created")
        
        return {
            'success': True,
            'processed_files': processed_files,
            'created_jobs': created_jobs,
            'errors': errors,
            'scan_time': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during directory scan: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'processed_files': processed_files,
            'created_jobs': created_jobs,
            'errors': errors
        }


@celery.task(bind=True, name='worker.tasks.directory_watcher.process_single_upload')
def process_single_upload(self, file_path: str, project_id: Optional[str] = None) -> Dict[str, any]:
    """
    Process a single upload file immediately.
    Used for manual processing or API-triggered uploads.
    """
    logger.info(f"Processing single upload: {file_path}")
    
    try:
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}
        
        # Initialize services
        hash_detection_service = HashDetectionService()
        notification_service = NotificationService()
        file_validator = FileValidator()
        
        with get_db_session() as db:
            result = _process_upload_file(
                db, file_path_obj, hash_detection_service,
                notification_service, file_validator, project_id
            )
            
            return result
            
    except Exception as e:
        logger.error(f"Error processing upload {file_path}: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}


def _get_candidate_files(upload_dir: Path) -> List[Path]:
    """Get list of files that are candidates for processing."""
    candidate_files = []
    
    # Supported file extensions for hash files
    hash_extensions = {'.txt', '.hash', '.hashes', '.lst', '.list'}
    
    try:
        for file_path in upload_dir.iterdir():
            if not file_path.is_file():
                continue
            
            # Check file extension
            if file_path.suffix.lower() not in hash_extensions:
                continue
            
            # Skip hidden files
            if file_path.name.startswith('.'):
                continue
            
            # Skip files that are being written (check modification time)
            try:
                # If file was modified in the last 30 seconds, skip it
                # This prevents processing files that are still being uploaded
                if datetime.now().timestamp() - file_path.stat().st_mtime < 30:
                    continue
            except OSError:
                continue
            
            # Skip empty files
            if file_path.stat().st_size == 0:
                continue
            
            candidate_files.append(file_path)
            
    except Exception as e:
        logger.error(f"Error scanning upload directory: {e}")
    
    # Sort by modification time (oldest first)
    candidate_files.sort(key=lambda f: f.stat().st_mtime)
    
    return candidate_files


def _process_upload_file(db: Session, file_path: Path, 
                        hash_detection_service: HashDetectionService,
                        notification_service: NotificationService,
                        file_validator: FileValidator,
                        project_id: Optional[str] = None) -> Dict[str, any]:
    """Process a single upload file."""
    logger.info(f"Processing upload file: {file_path}")
    
    try:
        # Check if file is already being processed
        existing_upload = db.query(Upload).filter(
            Upload.original_filename == file_path.name
        ).first()
        
        if existing_upload and not _is_duplicate_file(file_path, existing_upload):
            logger.info(f"File {file_path.name} already processed, skipping")
            return {'success': True, 'job_created': False, 'reason': 'already_processed'}
        
        # Validate file
        validation_result = file_validator.validate_hash_file(str(file_path))
        if not validation_result['valid']:
            logger.warning(f"File validation failed for {file_path}: {validation_result['error']}")
            return {'success': False, 'error': validation_result['error']}
        
        # Detect hash types
        logger.info(f"Detecting hash types in {file_path}")
        detection_result = hash_detection_service.analyze_file(str(file_path))
        
        if not detection_result['success']:
            return {'success': False, 'error': detection_result['error']}
        
        if not detection_result['detected_types']:
            logger.warning(f"No supported hash types detected in {file_path}")
            return {'success': False, 'error': 'No supported hash types detected'}
        
        # Get or create default project if not specified
        if not project_id:
            project = _get_or_create_default_project(db)
            project_id = project.id
        
        # Create upload record
        upload = _create_upload_record(db, file_path, detection_result, project_id)
        
        # Create jobs for each detected hash type
        created_jobs = []
        
        for hash_type, type_info in detection_result['detected_types'].items():
            if type_info['count'] < 1:
                continue
            
            job = _create_job_for_hash_type(
                db, upload, hash_type, type_info, project_id
            )
            
            if job:
                created_jobs.append(job)
        
        db.commit()
        
        # Send notifications for created jobs
        for job in created_jobs:
            await notification_service.send_job_notification(
                job, 'job.created', {
                    'source': 'directory_watcher',
                    'auto_created': True,
                    'file_path': str(file_path)
                }
            )
        
        # Queue jobs for execution
        from worker.tasks.job_tasks import execute_hashcat_job
        
        for job in created_jobs:
            execute_hashcat_job.delay(job.id)
            logger.info(f"Queued job {job.id} for execution")
        
        logger.info(f"Successfully processed {file_path}, created {len(created_jobs)} jobs")
        
        return {
            'success': True,
            'job_created': len(created_jobs) > 0,
            'jobs_created': len(created_jobs),
            'upload_id': upload.id,
            'job_ids': [job.id for job in created_jobs]
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing upload file {file_path}: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


def _is_duplicate_file(file_path: Path, existing_upload: Upload) -> bool:
    """Check if file is a duplicate of an existing upload."""
    try:
        # Compare file size
        if file_path.stat().st_size != existing_upload.file_size:
            return False
        
        # Compare file hash
        file_hash = _calculate_file_hash(file_path)
        if file_hash != existing_upload.file_hash:
            return False
        
        return True
        
    except Exception as e:
        logger.warning(f"Error checking for duplicate file: {e}")
        return False


def _calculate_file_hash(file_path: Path, chunk_size: int = 8192) -> str:
    """Calculate SHA256 hash of file."""
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256_hash.update(chunk)
    
    return sha256_hash.hexdigest()


def _get_or_create_default_project(db: Session) -> Project:
    """Get or create the default project for auto-created jobs."""
    # Look for existing default project
    default_project = db.query(Project).filter(
        Project.name == "Auto-Generated Jobs"
    ).first()
    
    if not default_project:
        # Create default project
        default_project = Project(
            name="Auto-Generated Jobs",
            description="Automatically created jobs from directory watcher",
            created_by="system"  # This should be a valid user ID in production
        )
        db.add(default_project)
        db.flush()  # Get the ID
    
    return default_project


def _create_upload_record(db: Session, file_path: Path, 
                         detection_result: Dict, project_id: str) -> Upload:
    """Create upload record in database."""
    file_hash = _calculate_file_hash(file_path)
    
    upload = Upload(
        project_id=project_id,
        original_filename=file_path.name,
        file_path=str(file_path),
        file_size=file_path.stat().st_size,
        file_hash=file_hash,
        hash_count=detection_result.get('total_hashes', 0),
        status=UploadStatus.COMPLETED,
        created_by="system"  # This should be a valid user ID in production
    )
    
    db.add(upload)
    db.flush()  # Get the ID
    
    return upload


def _create_job_for_hash_type(db: Session, upload: Upload, hash_type: str, 
                             type_info: Dict, project_id: str) -> Optional[Job]:
    """Create a job for a specific hash type."""
    try:
        # Generate job name
        job_name = f"Auto: {hash_type} ({upload.original_filename})"
        
        # Determine appropriate profile based on hash type
        profile_name = _select_profile_for_hash_type(hash_type)
        
        job = Job(
            name=job_name,
            project_id=project_id,
            upload_id=upload.id,
            hash_type=hash_type,
            profile_name=profile_name,
            status=JobStatus.QUEUED,
            total_hashes=type_info['count'],
            created_by="system"  # This should be a valid user ID in production
        )
        
        db.add(job)
        db.flush()  # Get the ID
        
        return job
        
    except Exception as e:
        logger.error(f"Error creating job for hash type {hash_type}: {e}")
        return None


def _select_profile_for_hash_type(hash_type: str) -> str:
    """Select appropriate attack profile based on hash type."""
    # Profile selection logic based on hash type characteristics
    profile_mapping = {
        'MD5': 'fast',
        'SHA1': 'fast', 
        'SHA256': 'medium',
        'SHA512': 'medium',
        'NTLM': 'fast',
        'NetNTLMv1': 'medium',
        'NetNTLMv2': 'medium',
        'bcrypt': 'slow',
        'scrypt': 'slow',
        'Argon2': 'slow',
        'MySQL': 'fast',
        'PostgreSQL': 'fast',
        'WordPress': 'medium',
        'Kerberos': 'slow'
    }
    
    # Default to medium if hash type not found
    return profile_mapping.get(hash_type, 'medium')


@celery.task(bind=True, name='worker.tasks.directory_watcher.cleanup_processed_files')
def cleanup_processed_files(self, max_age_days: int = 7) -> Dict[str, any]:
    """Clean up processed upload files older than specified days."""
    logger.info(f"Cleaning up processed files older than {max_age_days} days")
    
    settings = get_settings()
    upload_dir = Path(settings.UPLOAD_DIR)
    processed_dir = upload_dir / "processed"
    processed_dir.mkdir(exist_ok=True)
    
    cleaned_files = 0
    errors = []
    cutoff_date = datetime.now() - timedelta(days=max_age_days)
    
    try:
        with get_db_session() as db:
            # Find completed uploads older than cutoff
            old_uploads = db.query(Upload).filter(
                Upload.status == UploadStatus.COMPLETED,
                Upload.created_at < cutoff_date
            ).all()
            
            for upload in old_uploads:
                try:
                    file_path = Path(upload.file_path)
                    
                    if file_path.exists():
                        # Move to processed directory
                        processed_path = processed_dir / f"{upload.created_at.strftime('%Y%m%d')}_{file_path.name}"
                        file_path.rename(processed_path)
                        
                        # Update file path in database
                        upload.file_path = str(processed_path)
                        
                        cleaned_files += 1
                        
                except Exception as e:
                    error_msg = f"Error processing {upload.original_filename}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            db.commit()
        
        logger.info(f"Cleanup completed: {cleaned_files} files processed")
        
        return {
            'success': True,
            'cleaned_files': cleaned_files,
            'errors': errors
        }
        
    except Exception as e:
        logger.error(f"Error during file cleanup: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'cleaned_files': cleaned_files,
            'errors': errors
        }