# Assumptions

This document records assumptions made during development where requirements were ambiguous or implementation details needed to be decided.

## Environment Assumptions

### Hardware
- **GPU Availability**: Assumes NVIDIA GPUs with CUDA support for hashcat acceleration
- **Storage**: Assumes sufficient disk space for wordlists, rules, and job data (default: 100GB minimum)
- **Memory**: Assumes minimum 8GB RAM for backend services, more for intensive cracking jobs

### Operating System
- **Container Runtime**: Assumes Docker with NVIDIA Container Toolkit installed
- **File Permissions**: Assumes ability to mount host directories with appropriate permissions
- **Network**: Assumes standard HTTP/HTTPS ports (80/443) available, or ability to configure alternatives

## Security Assumptions

### Authentication
- **2FA Enforcement**: All users must enable TOTP 2FA after first login (no bypass option)
- **Session Timeout**: Default 8-hour session timeout for security vs usability balance
- **Password Policy**: Minimum 12 characters with complexity requirements

### Authorization
- **Default Role**: New users default to 'viewer' role, must be promoted by admin
- **Admin Bootstrap**: First user created becomes admin automatically
- **Service Accounts**: No service account authentication initially (human users only)

### Data Handling
- **Retention Period**: Default 90-day retention for job data and audit logs
- **Mask by Default**: All cracked passwords masked in UI/logs unless explicitly revealed
- **Export Restrictions**: CSV/JSON exports require 'operator' or 'admin' role

## Business Logic Assumptions

### Hash Processing
- **Auto-Detection**: When hashcat --identify fails, fall back to filename/format heuristics
- **Duplicate Handling**: Identical hashes (same type) are de-duplicated automatically
- **Mixed Hash Files**: Files with multiple hash types are automatically split

### Job Management
- **Default Profile**: Jobs without specified profile use 'balanced' strategy
- **Concurrent Jobs**: Maximum 4 concurrent jobs per system (configurable)
- **Queue Priority**: FIFO processing with no priority queues initially

### Notifications
- **Event Frequency**: Progress notifications sent every 5 minutes during job execution
- **Webhook Timeout**: 10-second timeout for notification webhook delivery
- **Retry Policy**: 3 retries with exponential backoff for failed notifications

## Technical Assumptions

### Database
- **Migration Strategy**: Alembic migrations applied automatically on container startup
- **Connection Pooling**: Default PostgreSQL connection pool size of 20
- **Backup Strategy**: Database backups are handled by external system (not application concern)

### File System
- **Upload Directory**: Assumes `/data/uploads` is writable and has sufficient space
- **Wordlist Management**: Wordlists and rules provided by admin, not auto-downloaded
- **Result Cleanup**: Old job results cleaned up based on retention policy

### Integration
- **Hashcat Version**: Assumes hashcat 6.2.0 or later with --status-json support
- **Container Registry**: Uses Docker Hub for base images (assumes internet access during build)
- **External Dependencies**: Redis and PostgreSQL provided via Docker Compose

## Deployment Assumptions

### Development
- **Local Development**: Developers use SQLite for local development database
- **Hot Reload**: API and UI support hot reload for development productivity
- **Test Data**: Includes sample hash files and test data for development

### Production
- **Reverse Proxy**: Assumes nginx or similar reverse proxy handles TLS termination
- **Secrets Management**: Environment variables provided via Docker secrets or similar
- **Monitoring**: External monitoring system consumes /metrics endpoint

### Scaling
- **Single Node**: Initial deployment targets single-node operation
- **Horizontal Scaling**: Worker scaling via Docker Compose scale command
- **Load Balancing**: Multiple API instances can be load balanced (stateless design)

## Compliance Assumptions

### Legal
- **Authorized Use**: All users acknowledge authorized use via legal banner
- **Engagement Tracking**: Client/engagement information required for audit compliance
- **Data Location**: Data stored in region appropriate for client requirements

### Audit
- **Log Retention**: Audit logs retained for minimum 1 year
- **Immutability**: Audit logs write-only, no deletion capability
- **Export Format**: Audit logs exportable in standard formats (JSON, CSV)

These assumptions will be validated with users and updated as requirements are clarified.