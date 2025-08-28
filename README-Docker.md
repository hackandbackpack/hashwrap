# HashWrap Docker Configuration

This document provides comprehensive instructions for deploying HashWrap using Docker with security hardening, GPU support, and production-ready features.

## Quick Start

### One-Command Bootstrap

**Linux/macOS:**
```bash
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

**Windows PowerShell:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\scripts\bootstrap.ps1
```

This will automatically:
- Check prerequisites and GPU support
- Generate secure passwords and secrets
- Create directory structure and configuration
- Build all Docker images
- Start all services with proper dependencies
- Run database migrations
- Display service URLs and status

## Architecture Overview

The Docker configuration includes the following services:

### Core Services
- **PostgreSQL** - Primary database with security hardening
- **Redis** - Message broker and caching layer
- **FastAPI Backend** - API service with authentication
- **React Frontend** - Modern TypeScript UI with Nginx
- **Celery Workers** - Background job processing with hashcat
- **Celery Beat** - Scheduled task management
- **Nginx** - Reverse proxy with security headers

### Optional Services
- **Prometheus** - Metrics collection and monitoring
- **PgAdmin** - Database administration (development)
- **Flower** - Celery monitoring (development)
- **Mailhog** - Email testing (development)

## Prerequisites

### Required
- Docker Engine 20.10+ or Docker Desktop
- Docker Compose V2
- 8GB+ RAM (16GB+ recommended)
- 10GB+ free disk space

### For GPU Support
- NVIDIA GPU with CUDA support
- NVIDIA Container Toolkit
- NVIDIA drivers 470.57.02+

### Windows Specific
- Windows 10/11 with WSL2
- Docker Desktop with WSL2 backend
- PowerShell 5.1 or PowerShell Core 7.0+

## Configuration

### Environment Variables

Copy `.env.template` to `.env` and customize:

```bash
cp .env.template .env
```

Key settings to modify:
- `POSTGRES_PASSWORD` - Database password
- `REDIS_PASSWORD` - Redis password  
- `JWT_SECRET` - Authentication secret
- `CORS_ORIGINS` - Allowed frontend origins
- `CUDA_VISIBLE_DEVICES` - GPU device selection

### Secrets Management

Sensitive data is stored in Docker secrets:
- `secrets/db_password.txt` - Database password
- `secrets/redis_password.txt` - Redis password
- `secrets/jwt_secret.txt` - JWT signing key

## Deployment Modes

### Production Deployment

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Check status
docker compose ps
```

### Development Deployment

```bash
# Start with development overrides
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Enable development tools
docker compose --profile dev-tools up -d

# View logs with real-time updates
docker compose logs -f backend worker
```

## GPU Configuration

### NVIDIA Container Toolkit Installation

**Ubuntu/Debian:**
```bash
# Add NVIDIA package repositories
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install nvidia-container-toolkit
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Restart Docker
sudo systemctl restart docker
```

**Windows (Docker Desktop):**
1. Install NVIDIA GPU drivers
2. Enable GPU support in Docker Desktop settings
3. Restart Docker Desktop

### GPU Device Selection

Configure visible GPUs in `.env`:
```bash
CUDA_VISIBLE_DEVICES=0,1,2,3  # Use specific GPUs
# or
CUDA_VISIBLE_DEVICES=all      # Use all GPUs
```

### Testing GPU Support

```bash
# Test NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi

# Check GPU in HashWrap worker
docker compose exec worker nvidia-smi
```

## Security Features

### Container Security
- **Non-root users** - All services run as non-root
- **Read-only root filesystem** - Where applicable
- **Security contexts** - Capability drops and security options
- **Network segmentation** - Separate frontend/backend networks
- **Resource limits** - Memory and CPU constraints

### Secret Management
- **Docker secrets** - Sensitive data stored securely
- **Environment isolation** - Production vs development configs
- **File permissions** - Restricted access to secret files

### Network Security
- **Nginx security headers** - XSS, CSRF, clickjacking protection
- **Rate limiting** - API and authentication endpoints
- **CORS policies** - Controlled cross-origin access
- **SSL/TLS ready** - Certificate mounting support

## Service Management

### Starting Services

```bash
# All services
docker compose up -d

# Specific services
docker compose up -d database redis backend

# With specific profiles
docker compose --profile monitoring up -d
```

### Scaling Workers

```bash
# Scale worker instances
docker compose up -d --scale worker=3

# Scale specific queues
docker compose run --rm worker celery -A celery_app worker -Q hashcat --concurrency=1
```

### Health Checks

```bash
# Check all services
docker compose ps

