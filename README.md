# HashWrap - Secure Password Cracking Service

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue)](https://docker.com)
[![Security](https://img.shields.io/badge/Security-Hardened-green)](https://github.com/hackandbackpack/hashwrap)

**⚠️ AUTHORIZED USE ONLY**: This tool is designed exclusively for authorized penetration testing and security research. Users must obtain explicit written authorization before processing any password hashes.

## Overview

HashWrap transforms the powerful command-line hashcat tool into a secure, auditable, web-managed cracking service. Built for professional penetration testers and security researchers, it provides enterprise-grade security controls, comprehensive audit trails, and streamlined workflow management.

### Key Features

- **🔐 Enterprise Security**: Multi-factor authentication, role-based access control, audit logging
- **🚀 GPU Acceleration**: Full NVIDIA CUDA support with automatic GPU detection
- **📊 Real-time Monitoring**: Live job progress, system metrics, and performance dashboards  
- **🔔 Smart Notifications**: Slack and Discord integration with customizable event triggers
- **📈 Advanced Analytics**: Success rates, performance metrics, and detailed reporting
- **🏢 Compliance Ready**: Legal authorization tracking, immutable audit logs, data retention policies
- **🎯 Attack Profiles**: Pre-configured attack strategies (quick, balanced, thorough)
- **🔍 Auto-Detection**: Intelligent hash type identification with confidence scoring

## Quick Start

### One-Command Deployment

```bash
git clone https://github.com/hackandbackpack/hashwrap.git
cd hashwrap
./bootstrap.sh
```

That's it! The bootstrap script will:
- ✅ Check system requirements (Docker, NVIDIA toolkit)
- ✅ Generate secure secrets and certificates
- ✅ Create directory structure and sample configs
- ✅ Build and deploy all services with Docker Compose
- ✅ Verify service health and GPU availability

**Access your instance:** http://localhost (or https://localhost:8443 with SSL)

### Prerequisites

- **Docker & Docker Compose** (latest versions)
- **NVIDIA Container Toolkit** (for GPU acceleration)
- **8GB+ RAM** (recommended for intensive cracking jobs)
- **100GB+ Storage** (for wordlists, results, and job data)

## Architecture

HashWrap employs a microservices architecture designed for security, scalability, and reliability:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   React UI      │    │   FastAPI API    │    │  Celery Workers │
│   (Frontend)    │───▶│   (Backend)      │───▶│  (Job Execution)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │              ┌─────────▼─────────┐             │
         │              │   PostgreSQL      │             │
         │              │   (Database)      │             │
         │              └───────────────────┘             │
         │                        │                        │
         │              ┌─────────▼─────────┐    ┌────────▼─────────┐
         └──────────────┤      Redis        │    │     Hashcat      │
                        │   (Queue/Cache)   │    │  (GPU Processing)│
                        └───────────────────┘    └──────────────────┘
```

## Security Model

### Authentication & Authorization

- **Multi-Factor Authentication**: TOTP (Time-based One-Time Password) required
- **Role-Based Access Control**: Admin, Operator, Viewer permission levels
- **Session Management**: Secure HTTP-only cookies with CSRF protection
- **Account Lockout**: Automatic lockout after failed login attempts

### Data Protection

- **Default Masking**: All cracked passwords masked in UI and logs by default
- **Audit Trail**: Every password reveal generates immutable audit record
- **Secure Export**: Explicit export actions with full audit trail
- **Data Retention**: Configurable cleanup policies with secure deletion

## Quick Usage

### 1. Initial Setup
1. Create admin account at http://localhost
2. Enable 2FA authentication
3. Create project with client authorization details

### 2. Upload Hash Files
- Drag & drop files in web interface
- Supports MD5, SHA1, SHA256, NTLM, bcrypt, and more
- Automatic hash type detection

### 3. Run Cracking Jobs
- Choose attack profile (quick/balanced/thorough)
- Monitor real-time progress with GPU stats
- Control jobs (pause/resume/cancel)

### 4. View Results
- Search and filter crack results
- Export data (CSV/JSON) with audit logging
- Role-based password reveal

## Configuration Files

### hashwrap.yaml - Attack Profiles
```yaml
profiles:
  quick:
    description: "Fast dictionary attack"
    max_runtime: 1800
    attacks:
      - type: dictionary
        wordlist: "rockyou.txt"
        rules: "best64.rule"
```

### notifiers.yaml - Webhooks
```yaml
slack:
  enabled: true
  channels:
    general:
      webhook_url: "https://hooks.slack.com/your/webhook"
      events: [job_started, job_completed, password_cracked]
```

## API Access

Full OpenAPI documentation: http://localhost/api/v1/docs

```bash
# Authentication
curl -X POST "http://localhost/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password", "totp_code": "123456"}'

# Get jobs
curl -X GET "http://localhost/api/v1/jobs" \
  -H "Authorization: Bearer your-jwt-token"
```

## Monitoring

- **Health Check**: `GET /healthz`
- **Metrics**: `GET /metrics` (Prometheus format)
- **Logs**: Structured JSON logging with full context

## Development

```bash
# Backend development
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend development  
cd frontend && npm install
npm run dev

# Run tests
pytest backend/tests/
npm run test --prefix frontend
```

## Production Deployment

### Security Checklist
- [ ] Enable HTTPS with valid SSL certificates
- [ ] Configure reverse proxy security headers
- [ ] Set up database backups and monitoring
- [ ] Review security policies and access controls
- [ ] Configure external secrets management
- [ ] Set up log aggregation and alerting

### Docker Compose Production
```bash
# Use production configuration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Troubleshooting

### GPU Issues
```bash
# Check NVIDIA drivers
nvidia-smi

# Test Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

### Service Issues
```bash
# Check logs
docker-compose logs -f api worker

# Health status
curl http://localhost/healthz
```

## Security & Compliance

### Legal Requirements
- Written authorization required for all hash processing
- Client engagement ID tracking for audit compliance
- Comprehensive activity logging and retention policies

### Data Handling
- All passwords masked by default in logs and UI
- Explicit reveal actions create audit records
- Configurable data retention with secure deletion

## Support & Contributing

- **Issues**: Report bugs and request features on GitHub
- **Security**: Email security@hackandbackpack.com for vulnerabilities
- **Contributing**: See CONTRIBUTING.md for development guidelines

## License

MIT License - see LICENSE file for details.

---

**⚠️ IMPORTANT**: This tool is for authorized security testing only. Ensure proper authorization before processing any password hashes. Unauthorized use is illegal and unethical.

For questions and support: support@hackandbackpack.com