# HashWrap - Simple Pentest Edition

**🎯 Simplified web interface for hash cracking during penetration tests**

> **Note**: This is the simplified version focused on essential pentest workflow. 
> For the full enterprise version, see the main README.md.

## ⚡ Quick Start

```bash
# One command deployment (auto-installs Docker if needed)
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
- **Simple Setup**: Single container, no complex configuration

## 📁 File Structure

```
hashwrap/
├── webapp/              # Simplified Flask web app
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

## ⚙️ Configuration

### Add Custom Wordlists
```bash
# Add your wordlists to the wordlists directory
cp /path/to/rockyou.txt wordlists/
cp /path/to/custom.txt wordlists/
```

### GPU Requirements
- NVIDIA GPU with CUDA support
- NVIDIA Container Toolkit installed
- Docker with GPU support

### Check GPU Support
```bash
# Test GPU access
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

## 🐳 Docker Commands

```bash
# Start HashWrap
docker-compose -f docker-compose.simple.yml up -d

# View logs
docker-compose -f docker-compose.simple.yml logs -f

# Stop HashWrap
docker-compose -f docker-compose.simple.yml down

# Restart after changes
docker-compose -f docker-compose.simple.yml restart
```

## 🚀 Performance Tips

1. **Use GPU**: Install NVIDIA Container Toolkit for 10-100x speed boost
2. **Good Wordlists**: Use rockyou.txt or other comprehensive wordlists
3. **File Size**: Break large hash files into smaller chunks
4. **Resource Monitoring**: Monitor GPU temperature during long jobs

## 🔍 Troubleshooting

### Common Issues

**"No GPU detected"**
```bash
# Install NVIDIA Container Toolkit
sudo apt install nvidia-container-toolkit
sudo systemctl restart docker
```

**"Permission denied"**
```bash
# Fix file permissions
sudo chown -R $USER:$USER data/ wordlists/
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
```

## 📊 What's Different from Full Version?

**Simplified Version (This):**
- ✅ Single container deployment
- ✅ SQLite database (no PostgreSQL)
- ✅ Basic authentication (username/password)
- ✅ Essential features only
- ✅ ~600 lines of code

**Full Enterprise Version:**
- 🏢 Microservices architecture
- 🏢 PostgreSQL + Redis
- 🏢 Advanced RBAC + 2FA
- 🏢 Comprehensive audit logging
- 🏢 17,000+ lines of code

## 🎯 Perfect For

- **Penetration Testing**: Quick hash cracking during engagements
- **CTF Competitions**: Fast setup and reliable cracking
- **Learning**: Simple codebase to understand and modify
- **Small Teams**: No complex user management needed

## ⚠️ Security Notes

- **Change default credentials** (admin/admin) in production
- **Use only for authorized testing** - never crack hashes without permission
- **Secure the web interface** - don't expose to the internet without proper security

---

**🔓 Ready to crack some hashes? Run `./setup.sh` and get started!**