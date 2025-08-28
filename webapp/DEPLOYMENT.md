# HashWrap Production Deployment Guide

Production deployment guide for HashWrap web interface with Apache and mod_wsgi.

## 🎯 Quick Start

For automated deployment on Ubuntu/Debian or RHEL/CentOS:

```bash
# Clone and run installer
git clone <repository>
cd hashwrap/webapp/deploy
sudo chmod +x install-linux.sh
sudo ./install-linux.sh
```

Access at: `https://hashwrap.local/` (admin/admin)

## 📋 System Requirements

### Minimum Hardware
- **CPU**: 2+ cores (4+ recommended for GPU acceleration)
- **RAM**: 4GB minimum (8GB+ recommended)
- **Storage**: 20GB+ available space
- **GPU**: NVIDIA GPU (optional, for hashcat acceleration)

### Operating System
- **Ubuntu 20.04+** or **Debian 11+**
- **RHEL 8+** or **CentOS Stream 8+**
- Other Linux distributions (manual configuration required)

### Dependencies
- **Apache 2.4+** with mod_wsgi
- **Python 3.8+**
- **Hashcat 6.0+**
- **SQLite 3**
- **OpenSSL** (for HTTPS)

## 🚀 Manual Installation

### 1. System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies (Ubuntu/Debian)
sudo apt install -y apache2 libapache2-mod-wsgi-py3 python3 python3-venv \
    python3-pip sqlite3 hashcat nvidia-smi curl openssl git

# For RHEL/CentOS
sudo yum install -y httpd python3-mod_wsgi python3 python3-pip \
    sqlite curl openssl git
```

### 2. Application Setup

```bash
# Create service user
sudo useradd --system --shell /bin/false --home-dir /opt/hashwrap \
    --create-home hashwrap

