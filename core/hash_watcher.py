import os
import time
import threading
import queue
from pathlib import Path
from typing import Dict, List, Set, Optional, Callable
from datetime import datetime
import hashlib

from .security import SecurityValidator, SecureFileOperations


class HashFileWatcher:
    """Monitor hash files and directories for new additions."""
    
    def __init__(self, hash_manager, security_validator: SecurityValidator):
        self.hash_manager = hash_manager
        self.validator = security_validator
        self.file_ops = SecureFileOperations(security_validator)
        
        # Watching configuration
        self.watch_interval = 5  # seconds
        self.running = False
        self.watcher_thread = None
        
        # Files being watched
        self.watched_files: Dict[str, Dict] = {}  # filepath -> {mtime, size, checksum}
        self.incoming_dir = Path(".hashwrap_sessions/incoming_hashes")
        self.processed_dir = Path(".hashwrap_sessions/processed_hashes")
        
        # Callbacks
        self.on_new_hashes_callback: Optional[Callable] = None
        
        # Statistics
        self.stats = {
            'files_processed': 0,
            'hashes_added': 0,
            'last_check': None
        }
        
        self._setup_directories()
    
    def _setup_directories(self):
        """Create necessary directories."""
        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Set secure permissions
        os.chmod(self.incoming_dir, 0o700)
        os.chmod(self.processed_dir, 0o700)
    
    def start(self):
        """Start watching for changes."""
        if self.running:
            return
        
        self.running = True
        self.watcher_thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name="HashFileWatcher"
        )
        self.watcher_thread.start()
    
    def stop(self):
        """Stop watching."""
        self.running = False
        if self.watcher_thread:
            self.watcher_thread.join(timeout=10)
    
    def add_watch_file(self, filepath: str):
        """Add a file to watch list."""
        try:
            safe_path = self.validator.validate_file_path(filepath, must_exist=True)
            
            # Get initial file state
            stat = safe_path.stat()
            file_info = {
                'mtime': stat.st_mtime,
                'size': stat.st_size,
                'checksum': self._calculate_file_checksum(safe_path),
                'path': safe_path
            }
            
            self.watched_files[str(safe_path)] = file_info
            
        except Exception as e:
            print(f"Error adding watch file {filepath}: {e}")
    
    def _calculate_file_checksum(self, filepath: Path, chunk_size: int = 8192) -> str:
        """Calculate MD5 checksum of file tail (last 1MB)."""
        # Only checksum the tail for performance
        file_size = filepath.stat().st_size
        start_pos = max(0, file_size - 1024 * 1024)  # Last 1MB
        
        md5 = hashlib.md5()
        with open(filepath, 'rb') as f:
            f.seek(start_pos)
            while chunk := f.read(chunk_size):
                md5.update(chunk)
        
        return md5.hexdigest()
    
    def _watch_loop(self):
        """Main watching loop."""
        while self.running:
            try:
                self.stats['last_check'] = datetime.now()
                
                # Check watched files for changes
                self._check_watched_files()
                
                # Check incoming directory
                self._check_incoming_directory()
                
            except Exception as e:
                print(f"Error in watch loop: {e}")
            
            time.sleep(self.watch_interval)
    
    def _check_watched_files(self):
        """Check if any watched files have been modified."""
        for filepath, old_info in list(self.watched_files.items()):
            try:
                path = Path(filepath)
                if not path.exists():
                    continue
                
                # Get current file state
                stat = path.stat()
                current_mtime = stat.st_mtime
                current_size = stat.st_size
                
                # Check if file has grown (appended to)
                if current_size > old_info['size']:
                    # File has grown - check what was added
                    new_hashes = self._extract_new_content(
                        path, 
                        old_info['size'],
                        current_size
                    )
                    
                    if new_hashes:
                        self._process_new_hashes(new_hashes, f"appended to {path.name}")
                    
                    # Update tracked info
                    self.watched_files[filepath] = {
                        'mtime': current_mtime,
                        'size': current_size,
                        'checksum': self._calculate_file_checksum(path),
                        'path': path
                    }
                
            except Exception as e:
                print(f"Error checking file {filepath}: {e}")
    
    def _extract_new_content(self, filepath: Path, old_size: int, new_size: int) -> List[str]:
        """Extract newly added content from file."""
        new_hashes = []
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                # Seek to where we left off
                f.seek(old_size)
                
                # Read new content
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            validated_hash = self.validator.validate_hash_format(line)
                            new_hashes.append(validated_hash)
                        except ValueError:
                            # Skip invalid hashes
                            pass
        
        except Exception as e:
            print(f"Error extracting new content: {e}")
        
        return new_hashes
    
    def _check_incoming_directory(self):
        """Check for new files in incoming directory."""
        try:
            for file_path in self.incoming_dir.iterdir():
                if file_path.is_file() and file_path.suffix in ['.txt', '.lst', '.hashes']:
                    self._process_incoming_file(file_path)
        
        except Exception as e:
            print(f"Error checking incoming directory: {e}")
    
    def _process_incoming_file(self, file_path: Path):
        """Process a new file from incoming directory."""
        try:
            # Read and validate hashes
            new_hashes = []
            
            for line_num, line in self.file_ops.read_lines_streaming(str(file_path)):
                if line and not line.startswith('#'):
                    try:
                        validated_hash = self.validator.validate_hash_format(line)
                        new_hashes.append(validated_hash)
                    except ValueError:
                        # Skip invalid hashes
                        pass
            
            if new_hashes:
                self._process_new_hashes(new_hashes, f"file {file_path.name}")
                self.stats['files_processed'] += 1
            
            # Move file to processed directory
            processed_path = self.processed_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_path.name}"
            file_path.rename(processed_path)
            
        except Exception as e:
            print(f"Error processing incoming file {file_path}: {e}")
    
    def _process_new_hashes(self, new_hashes: List[str], source: str):
        """Process newly discovered hashes."""
        if not new_hashes:
            return
        
        # Add to hash manager
        added_count = self.hash_manager.add_hashes_dynamically(new_hashes)
        
        if added_count > 0:
            self.stats['hashes_added'] += added_count
            
            # Trigger callback if set
            if self.on_new_hashes_callback:
                self.on_new_hashes_callback(added_count, source)
            
            print(f"\n🔄 Added {added_count} new hashes from {source}")
    
    def get_stats(self) -> Dict:
        """Get watcher statistics."""
        return {
            **self.stats,
            'watched_files': len(self.watched_files),
            'is_running': self.running
        }