# Health check endpoints
curl http://localhost:80/health
curl http://localhost:8000/health
```

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend

# Tail logs
docker compose logs -f --tail=100 worker
```

### Database Management

```bash
# Access PostgreSQL
docker compose exec database psql -U hashwrap -d hashwrap

# Run migrations
docker compose exec backend python -m alembic upgrade head

# Create admin user (if supported)
docker compose exec backend python -m app.cli create-admin
```

## Monitoring and Metrics

### Prometheus Metrics

Enable monitoring profile:
```bash
docker compose --profile monitoring up -d
```

Access Prometheus at http://localhost:9090

### Service Logs

Centralized logging configuration in `docker-compose.yml`:
- JSON structured logging
- Log rotation and retention
- Service-specific log levels

### Celery Monitoring

Development environment includes Flower:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev-tools up -d
```

Access Flower at http://localhost:5555

## Backup and Maintenance

### Database Backup

```bash
# Create backup
docker compose exec database pg_dump -U hashwrap hashwrap > backup.sql

# Restore backup  
docker compose exec -T database psql -U hashwrap -d hashwrap < backup.sql
```

### Volume Management

```bash
# List volumes
docker volume ls | grep hashwrap

# Backup volume
docker run --rm -v hashwrap_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-backup.tar.gz /data

# Clean up unused volumes
docker volume prune
```

### Log Rotation

Configure log rotation in production:
```bash
# Add to crontab
0 2 * * * docker system prune -f --filter "until=72h"
```

## Troubleshooting

### Common Issues

**Database Connection Issues:**
```bash
# Check database status
docker compose exec database pg_isready -U hashwrap

# Reset database
docker compose down -v
docker volume rm hashwrap_postgres_data
docker compose up -d
```

**GPU Not Detected:**
```bash
# Check NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi

# Verify container toolkit
sudo docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

**Permission Issues:**
```bash
# Fix volume permissions
sudo chown -R 1001:1001 data/
```

**Memory Issues:**
```bash
# Check container resource usage
docker stats

# Increase memory limits in docker-compose.yml
```

### Debug Mode

Enable debug logging:
```bash
# Set environment
export DEBUG=true
export LOG_LEVEL=DEBUG

# Or modify .env file
echo "DEBUG=true" >> .env
echo "LOG_LEVEL=DEBUG" >> .env

# Restart services
docker compose restart
```

### Service Dependencies

If services fail to start in order:
```bash
# Stop all services
docker compose down

# Start core services first
docker compose up -d database redis

# Wait and start others
sleep 10
docker compose up -d
```

## Performance Tuning

### Database Optimization

PostgreSQL is configured with performance settings in `init-db.sql`. For high-load environments, consider:

- Increasing `shared_buffers`
- Tuning `work_mem` and `maintenance_work_mem`
- Adjusting `max_connections`
- Enabling connection pooling

### Redis Optimization

Redis is configured with:
- Memory limits and eviction policies
- Persistence settings for durability
- Connection pooling

### Worker Optimization

Celery workers are configured for:
- Optimal concurrency per queue type
- Memory limits to prevent leaks
- Task routing for efficiency

### Nginx Optimization

Nginx includes:
- Gzip compression
- Static file caching
- Connection keep-alive
- Buffer optimization

## Security Considerations

### Network Security
- Internal networks isolate backend services
- Frontend network only exposes necessary services
- Rate limiting prevents abuse

### Container Security
- All containers run as non-root users
- Read-only root filesystems where possible
- Minimal base images (Alpine Linux)
- Regular security updates

### Data Protection
- Secrets stored in Docker secrets
- Database encryption at rest (configurable)
- SSL/TLS termination at Nginx
- Audit logging enabled

### Access Control
- Role-based authentication
- API key management
- Session management
- CSRF protection

## Maintenance Tasks

### Regular Updates

```bash
# Update images
docker compose pull

# Rebuild and restart
docker compose up -d --build

# Clean old images
docker image prune -f
```

### Log Management

```bash
# View log sizes
docker system df

# Clean logs
docker container prune -f
```

### Database Maintenance

```bash
# Vacuum database
docker compose exec database psql -U hashwrap -d hashwrap -c "VACUUM ANALYZE;"

# Check database size
docker compose exec database psql -U hashwrap -d hashwrap -c "SELECT pg_size_pretty(pg_database_size('hashwrap'));"
```

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Docker and container logs
3. Check system resources and requirements
4. Consult the main HashWrap documentation