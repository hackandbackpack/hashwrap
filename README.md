# HashWrap - Penetration Testing Hash Cracker

**🎯 Web interface for hash cracking during penetration tests with automatic Docker setup**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Auto--Install-blue)](https://docker.com)
[![Security](https://img.shields.io/badge/Security-Pentest--Ready-green)](https://github.com/hackandbackpack/hashwrap)

**⚠️ AUTHORIZED USE ONLY**: This tool is designed exclusively for authorized penetration testing and security research. Users must obtain explicit written authorization before processing any password hashes.

## ⚡ Quick Start

```bash
# Clone and run setup (auto-installs Docker if needed)
git clone https://github.com/hackandbackpack/hashwrap.git
cd hashwrap
./setup.sh

# Access at: http://localhost:5000
# Login: admin / admin
```

## 🎯 What This Does

- **Web Interface**: Upload hash files, view progress, get results
- **Auto Detection**: Automatically detects MD5, SHA1, SHA256, NTLM, bcrypt, etc.
- **GPU Acceleration**: Uses your NVIDIA GPU if available
- **Real-time Progress**: See cracking progress live
- **Export Results**: Download cracked passwords as CSV
- **Smart Setup**: Automatically installs Docker, Docker Compose, and NVIDIA support
- **Simple Deployment**: Single container, no complex configuration

## 📁 File Structure

```
hashwrap/
├── webapp/              # Simplified Flask web app
│   ├── app_fixed.py    # Main application with comprehensive error handling
│   ├── hashcat_worker.py # Background worker for job processing
│   └── templates/      # Web interface templates
├── data/
│   ├── uploads/        # Drop hash files here
│   └── results/        # Cracked passwords stored here
├── wordlists/          # Add your wordlists here
└── setup.sh            # One-command setup with auto Docker install
```

## 🔧 Usage

### 1. Upload Hash Files
- Click "Upload Hash File" in web interface
- Drag & drop your .txt, .hash, or .lst files
- System auto-detects hash type

### 2. Monitor Progress
- View real-time cracking progress
- See GPU utilization and speed
- Get notifications when jobs complete

### 3. Get Results
- View cracked passwords (hidden by default)
- Export to CSV for reporting
- Results saved automatically

## 📋 Supported Hash Types

| Hash Type | Example | Auto-Detect |
|-----------|---------|-------------|
| MD5 | `5d41402abc4b2a76b9719d911017c592` | ✅ |
| SHA1 | `aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d` | ✅ |
| SHA256 | `ef537f25c895bfa782526529a9b63d97aa631564d5d789c2b765448c8635fb6c` | ✅ |
| NTLM | `admin:1001:aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0:::` | ✅ |
| bcrypt | `$2b$12$GhvMmNVjRW29ulnudl5fGeJrYKs.Ja4u7eFVdgfO3CnhSwI7wacay` | ✅ |
| MD5crypt | `$1$salt$qJH7.N4xYta3aEG/dfqo/0` | ✅ |
| SHA512crypt | `$6$salt$IxDD3jeSOb5eB1CX5LBsqZFVkJdido3OUILO5Ifz5iwMuTS4XMS130MTSuDDl3aCI6WouIL9AjRbLCelDCy.g.` | ✅ |

## ⚙️ System Requirements

**The setup.sh script automatically handles most requirements:**
- **Linux**: Ubuntu, Debian, Kali, RHEL, CentOS, Fedora, Arch (auto-detected)
- **Memory**: 2GB+ RAM (4GB+ recommended for intensive jobs)
- **Storage**: 5GB+ available space (more for large wordlists)
- **Docker**: Automatically installed if not present
- **GPU Support**: Auto-detects and configures GPU vs CPU-only mode
- **Virtual Machines**: Automatically uses CPU-only configuration

### Add Custom Wordlists
```bash
# Add your wordlists to the wordlists directory
cp /path/to/rockyou.txt wordlists/
cp /path/to/custom.txt wordlists/

# The setup creates a basic wordlist automatically
```

### Check GPU Support
```bash
# Test GPU access after setup
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

## 🐳 Docker Commands

The setup script automatically chooses the right configuration based on your system:

**GPU-enabled systems:**
```bash
# Start HashWrap with GPU acceleration
docker-compose -f docker-compose.gpu.yml up -d

# View logs
docker-compose -f docker-compose.gpu.yml logs -f

# Stop HashWrap
docker-compose -f docker-compose.gpu.yml down
```

**CPU-only systems (VMs, non-NVIDIA):**
```bash
# Start HashWrap in CPU-only mode  
docker-compose -f docker-compose.cpu.yml up -d

# View logs
docker-compose -f docker-compose.cpu.yml logs -f

# Stop HashWrap
docker-compose -f docker-compose.cpu.yml down
```

**Manual GPU detection:**
```bash
# Test if GPU acceleration is available
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

## 🚀 Performance Tips

1. **Use GPU**: The setup script automatically installs NVIDIA Container Toolkit for 10-100x speed boost
2. **Good Wordlists**: Use rockyou.txt or other comprehensive wordlists
3. **File Size**: Break large hash files into smaller chunks (< 1M lines each)
4. **Resource Monitoring**: Monitor GPU temperature during long jobs

## 🔍 Troubleshooting

### Setup Issues

**"Docker installation failed"**
```bash
# Check setup logs
cat setup.log

# Manual Docker install (if needed)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**"Permission denied"**
```bash
# Fix file permissions
sudo chown -R $USER:$USER data/ wordlists/

# Add user to docker group (may require logout/login)
sudo usermod -aG docker $USER
```

### Runtime Issues

**"No GPU detected"**
```bash
# The setup script handles this, but if needed:
sudo apt install nvidia-container-toolkit
sudo systemctl restart docker
```

**"Hashcat not found"**
```bash
# Rebuild container
docker-compose -f docker-compose.simple.yml build --no-cache
```

### Logs and Debugging
```bash
# View detailed logs
docker-compose -f docker-compose.simple.yml logs hashwrap

# Access container shell
docker-compose -f docker-compose.simple.yml exec hashwrap bash

# Check hashcat version
docker-compose -f docker-compose.simple.yml exec hashwrap hashcat --version

# System validation
python3 webapp/validate_deployment.py
```

## 🧪 Testing

The setup includes comprehensive testing tools:

```bash
# Pre-deployment validation
cd webapp
python3 validate_deployment.py

# Full system test
python3 test_system.py http://localhost:5000
```

## 🚀 Production Deployment

For production deployment on Linux servers with Apache:

```bash
# Use the production deployment files
cd webapp/deploy
sudo chmod +x install-linux.sh
sudo ./install-linux.sh

# See webapp/DEPLOYMENT.md for full guide
```

## 🎯 Perfect For

- **Penetration Testing**: Quick hash cracking during engagements
- **CTF Competitions**: Fast setup and reliable cracking
- **Security Research**: Simple codebase to understand and modify
- **Small Teams**: No complex user management needed
- **Training**: Educational tool for understanding hash cracking

## 🏗️ Architecture

Simple, focused architecture designed for penetration testers:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Interface │    │   Flask App      │    │  Worker Daemon  │
│   (Browser)     │───▶│   (Python)       │───▶│  (Hashcat Jobs) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │              ┌─────────▼─────────┐             │
         │              │   SQLite DB       │             │
         │              │   (Job Storage)   │             │
         │              └───────────────────┘             │
         │                                                │
         └────────────────────────────────────────────────┘
                           File System
                    (Uploads, Results, Wordlists)
```

**Key Features:**
- **Thread-Safe**: Comprehensive database locking and error handling
- **Secure**: File validation, session management, rate limiting
- **Monitored**: Extensive logging with checkpoint system
- **Validated**: Pre-deployment checks and system testing
- **Production-Ready**: Apache deployment configuration included

## ⚠️ Security Notes

- **Change default credentials** (admin/admin) immediately in production
- **Use only for authorized testing** - never crack hashes without permission
- **Secure the web interface** - don't expose to the internet without proper security
- **Monitor resource usage** - hash cracking is resource-intensive
- **Regular updates** - keep Docker images and system packages updated

## 📞 Support & Contributing

- **Issues**: Report bugs and request features on GitHub
- **Security**: Email security@hackandbackpack.com for vulnerabilities  
- **Documentation**: See webapp/DEPLOYMENT.md for production setup

## 📄 License

MIT License - see LICENSE file for details.

---

**🔓 Ready to crack some hashes? Run `./setup.sh` and get started!**

**⚠️ IMPORTANT**: This tool is for authorized security testing only. Ensure proper authorization before processing any password hashes. Unauthorized use is illegal and unethical.