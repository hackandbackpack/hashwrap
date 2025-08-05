# Hashwrap - Intelligent Hash Cracking Orchestrator

A secure, intelligent wrapper for hashcat that automates hash cracking with minimal user interaction. Features hot-reload capability, smart attack orchestration, and comprehensive security hardening.

## Features

### 🔒 Security First
- **No sudo/admin required** - Runs with user permissions only
- **Command injection prevention** - All inputs properly sanitized
- **Path traversal protection** - File operations sandboxed
- **Secure session persistence** - JSON-based (no pickle)

### 🔄 Hot-Reload Capability
Add new hashes while cracking is in progress:
- Append to original hash file
- Drop files in `.hashwrap_sessions/incoming_hashes/`
- Use CLI: `python hashwrap_v3.py add-hashes SESSION_ID file.txt`

### 🧠 Intelligent Automation
- **Auto-detects** 20+ hash types (MD5, SHA, NTLM, bcrypt, etc.)
- **Smart attack ordering** - Quick wins first, exhaustive last
- **Context awareness** - Detects AD dumps, web apps, etc.
- **Pattern learning** - Adapts based on cracked passwords

### 📊 Session Management
- Full pause/resume capability
- Survives interruptions gracefully
- Detailed progress tracking
- Comprehensive reports

## Installation

```bash
# Clone repository
git clone https://github.com/hackandbackpack/hashwrap.git
cd hashwrap

# Install dependencies
pip install -r requirements.txt

# Install hashcat (if not already installed)
# Ubuntu/Debian: apt install hashcat
# macOS: brew install hashcat
# Windows: Download from https://hashcat.net/hashcat/

# Hashcat Version Compatibility
# - Fully compatible with hashcat v6.2.6 (current stable)
# - Ready for hashcat v7.0.0 with support for new hash types
# - Minimum supported version: hashcat v6.0.0
```

## Quick Start

```bash
# Basic usage - fully automated
python hashwrap_v3.py auto crack hashes.txt

# Analyze hashes first
python hashwrap_v3.py analyze hashes.txt

# Resume a session
python hashwrap_v3.py resume 20240120_143052

# Check status
python hashwrap_v3.py status

# Add hashes to running session
python hashwrap_v3.py add-hashes 20240120_143052 new_hashes.txt
```

## Configuration

Create `hashwrap_security.json` for custom settings:

```json
{
  "allowed_directories": [
    "./wordlists",
    "./rules",
    "./hashes"
  ],
  "max_file_size": 10737418240,
  "enable_hot_reload": true
}
```

## Project Structure

```
hashwrap/
├── core/
│   ├── security.py          # Input validation & sandboxing
│   ├── hash_manager.py      # Hash tracking & hot-reload
│   ├── hash_analyzer.py     # Auto-detection engine
│   ├── attack_orchestrator.py # Smart attack scheduling
│   ├── session_manager.py   # Persistence & recovery
│   └── hash_watcher.py      # File monitoring
├── utils/
│   ├── display.py          # Terminal UI
│   └── resource_monitor.py # System monitoring
├── wordlists/              # Default wordlists
├── rules/                  # Mutation rules
└── hashwrap_v3.py         # Main application
```

## Version History

- **v3.0** - Security hardening, hot-reload, no sudo requirement
- **v2.0** - Intelligent automation, session management
- **v1.0** - Basic sequential execution

## Security Notes

- Always ensure you have authorization to crack any hashes
- Configure allowed directories in `hashwrap_security.json`
- Review session reports for audit trails
- Never run as root/administrator

## License

Same as original hashwrap project

## Contributing

Contributions welcome! The modular architecture makes it easy to add new features while maintaining security.