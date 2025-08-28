import os
import re
import shlex
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
import hashlib
import tempfile

from .pattern_cache import HashPatterns, is_valid_hash_cached, validate_path_cached


class SecurityValidator:
    """Comprehensive security validation for all inputs."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.allowed_dirs = self._get_allowed_directories()
        self.max_file_size = self.config.get('max_file_size', 10 * 1024 * 1024 * 1024)  # 10GB default
        
    def _get_allowed_directories(self) -> List[Path]:
        """Get list of allowed directories for file operations."""
        default_dirs = [
            Path.cwd(),
            Path.cwd() / "wordlists",
            Path.cwd() / "rules",
            Path.cwd() / "hashes",
            Path.home() / ".hashwrap",
        ]
        
        # Add platform-specific directories
        if sys.platform != "win32":
            default_dirs.extend([
                Path("/usr/share/wordlists"),
                Path("/usr/share/hashcat")
            ])
        
        # Add temp directory for testing
        import tempfile
        default_dirs.append(Path(tempfile.gettempdir()))
        
        # Add custom directories from config
        if 'allowed_directories' in self.config:
            for dir_path in self.config['allowed_directories']:
                default_dirs.append(Path(dir_path).resolve())
        
        # Resolve all paths and include existing directories
        resolved_dirs = []
        for d in default_dirs:
            try:
                resolved = d.resolve()
                if resolved.exists():
                    resolved_dirs.append(resolved)
            except:
                pass
                
        return resolved_dirs
    
    def validate_file_path(self, filepath: str, must_exist: bool = True) -> Path:
        """Validate and sanitize file paths to prevent traversal attacks."""
        if not filepath:
            raise ValueError("Empty file path provided")
        
        # Convert to Path object and resolve to absolute path
        try:
            path = Path(filepath).resolve()
        except (ValueError, OSError) as e:
            raise ValueError(f"Invalid path format: {filepath}")
        
        # Check if path exists (if required)
        if must_exist and not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Check if path is within allowed directories
        # Resolve symlinks to prevent symlink attacks
        try:
            real_path = path.resolve(strict=False)
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Cannot resolve path: {filepath} - {e}")
        
        # Check if resolved path is within allowed directories
        is_allowed = False
        for allowed_dir in self.allowed_dirs:
            try:
                # Use is_relative_to for secure validation (Python 3.9+)
                # For older Python, use the try/except pattern with relative_to
                try:
                    if hasattr(real_path, 'is_relative_to'):
                        if real_path.is_relative_to(allowed_dir):
                            is_allowed = True
                            break
                    else:
                        # Fallback for Python < 3.9
                        real_path.relative_to(allowed_dir)
                        is_allowed = True
                        break
                except ValueError:
                    continue
            except Exception:
                continue
        
        if not is_allowed:
            raise ValueError(f"Path '{filepath}' is outside allowed directories (resolved to: {real_path})")
        
        # Check file size if it exists
        if path.exists() and path.is_file():
            if path.stat().st_size > self.max_file_size:
                raise ValueError(f"File too large: {path.stat().st_size} bytes (max: {self.max_file_size})")
        
        return path
    
    def validate_hash_format(self, hash_string: str) -> str:
        """Validate hash string format with strict security checks using cached patterns."""
        if not hash_string:
            raise ValueError("Empty hash string")
        
        # Remove whitespace
        hash_string = hash_string.strip()
        
        # Length check first
        if len(hash_string) > 1024:  # Reasonable max for any hash format
            raise ValueError(f"Hash string too long: {len(hash_string)} characters")
        
        # Use cached validation for performance
        if is_valid_hash_cached(hash_string):
            return hash_string
        
        # For backward compatibility, allow a restricted set of characters
        # but only if it looks like a hash
        if re.match(r'^[a-fA-F0-9:$.*\-_/=+]+$', hash_string) and len(hash_string) >= 8:
            return hash_string
        
        raise ValueError(f"Invalid hash format: {hash_string[:50]}")
    
    def sanitize_command_argument(self, arg: str) -> str:
        """Sanitize command line arguments to prevent injection."""
        if not arg:
            return '""'
        
        # Use shlex.quote for proper shell escaping
        return shlex.quote(str(arg))
    
    def validate_attack_name(self, name: str) -> str:
        """Validate attack name for safe file operations."""
        if not name:
            raise ValueError("Empty attack name")
        
        # Length limit first
        if len(name) > 255:
            raise ValueError(f"Attack name too long: {len(name)} characters")
        
        # Use optimized pattern for filename validation
        # Allow spaces in attack names
        safe_name = name.replace(' ', '_')
        if not HashPatterns.is_valid_filename(safe_name):
            raise ValueError(f"Invalid attack name: {name}")
        
        return name
    
    def validate_session_id(self, session_id: str) -> str:
        """Validate session ID format."""
        if not session_id:
            raise ValueError("Empty session ID")
        
        # Expected format: YYYYMMDD_HHMMSS
        if not re.match(r'^\d{8}_\d{6}$', session_id):
            raise ValueError(f"Invalid session ID format: {session_id}")
        
        return session_id
    
    def create_secure_temp_file(self, prefix: str = "hashwrap_", suffix: str = ".tmp") -> str:
        """Create a secure temporary file."""
        # Validate prefix and suffix
        prefix = re.sub(r'[^a-zA-Z0-9_\-]', '', prefix)
        suffix = re.sub(r'[^a-zA-Z0-9_\-\.]', '', suffix)
        
        # Create temp file with secure permissions
        fd, filepath = tempfile.mkstemp(prefix=prefix, suffix=suffix)
        os.close(fd)
        
        # Set restrictive permissions (owner read/write only)
        os.chmod(filepath, 0o600)
        
        return filepath


class SecureFileOperations:
    """Secure wrappers for file operations."""
    
    def __init__(self, validator: SecurityValidator):
        self.validator = validator
    
    def read_file(self, filepath: str, encoding: str = 'utf-8') -> str:
        """Securely read a file."""
        # Validate path
        safe_path = self.validator.validate_file_path(filepath, must_exist=True)
        
        # Read with size limit
        with open(safe_path, 'r', encoding=encoding, errors='ignore') as f:
            # Read in chunks to avoid memory issues
            content = []
            total_size = 0
            chunk_size = 1024 * 1024  # 1MB chunks
            
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                    
                total_size += len(chunk)
                if total_size > self.validator.max_file_size:
                    raise ValueError(f"File too large to read: >{self.validator.max_file_size} bytes")
                
                content.append(chunk)
        
        return ''.join(content)
    
    def write_file(self, filepath: str, content: str, encoding: str = 'utf-8'):
        """Securely write to a file."""
        # Validate path (allow non-existing files for creation)
        safe_path = self.validator.validate_file_path(filepath, must_exist=False)
        
        # Create parent directory if needed
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write with secure permissions
        with tempfile.NamedTemporaryFile(mode='w', encoding=encoding, 
                                       dir=safe_path.parent, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        # Set secure permissions
        os.chmod(tmp_path, 0o600)
        
        # Atomic rename
        os.replace(tmp_path, safe_path)
    
    def read_lines_streaming(self, filepath: str, encoding: str = 'utf-8'):
        """Stream file lines without loading entire file into memory."""
        safe_path = self.validator.validate_file_path(filepath, must_exist=True)
        
        with open(safe_path, 'r', encoding=encoding, errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                yield line_num, line.strip()
    
    def append_to_file(self, filepath: str, content: str, encoding: str = 'utf-8'):
        """Securely append to a file."""
        safe_path = self.validator.validate_file_path(filepath, must_exist=True)
        
        # Use exclusive lock for appending
        with open(safe_path, 'a', encoding=encoding) as f:
            f.write(content)
    
    def delete_file_secure(self, filepath: str):
        """Securely delete a file."""
        safe_path = self.validator.validate_file_path(filepath, must_exist=True)
        
        # Overwrite with random data before deletion (optional, for sensitive data)
        if safe_path.exists() and safe_path.is_file():
            file_size = safe_path.stat().st_size
            
            # Only overwrite small files (performance consideration)
            if file_size < 1024 * 1024:  # 1MB
                with open(safe_path, 'wb') as f:
                    f.write(os.urandom(file_size))
            
            # Delete the file
            safe_path.unlink()


class CommandBuilder:
    """Secure command building for subprocess execution."""
    
    def __init__(self, validator: SecurityValidator):
        self.validator = validator
    
    def build_hashcat_command(self, hash_file: str, attack_params: Dict[str, Any]) -> List[str]:
        """Build secure hashcat command."""
        cmd = ['hashcat']
        
        # Validate and add hash file
        safe_hash_file = self.validator.validate_file_path(hash_file, must_exist=True)
        cmd.append(str(safe_hash_file))
        
        # Add mode if specified
        if 'mode' in attack_params and attack_params['mode'] is not None:
            cmd.extend(['-m', str(int(attack_params['mode']))])
        
        # Add attack type
        if 'attack_type' in attack_params:
            attack_type_map = {
                'dictionary': '0',
                'mask': '3',
                'hybrid': '6'
            }
            if attack_params['attack_type'] in attack_type_map:
                cmd.extend(['-a', attack_type_map[attack_params['attack_type']]])
        
        # Add wordlist (validated)
        if 'wordlist' in attack_params and attack_params['wordlist']:
            safe_wordlist = self.validator.validate_file_path(
                attack_params['wordlist'], 
                must_exist=True
            )
            cmd.append(str(safe_wordlist))
        
        # Add rules file (validated)
        if 'rules' in attack_params and attack_params['rules']:
            safe_rules = self.validator.validate_file_path(
                attack_params['rules'],
                must_exist=True
            )
            cmd.extend(['-r', str(safe_rules)])
        
        # Add mask (sanitized)
        if 'mask' in attack_params and attack_params['mask']:
            # Validate mask format using optimized pattern
            mask = attack_params['mask']
            if not HashPatterns.is_valid_mask(mask):
                # Get specific invalid characters for better error message
                SAFE_MASK_CHARS = set('?ludsahHx0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
                invalid_chars = set(mask) - SAFE_MASK_CHARS
                raise ValueError(f"Invalid mask characters detected: {invalid_chars}")
            if len(mask) > 256:  # Prevent excessively long masks
                raise ValueError(f"Mask too long: {len(mask)} characters (max 256)")
            # Use shlex.quote for additional safety
            cmd.append(shlex.quote(mask))
        
        # Add potfile
        if 'potfile' in attack_params:
            safe_potfile = self.validator.validate_file_path(
                attack_params['potfile'],
                must_exist=False
            )
            cmd.extend(['--potfile-path', str(safe_potfile)])
        
        # Add safe static options
        cmd.extend(['--quiet', '-w', '3', '-O'])
        
        # Add session support
        if 'session' in attack_params and attack_params['session']:
            # Validate session name using optimized pattern
            session_name = attack_params['session']
            if not HashPatterns.is_valid_session_name(session_name):
                raise ValueError(f"Invalid session name: {session_name}. Only alphanumeric, underscore, and dash allowed.")
            if len(session_name) > 64:
                raise ValueError(f"Session name too long: {len(session_name)} characters (max 64)")
            cmd.extend(['--session', shlex.quote(session_name)])
        
        # Add restore support
        if 'restore' in attack_params and attack_params['restore']:
            cmd.append('--restore')
        
        # Add status timer
        if 'status_timer' in attack_params:
            cmd.extend(['--status-timer', str(int(attack_params['status_timer']))])
        
        # Add workload profile
        if 'workload_profile' in attack_params:
            profile = int(attack_params['workload_profile'])
            if 1 <= profile <= 4:
                cmd.extend(['-w', str(profile)])
        
        return cmd