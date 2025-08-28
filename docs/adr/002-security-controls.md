# ADR-002: Security Controls

## Status
Accepted

## Context
The service handles sensitive password hashes and operates in pentesting environments requiring strong security controls, audit trails, and legal compliance.

## Decision

### Authentication & Authorization
- **Multi-factor Authentication**: Username/password + TOTP (pyotp)
- **Session Management**: Secure HTTP-only cookies with CSRF protection
- **Role-Based Access Control**: Three roles with specific permissions:
  - `admin`: Full system access, user management, configuration
  - `operator`: Job management, password reveal, export capabilities
  - `viewer`: Read-only access to jobs and redacted results

### Input Security
- **File Validation**: Extension whitelist, MIME type verification, size limits
- **Path Traversal Protection**: Strict path validation for all file operations
- **Content Sanitization**: Hash format validation, line count limits
- **Archive Handling**: Safe zip extraction with path validation

### Data Protection
- **Default Masking**: All cracked passwords masked by default in UI and logs
- **Reveal Auditing**: Password reveals require appropriate role and generate audit records
- **Secure Export**: Explicit export actions with full audit trail
- **Data Retention**: Configurable retention periods with secure deletion

### Network Security
- **HTTPS Only**: All communications encrypted in transit
- **CSP Headers**: Strict Content Security Policy preventing XSS
- **Rate Limiting**: Per-endpoint and per-user request limiting
- **CSRF Protection**: Double-submit cookie pattern

### Legal Compliance
- **Authorization Banner**: Required acknowledgment of authorized use
- **Engagement Tracking**: Client/engagement ID required for all jobs
- **Audit Logging**: Immutable logs of all sensitive operations
- **Data Classification**: Clear marking of sensitive data throughout system

## Implementation
- FastAPI security dependencies for role checking
- SQLAlchemy audit mixins for automatic logging
- Secure cookie configuration with appropriate flags
- Input validation using Pydantic models with strict typing

## Consequences
- Strong security posture appropriate for pentesting tools
- Full audit trail for compliance requirements
- Slight performance overhead from validation and logging
- Clear separation of privileges reduces attack surface