# Copy application files
sudo mkdir -p /opt/hashwrap/webapp
sudo cp -r hashwrap/webapp/* /opt/hashwrap/webapp/

# Set up Python environment
sudo python3 -m venv /opt/hashwrap/venv
sudo /opt/hashwrap/venv/bin/pip install flask werkzeug psutil requests

# Create directories
sudo mkdir -p /opt/hashwrap/webapp/data/{uploads,results}
sudo mkdir -p /opt/hashwrap/webapp/logs
sudo mkdir -p /var/log/hashwrap

# Set permissions
sudo chown -R hashwrap:hashwrap /opt/hashwrap
sudo chown -R hashwrap:hashwrap /var/log/hashwrap
sudo chmod 750 /opt/hashwrap/webapp/data
```

### 3. Apache Configuration

```bash
# Enable Apache modules
sudo a2enmod ssl rewrite headers deflate wsgi

# Copy virtual host configuration
sudo cp deploy/apache-hashwrap.conf /etc/apache2/sites-available/

# Enable the site
sudo a2ensite apache-hashwrap.conf
sudo a2dissite 000-default.conf

# Generate SSL certificate (self-signed for testing)
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/hashwrap.key \
    -out /etc/ssl/certs/hashwrap.crt \
    -subj "/C=US/ST=State/L=City/O=PenTest/CN=hashwrap.local"

# Set certificate permissions
sudo chmod 600 /etc/ssl/private/hashwrap.key
sudo chmod 644 /etc/ssl/certs/hashwrap.crt
```

### 4. Worker Service Setup

```bash
# Install systemd service
sudo cp deploy/hashwrap-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hashwrap-worker
```

### 5. Database Initialization

```bash
# Initialize database as service user
sudo -u hashwrap bash -c '
cd /opt/hashwrap/webapp
source /opt/hashwrap/venv/bin/activate
python3 -c "from app_fixed import init_db; init_db()"
'
```

### 6. Start Services

```bash
# Start Apache
sudo systemctl restart apache2

# Start worker
sudo systemctl start hashwrap-worker

# Check status
sudo systemctl status apache2
sudo systemctl status hashwrap-worker
```

## 🔧 Configuration

### Environment Variables

Create `/opt/hashwrap/webapp/.env`:

```bash
FLASK_ENV=production
HASHWRAP_SECRET_KEY=your-secret-key-change-this
HASHWRAP_DOMAIN=hashwrap.local
```

### Wordlists

```bash
# Download rockyou.txt (recommended)
sudo wget https://github.com/danielmiessler/SecLists/raw/master/Passwords/Leaked-Databases/rockyou.txt.tar.gz
sudo tar -xzf rockyou.txt.tar.gz -C /opt/hashwrap/webapp/wordlists/
sudo chown hashwrap:hashwrap /opt/hashwrap/webapp/wordlists/rockyou.txt
```

### Firewall Configuration

```bash
# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8080/tcp  # Development port (optional)
```

## 🛡️ Security Hardening

### 1. Change Default Credentials

**CRITICAL**: Change admin password immediately after deployment:

1. Login at `https://hashwrap.local/`
2. Use credentials: `admin` / `admin`
3. Change password in user management (if implemented)

### 2. SSL/TLS Configuration

For production, replace self-signed certificate:

```bash
# Using Let's Encrypt (recommended)
sudo apt install certbot python3-certbot-apache
sudo certbot --apache -d hashwrap.local

# Or use commercial certificate
sudo cp your-certificate.crt /etc/ssl/certs/hashwrap.crt
sudo cp your-private-key.key /etc/ssl/private/hashwrap.key
```

### 3. File Permissions

```bash
# Secure application files
sudo find /opt/hashwrap -type f -exec chmod 644 {} \;
sudo find /opt/hashwrap -type d -exec chmod 755 {} \;

# Secure sensitive files
sudo chmod 600 /opt/hashwrap/webapp/hashwrap.db
sudo chmod 600 /opt/hashwrap/webapp/secret.key
```

### 4. System Updates

```bash
# Enable automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

## 📊 Monitoring & Maintenance

### Log Files

- **Application**: `/var/log/hashwrap/hashwrap.log`
- **Apache Error**: `/var/log/apache2/hashwrap_error.log`
- **Apache Access**: `/var/log/apache2/hashwrap_access.log`
- **Worker Service**: `journalctl -u hashwrap-worker`

### System Health

```bash
# Check system status
sudo python3 /opt/hashwrap/webapp/validate_deployment.py

# Monitor services
sudo systemctl status apache2
sudo systemctl status hashwrap-worker

# Check resources
htop
df -h
```

### Regular Maintenance

```bash
# Rotate logs
sudo logrotate -f /etc/logrotate.conf

# Clean old jobs (if implemented)
sudo -u hashwrap python3 /opt/hashwrap/webapp/cleanup_old_jobs.py

# Update system
sudo apt update && sudo apt upgrade
```

## 🧪 Testing

### Pre-deployment Validation

```bash
cd /opt/hashwrap/webapp
sudo -u hashwrap python3 validate_deployment.py
```

### Full System Test

```bash
cd /opt/hashwrap/webapp
sudo -u hashwrap python3 test_system.py https://hashwrap.local
```

### Manual Testing Checklist

- [ ] Web interface loads at HTTPS URL
- [ ] Login works with admin credentials
- [ ] File upload accepts valid hash files
- [ ] Dashboard shows job status
- [ ] Worker service processes jobs
- [ ] Results are displayed correctly
- [ ] Logout clears session

## 🔍 Troubleshooting

### Common Issues

#### "Internal Server Error"
```bash
# Check Apache error logs
sudo tail -f /var/log/apache2/hashwrap_error.log

# Check Python path and permissions
sudo -u hashwrap python3 /opt/hashwrap/webapp/hashwrap.wsgi
```

#### Worker Not Processing Jobs
```bash
# Check worker service
journalctl -u hashwrap-worker -f

# Check hashcat binary
sudo -u hashwrap hashcat --version

# Check database permissions
ls -la /opt/hashwrap/webapp/hashwrap.db
```

#### High CPU Usage
```bash
# Check running processes
ps aux | grep hashcat

# Adjust worker settings in hashcat_worker.py
# Reduce MAX_CONCURRENT_JOBS
```

#### Permission Denied
```bash
# Fix ownership
sudo chown -R hashwrap:hashwrap /opt/hashwrap
sudo chown -R hashwrap:hashwrap /var/log/hashwrap

# Check SELinux (RHEL/CentOS)
sudo setsebool -P httpd_can_network_connect 1
sudo setsebool -P httpd_execmem 1
```

### Debug Mode

For development/debugging:

```bash
# Stop production services
sudo systemctl stop apache2
sudo systemctl stop hashwrap-worker

# Run in debug mode
cd /opt/hashwrap/webapp
source /opt/hashwrap/venv/bin/activate
python3 app_fixed.py
```

## 🎯 Performance Optimization

### Apache Tuning

Edit `/etc/apache2/conf-available/performance.conf`:

```apache
# Worker process optimization
StartServers         2
MinSpareServers      2
MaxSpareServers      5
MaxRequestWorkers    150
ThreadsPerChild      25

# Keep-alive settings
KeepAlive On
MaxKeepAliveRequests 100
KeepAliveTimeout 5

# Compression
LoadModule deflate_module modules/mod_deflate.so
<Location />
    SetOutputFilter DEFLATE
</Location>
```

### Database Optimization

```bash
# Optimize SQLite
sudo -u hashwrap sqlite3 /opt/hashwrap/webapp/hashwrap.db "VACUUM;"
sudo -u hashwrap sqlite3 /opt/hashwrap/webapp/hashwrap.db "PRAGMA optimize;"
```

### GPU Configuration

```bash
# Check GPU status
nvidia-smi

# Configure hashcat GPU settings
sudo -u hashwrap hashcat --benchmark
```

## 🚨 Security Considerations

### Network Security
- Use firewall (ufw, iptables)
- Consider VPN for remote access
- Enable fail2ban for brute force protection
- Use strong SSL/TLS configuration

### Application Security
- Change default passwords
- Regular security updates
- Monitor access logs
- Implement rate limiting
- Use secure file upload validation

### Data Security
- Encrypt sensitive data at rest
- Secure database backups
- Implement data retention policies
- Monitor for unauthorized access

## 📞 Support

For issues and questions:

1. Check this deployment guide
2. Review log files for errors
3. Run validation scripts
4. Check GitHub issues
5. Consult hashcat documentation

## 🔄 Updates

To update the application:

```bash
# Backup current installation
sudo cp -r /opt/hashwrap/webapp /opt/hashwrap/webapp.backup

# Update application files
sudo cp -r new-version/* /opt/hashwrap/webapp/

# Restart services
sudo systemctl restart apache2
sudo systemctl restart hashwrap-worker

# Validate deployment
sudo -u hashwrap python3 /opt/hashwrap/webapp/validate_deployment.py
```

---

**⚠️ Security Notice**: This is a penetration testing tool. Use only in authorized environments. Always follow responsible disclosure practices.