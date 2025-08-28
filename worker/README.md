# HashWrap Celery Worker System

A comprehensive Celery-based worker system for distributed hash cracking operations using hashcat.

## Architecture

The worker system consists of several components:

### Core Components

- **`celery_app.py`** - Main Celery application configuration with Redis broker
- **`tasks/`** - Task modules for different operation types
- **`services/`** - Business logic services 
- **`utils/`** - Utility modules for database, logging, and file operations

### Task Queues

- **`hashcat`** - Long-running hashcat job execution
- **`control`** - Job control operations (pause, resume, cancel)
- **`monitoring`** - Progress updates and metrics collection
- **`maintenance`** - System cleanup and maintenance
- **`watcher`** - Directory monitoring and file processing
- **`default`** - General purpose tasks

## Features

### Job Management
- Execute hashcat jobs with real-time progress monitoring
- Parse `--status-json` output for accurate progress tracking
- Support job control operations (pause, resume, cancel)
- Automatic attack orchestration based on hash types
- Integration with existing HashWrap core components

### Directory Monitoring
- Automatic polling of `/data/uploads` directory every 60 seconds
- Hash type detection using hashcat `--identify` and pattern matching
- Automatic job creation for detected hash files
- File validation and deduplication
- Secure file processing with validation

### Notification System
- Integration with existing webhook system
- Support for Discord and Slack notifications
- Configurable event types and notification channels
- Retry logic with exponential backoff
- HMAC signature validation for webhook security

### System Monitoring
- Real-time system metrics collection (CPU, memory, disk, GPU)
- Job health monitoring and alerting
- Performance reporting and analytics
- Resource usage tracking and cleanup recommendations

### Security Features
- Input validation and sanitization
- Path traversal protection
- Command injection prevention
- Secure file operations
- Audit logging for security events

## Installation

1. Ensure Redis is running:
```bash
redis-server
```

2. Install Python dependencies (already included in backend requirements):
```bash
pip install celery[redis] structlog python-magic psutil
```

3. Start Celery workers for different queues:

```bash
# Hashcat job worker (limited concurrency for resource management)
celery -A worker.celery_app worker -Q hashcat --concurrency=2 --prefetch-multiplier=1

# Control operations worker
celery -A worker.celery_app worker -Q control --concurrency=10 --prefetch-multiplier=4

# Monitoring worker
celery -A worker.celery_app worker -Q monitoring --concurrency=4 --prefetch-multiplier=2

# Directory watcher worker
celery -A worker.celery_app worker -Q watcher --concurrency=2 --prefetch-multiplier=1

# Maintenance worker
celery -A worker.celery_app worker -Q maintenance --concurrency=2 --prefetch-multiplier=1

# General purpose worker
celery -A worker.celery_app worker -Q default --concurrency=4 --prefetch-multiplier=1
```

4. Start Celery Beat for periodic tasks:
```bash
celery -A worker.celery_app beat --loglevel=info
```

## Configuration

### Environment Variables

Configure these in your `.env` file or environment:

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Directory Paths
UPLOAD_DIR=/data/uploads
RESULTS_DIR=/data/results
WORDLISTS_DIR=/wordlists
RULES_DIR=/rules

# Job Settings
MAX_CONCURRENT_JOBS=4
DIRECTORY_SCAN_INTERVAL=60
PROGRESS_UPDATE_INTERVAL=30

# GPU Settings (if available)
CUDA_VISIBLE_DEVICES=0,1,2,3
```

### Webhook Notifications

Configure webhooks in the database using the existing webhook system or via the web interface.

Supported events:
- `job.created` - New job created
- `job.started` - Job execution started
- `job.progress` - Progress update (configurable interval)
- `job.paused` / `job.resumed` - Job control operations
- `job.completed` - Job finished successfully
- `job.failed` - Job failed with error
- `job.cancelled` - Job cancelled by user
- `hash.cracked` - New password cracked
- `system.error` - System-level errors
- `system.alert` - Resource usage alerts

## Usage

### Manual Job Execution

```python
from worker.tasks.job_tasks import execute_hashcat_job

