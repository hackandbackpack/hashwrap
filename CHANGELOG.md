# Hashwrap Changelog

## v3.0.1 - Compatibility Update (2025-01-14)

### Added
- Support for 20+ new hash types for hashcat v7.0.0 compatibility
  - Argon2 variants (argon2i/d/id)
  - Cryptocurrency wallets (Ethereum, Bitcoin, MetaMask)
  - Modern encryption (LUKS2, Ansible Vault, ZIP3 AES-256)
  - Cloud services (Okta, MongoDB SCRAM, Microsoft Online)
  - Protocols (SNMPv3, OpenSSH keys, GPG keys)
  - JWT token support
- Version detection and compatibility checking in resource monitor
- Detailed COMPATIBILITY.md documentation
- hashcat version information in system checks

### Updated
- Hash pattern database expanded from 20 to 40+ formats
- Resource monitor reports hashcat version and capabilities
- README includes version compatibility information

### Fixed
- Ensured full compatibility with hashcat v6.2.6 and v7.0.0
- Version parsing handles various hashcat version formats

### Compatibility
- Minimum required: hashcat v6.0.0
- Tested with: hashcat v6.2.6 (current stable)
- Future ready: hashcat v7.0.0 (upcoming release)

## v3.0.0 - Security & Hot-Reload Update

### 🔒 Security Enhancements

#### Critical Fixes
- **Removed sudo requirement** - Runs as regular user with modern hashcat
- **Command injection prevention** - All subprocess commands properly sanitized with shlex
- **Path traversal protection** - File operations restricted to allowed directories
- **Replaced pickle with JSON** - Eliminated arbitrary code execution vulnerability
- **Secure file operations** - Atomic writes, proper permissions (0600), secure deletion

#### Input Validation
- Hash format validation with regex patterns
- Session ID format enforcement  
- Attack name sanitization
- File path validation and sandboxing
- Size limits to prevent memory exhaustion

#### New Security Module (`core/security.py`)
- `SecurityValidator` - Comprehensive input validation
- `SecureFileOperations` - Safe file I/O with streaming support
- `CommandBuilder` - Secure hashcat command construction

### 🔄 Hot-Reload Feature

#### Real-time Hash Addition
- Add hashes without stopping the cracking process
- Three methods supported:
  1. Append to original hash file
  2. Drop files in `.hashwrap_sessions/incoming_hashes/`
  3. CLI command: `add-hashes SESSION_ID file.txt`

#### Implementation (`core/hash_watcher.py`)
- `HashFileWatcher` - Monitors files for changes
- `HashReloader` - Coordinates with attack orchestrator
- Thread-safe hash addition to running sessions
- Automatic injection of quick attacks for new hashes

### 📊 Enhanced Hash Manager
- Thread-safe operations with locking
- Dynamic hash addition support
- New method: `add_hashes_dynamically()`
- Queue-based notification system

### 🚀 Improved Main Application (`hashwrap_v3.py`)
- No sudo check - works with user permissions
- Integrated security validation throughout
- Hot-reload setup and monitoring
- Enhanced error handling and recovery
- Secure subprocess execution

### 📝 Other Improvements
- Streaming file operations for large hash files
- Better resource monitoring
- Comprehensive documentation
- Demo scripts for hot-reload
- Security configuration template

## v2.0.0 - Intelligence Update

### Core Features
- Automatic hash type detection
- Priority-based attack orchestration
- Session persistence and resume
- Smart hash tracking
- Pattern analysis from cracked passwords

## v1.0.0 - Initial Release

### Basic Features
- Sequential wordlist/rule execution
- Basic progress monitoring
- Simple configuration file support

---

## Migration Guide

### v2 to v3
1. **Remove sudo from all commands**
2. **Update script references**: `hashwrap_v2.py` → `hashwrap_v3.py`
3. **Create security config**: Copy `hashwrap_security.json.template`
4. **Session format changed**: v2 sessions need manual conversion

### v1 to v3
- Complete rewrite recommended
- Backup existing configurations
- Test with small hash sets first

## Security Notes

### Fixed Vulnerabilities
- CVE-pending: Command injection via wordlist paths
- CVE-pending: Path traversal in hash file operations
- CVE-pending: Arbitrary code execution via pickle deserialization
- CVE-pending: Privilege escalation through sudo requirement

### Best Practices
- Always run as regular user (no sudo)
- Configure allowed directories restrictively
- Set appropriate file size limits
- Monitor hot-reload directories
- Review session reports regularly