class HashReloader:
    """Coordinate hash reloading with attack orchestration."""
    
    def __init__(self, hash_manager, orchestrator, hash_analyzer):
        self.hash_manager = hash_manager
        self.orchestrator = orchestrator
        self.hash_analyzer = hash_analyzer
        self.reload_lock = threading.Lock()
        
    def handle_new_hashes(self, count: int, source: str):
        """Handle newly added hashes."""
        with self.reload_lock:
            # Quick analysis of new hashes
            remaining_file = self.hash_manager.get_remaining_hashes_file()
            
            try:
                # Analyze just the new hashes
                analysis = self.hash_analyzer.analyze_file(remaining_file)
                
                # Generate quick attacks for new hashes
                if analysis['detected_types']:
                    # Inject high-priority attacks
                    self._inject_quick_attacks(analysis)
                
            finally:
                # Clean up temp file
                if os.path.exists(remaining_file):
                    os.remove(remaining_file)
    
    def _inject_quick_attacks(self, analysis: Dict):
        """Inject quick attacks for newly added hashes."""
        from .attack_orchestrator import Attack, AttackPriority
        
        # Get the most common hash type from new hashes
        if analysis['detected_types']:
            hash_type_info = list(analysis['detected_types'].values())[0]
            mode = hash_type_info['mode']
            
            # Create high-priority quick attacks
            quick_attacks = [
                Attack(
                    priority=AttackPriority.QUICK_WIN.value - 0.5,  # Higher than normal
                    name="Quick attack for new hashes",
                    attack_type="dictionary",
                    wordlist="wordlists/top100.txt",
                    mode=mode,
                    estimated_duration=30,
                    success_probability=0.9
                ),
                Attack(
                    priority=AttackPriority.QUICK_WIN.value - 0.4,
                    name="Common patterns for new hashes",
                    attack_type="mask",
                    mask="?u?l?l?l?l?l?d?d",
                    mode=mode,
                    estimated_duration=60,
                    success_probability=0.7
                )
            ]
            
            # Add to orchestrator queue
            for attack in quick_attacks:
                self.orchestrator.add_attack(attack)