# Queue a job for execution
result = execute_hashcat_job.delay('job-uuid-here')
```

### Directory Processing

```python
from worker.tasks.directory_watcher import process_single_upload

# Process a specific file
result = process_single_upload.delay('/path/to/hashfile.txt')
```

### System Monitoring

```python
from worker.tasks.monitoring_tasks import generate_system_report

# Generate performance report
result = generate_system_report.delay(hours=24)
```

## Monitoring

### Celery Flower (Optional)

Install and run Flower for web-based monitoring:

```bash
pip install flower
celery -A worker.celery_app flower
```

Access at `http://localhost:5555`

### Health Checks

The system includes built-in health checks:

- Database connectivity
- Redis connectivity  
- File system access
- Job queue status
- Resource usage monitoring

### Logs

Structured JSON logs are written to stdout with contextual information:

```json
{
  "timestamp": "2024-01-20T15:30:45.123456Z",
  "level": "info",
  "message": "Job execution started",
  "task": {
    "id": "task-uuid",
    "name": "worker.tasks.job_tasks.execute_hashcat_job",
    "retries": 0
  },
  "job_id": "job-uuid",
  "hash_type": "SHA256"
}
```

## Security Considerations

### File Security
- All file paths are validated against allowed directories
- Path traversal attacks are prevented
- File content is validated before processing
- Temporary files are securely cleaned up

### Command Injection Prevention
- All hashcat command arguments are validated
- No shell execution - direct subprocess calls only
- Input sanitization for all user-provided data

### Resource Limits
- File size limits (default 100MB)
- Line count limits (default 10M lines) 
- Process timeouts and resource monitoring
- Automatic cleanup of old files and processes

### Audit Trail
- All security events are logged
- File access attempts are tracked
- Command executions are audited
- Failed authentication attempts are recorded

## Performance Tuning

### Worker Configuration

Adjust concurrency based on your system:

```bash
# CPU-intensive tasks (hashcat)
--concurrency=<number_of_gpus>

# I/O-intensive tasks (monitoring, file processing)  
--concurrency=<cpu_cores * 2>

# Control operations
--concurrency=10+
```

### Memory Management

- Workers restart after processing 50 tasks to prevent memory leaks
- Large files are processed in streaming chunks
- Database connections are properly pooled and cleaned up

### GPU Resource Management

- Hashcat jobs are limited to available GPU count
- GPU temperature and utilization monitoring
- Automatic job throttling on resource exhaustion

## Troubleshooting

### Common Issues

1. **Redis Connection Errors**
   - Verify Redis is running: `redis-cli ping`
   - Check REDIS_URL configuration
   - Ensure Redis accepts connections from worker hosts

2. **Hashcat Not Found**
   - Verify hashcat is in PATH: `which hashcat`
   - Install hashcat if missing
   - Check hashcat version compatibility

3. **Permission Errors**
   - Verify file permissions on upload/results directories
   - Ensure worker process has read/write access
   - Check directory ownership

4. **High Memory Usage**
   - Reduce worker concurrency
   - Enable worker auto-restart: `--max-tasks-per-child=50`
   - Monitor large file processing

### Debug Mode

Enable debug logging:

```bash
celery -A worker.celery_app worker --loglevel=debug
```

### Task Monitoring

Check task status:

```python
from worker.celery_app import celery

# Get active tasks
active = celery.control.inspect().active()

# Get scheduled tasks  
scheduled = celery.control.inspect().scheduled()

# Get task result
result = celery.AsyncResult('task-id')
print(result.status, result.result)
```

## Development

### Adding New Tasks

1. Create task function in appropriate module under `tasks/`
2. Register task in `celery_app.py` task routes
3. Add appropriate queue and concurrency settings
4. Include comprehensive error handling and logging
5. Add security validation for inputs
6. Write unit tests

### Testing

Run worker system tests:

```bash
# Unit tests
python -m pytest worker/tests/

# Integration tests  
python -m pytest worker/tests/integration/

# Load testing
python worker/tests/load_test.py
```

## Contributing

1. Follow existing code patterns and security practices
2. Add comprehensive logging and error handling
3. Include security validation for all inputs
4. Write unit tests for new functionality
5. Update documentation for new features