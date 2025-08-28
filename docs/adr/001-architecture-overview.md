# ADR-001: Architecture Overview

## Status
Accepted

## Context
Transform hashwrap from a CLI tool into a production-ready web-managed cracking service with authentication, job queuing, real-time monitoring, and enterprise security controls.

## Decision
Adopt a microservices architecture with the following components:

### Core Components
- **API Gateway**: FastAPI backend handling authentication, authorization, and business logic
- **Worker Pool**: Celery workers executing hashcat jobs with real-time status reporting
- **Scheduler**: Celery Beat for periodic tasks (directory watching, cleanup)
- **Queue**: Redis as message broker and result backend
- **Database**: PostgreSQL for persistent data, SQLite for development
- **Web UI**: React + TypeScript SPA with real-time updates via SSE

### Security Architecture
- **Authentication**: Session-based auth with bcrypt + TOTP 2FA
- **Authorization**: Role-based access control (admin/operator/viewer)
- **Input Validation**: Comprehensive file validation, anti-path traversal
- **Audit Logging**: Immutable logs for all sensitive operations
- **Secrets Management**: Environment variables and Docker secrets

### Data Flow
1. Files uploaded via web UI → validation → storage → job creation
2. Directory watcher polls uploads → auto-detection → job queuing
3. Workers consume jobs → execute hashcat → stream status → store results
4. Web UI polls job status → displays real-time progress → shows results

## Consequences

### Positive
- Clear separation of concerns
- Scalable job processing
- Real-time status updates
- Enterprise-grade security
- Production-ready observability

### Negative
- Increased complexity vs CLI tool
- Multiple container orchestration
- Network communication overhead

## Alternatives Considered
- Monolithic Flask app: Rejected due to scalability concerns
- Direct file polling: Rejected in favor of queue-based processing
- WebSocket-only status: Rejected in favor of SSE for simplicity