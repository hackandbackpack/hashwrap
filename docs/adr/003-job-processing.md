# ADR-003: Job Processing Architecture

## Status
Accepted

## Context
Need reliable, scalable job processing for long-running hashcat operations with real-time status updates, job control (pause/resume/stop), and fault tolerance.

## Decision

### Queue Architecture
- **Broker**: Redis for message queuing and result storage
- **Workers**: Celery workers with job isolation and resource management
- **Scheduler**: Celery Beat for periodic tasks (directory watching, cleanup)
- **Routing**: Separate queues for different job types and priorities

### Job State Machine
```
queued → preparing → running → paused → completed
                           → failed
                           → cancelled
                           → exhausted
```

### Status Reporting
- **Real-time Updates**: Parse hashcat --status-json output
- **Progress Metrics**: Speed, ETA, candidates processed, GPU utilization
- **Event Streaming**: Server-Sent Events from API to web UI
- **Persistence**: Job events stored in database for history

### Job Control
- **Pause/Resume**: SIGSTOP/SIGCONT process management
- **Graceful Stop**: SIGTERM with cleanup timeout
- **Force Kill**: SIGKILL as last resort
- **Checkpointing**: Hashcat session files for resume capability

### Resource Management
- **GPU Affinity**: Assign specific GPUs to jobs
- **Memory Limits**: Container-level memory constraints
- **Disk Quotas**: Per-project storage limits
- **Timeout Controls**: Maximum runtime per job

### Profile System
Configuration-driven attack strategies:
- **Built-in Profiles**: quick, balanced, thorough
- **Custom Profiles**: Admin-configurable attack sequences
- **Attack Types**: Dictionary+rules, hybrid, mask, PRINCE
- **Resource Limits**: Time caps, attempt limits per attack

## Implementation
- Celery worker with custom job class for hashcat integration
- Redis for both message queue and real-time status storage
- Process management using psutil for reliable control
- File-based checkpointing with atomic operations

## Consequences
- Reliable job processing with fault tolerance
- Real-time visibility into long-running operations
- Flexible attack strategy configuration
- Resource isolation prevents job interference
- Complexity of distributed system management