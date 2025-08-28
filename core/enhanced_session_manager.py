"""
Enhanced session management with proper --session and --restore support.
Provides checkpoint/resume functionality compatible with hashcat's session system.
"""

import json
import os
import time
import shutil
import threading
import platform
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

from .logger import get_logger

# Cross-platform file locking
if platform.system() == 'Windows':
    import msvcrt
else:
    import fcntl


class SessionNotFoundError(Exception):
    """Raised when a session cannot be found."""
    pass


class SessionStatus(Enum):
    """Session status states."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"
    ERROR = "error"


@dataclass
class SessionState:
    """Complete session state for checkpoint/restore."""
    session_id: str
    session_name: Optional[str]
    hash_file: str
    potfile: str
    config: Dict[str, Any]
    status: str
    start_time: str
    last_checkpoint: str
    total_hashes: int
    cracked_hashes: int
    remaining_hashes: int
    completed_attacks: List[Dict[str, Any]]
    pending_attacks: List[Dict[str, Any]]
    current_attack: Optional[Dict[str, Any]]
    attack_position: int
    runtime_seconds: float
    hashcat_session: Optional[str]
    hot_reload_enabled: bool
    statistics: Dict[str, Any]


class EnhancedSessionManager:
    """Enhanced session management with full checkpoint/restore support."""
    
    def __init__(self, session_dir: str = ".hashwrap_sessions"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(exist_ok=True)
        self.logger = get_logger('session_manager')
        
        # Current session state
        self.current_session: Optional[SessionState] = None
        self.session_file: Optional[Path] = None
        self.checkpoint_interval = 60  # Checkpoint every 60 seconds
        self.last_checkpoint_time = 0
        
        # Session tracking
        self.sessions_index_file = self.session_dir / "sessions.json"
        self._ensure_sessions_index()
        
        # Thread safety
        self._session_lock = threading.RLock()  # Reentrant lock for nested calls
    
    def _ensure_sessions_index(self):
        """Ensure sessions index file exists."""
        if not self.sessions_index_file.exists():
            with open(self.sessions_index_file, 'w') as f:
                json.dump({}, f)
    
    def create_session(self, 
                      hash_file: str, 
                      config: Dict[str, Any],
                      session_name: Optional[str] = None,
                      resume_from: Optional[str] = None) -> str:
        """
        Create a new session with optional name and resume support.
        
        Args:
            hash_file: Path to hash file
            config: Session configuration
            session_name: Optional custom session name (for --session)
            resume_from: Session ID to resume from
            
        Returns:
            Session ID
        """
        # Generate session ID
        if session_name:
            # Use provided session name
            session_id = session_name
            self.logger.info("Creating named session", session_name=session_name)
        else:
            # Generate timestamp-based ID
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            
        # Create session directory
        session_path = self.session_dir / f"session_{session_id}"
        session_path.mkdir(exist_ok=True)
        
        # Initialize potfile
        potfile_path = str(session_path / "hashwrap.potfile")
        
        # Create session state
        if resume_from:
            # Resume from existing session
            old_session = self.load_session(resume_from)
            if old_session:
                self.current_session = SessionState(
                    session_id=session_id,
                    session_name=session_name,
                    hash_file=old_session.hash_file,
                    potfile=potfile_path,
                    config=old_session.config,
                    status=SessionStatus.RUNNING.value,
                    start_time=datetime.now().isoformat(),
                    last_checkpoint=datetime.now().isoformat(),
                    total_hashes=old_session.total_hashes,
                    cracked_hashes=old_session.cracked_hashes,
                    remaining_hashes=old_session.remaining_hashes,
                    completed_attacks=old_session.completed_attacks,
                    pending_attacks=old_session.pending_attacks,
                    current_attack=old_session.current_attack,
                    attack_position=old_session.attack_position,
                    runtime_seconds=old_session.runtime_seconds,
                    hashcat_session=session_id if session_name else None,
                    hot_reload_enabled=config.get('enable_hot_reload', True),
                    statistics=old_session.statistics
                )
                
                # Copy old potfile if exists
                old_potfile = Path(old_session.potfile)
                if old_potfile.exists():
                    shutil.copy2(old_potfile, potfile_path)
                    
                self.logger.info("Resumed from session", 
                               old_session=resume_from,
                               new_session=session_id)
            else:
                raise ValueError(f"Could not load session to resume: {resume_from}")
        else:
            # Create new session
            self.current_session = SessionState(
                session_id=session_id,
                session_name=session_name,
                hash_file=hash_file,
                potfile=potfile_path,
                config=config,
                status=SessionStatus.CREATED.value,
                start_time=datetime.now().isoformat(),
                last_checkpoint=datetime.now().isoformat(),
                total_hashes=0,
                cracked_hashes=0,
                remaining_hashes=0,
                completed_attacks=[],
                pending_attacks=[],
                current_attack=None,
                attack_position=0,
                runtime_seconds=0.0,
                hashcat_session=session_id if session_name else None,
                hot_reload_enabled=config.get('enable_hot_reload', True),
                statistics={
                    'attacks_completed': 0,
                    'attacks_skipped': 0,
                    'total_runtime': 0,
                    'average_crack_rate': 0
                }
            )
        
        # Set session file path
        self.session_file = session_path / "session.json"
        
        # Save initial state
        self.checkpoint()
        
        # Update sessions index
        self._update_sessions_index(session_id, session_path)
        
        return session_id
    
    def load_session(self, session_id: str) -> Optional[SessionState]:
        """
        Load an existing session for resume.
        
        Args:
            session_id: Session ID or name to load
            
        Returns:
            SessionState if found, None otherwise
        """
        # Try direct session ID first
        session_path = self.session_dir / f"session_{session_id}"
        session_file = session_path / "session.json"
        
        if not session_file.exists():
            # Try looking up in sessions index
            with open(self.sessions_index_file, 'r') as f:
                sessions_index = json.load(f)
            
            if session_id in sessions_index:
                session_path = Path(sessions_index[session_id]['path'])
                session_file = session_path / "session.json"
        
        if session_file.exists():
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                
                # Convert to SessionState
                session_state = SessionState(**data)
                
                self.logger.info("Loaded session", 
                               session_id=session_id,
                               status=session_state.status,
                               cracked=session_state.cracked_hashes,
                               remaining=session_state.remaining_hashes)
                
                return session_state
                
            except Exception as e:
                self.logger.error("Failed to load session", 
                                error=e,
                                session_id=session_id)
                raise SessionNotFoundError(f"Failed to load session {session_id}: {e}")
        
        raise SessionNotFoundError(f"Session not found: {session_id}")
    
    def checkpoint(self, force: bool = False) -> bool:
        """
        Save current session state (checkpoint) with file locking.
        
        Args:
            force: Force checkpoint even if interval hasn't elapsed
            
        Returns:
            True if checkpoint saved, False otherwise
        """
        if not self.current_session or not self.session_file:
            return False
        
        # Check if we should checkpoint
        current_time = time.time()
        if not force and (current_time - self.last_checkpoint_time) < self.checkpoint_interval:
            return False
        
        # Use a lock file to prevent concurrent writes
        lock_file = self.session_file.with_suffix('.lock')
        lock_acquired = False
        lock_handle = None
        
        try:
            # Try to acquire exclusive lock
            lock_handle = open(lock_file, 'w')
            
            if platform.system() == 'Windows':
                # Windows file locking
                import msvcrt
                for attempt in range(5):  # Try 5 times with backoff
                    try:
                        msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
                        lock_acquired = True
                        break
                    except IOError:
                        if attempt < 4:
                            time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        else:
                            raise
            else:
                # Unix file locking
                import fcntl
                for attempt in range(5):  # Try 5 times with backoff
                    try:
                        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        lock_acquired = True
                        break
                    except BlockingIOError:
                        if attempt < 4:
                            time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        else:
                            raise
            
            if not lock_acquired:
                self.logger.warning("Could not acquire lock for checkpoint")
                return False
            
            # Update checkpoint time
            self.current_session.last_checkpoint = datetime.now().isoformat()
            
            # Convert to dict and save
            session_data = asdict(self.current_session)
            
            # Atomic write with proper permissions
            temp_file = self.session_file.with_suffix('.tmp')
            
            # Write to temp file
            with open(temp_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            # Set restrictive permissions on temp file
            os.chmod(temp_file, 0o600)
            
            # Atomic replace
            if platform.system() == 'Windows':
                # Windows doesn't support atomic rename if target exists
                if self.session_file.exists():
                    self.session_file.unlink()
            temp_file.replace(self.session_file)
            
            self.last_checkpoint_time = current_time
            
            self.logger.debug("Session checkpoint saved", 
                            session_id=self.current_session.session_id)
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to save checkpoint", 
                            error=e,
                            session_id=self.current_session.session_id)
            return False
        finally:
            # Always release lock and clean up
            if lock_handle:
                if lock_acquired:
                    if platform.system() == 'Windows':
                        try:
                            import msvcrt
                            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                        except:
                            pass
                    else:
                        try:
                            import fcntl
                            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                        except:
                            pass
                lock_handle.close()
            
            # Remove lock file
            if lock_file.exists():
                try:
                    lock_file.unlink()
                except:
                    pass
    
    def update_session(self, updates: Dict[str, Any]) -> None:
        """
        Update session state with new data (thread-safe).
        
        Args:
            updates: Dictionary of updates to apply
        """
        with self._session_lock:
            if not self.current_session:
                return
            
            # Update fields
            for key, value in updates.items():
                if hasattr(self.current_session, key):
                    setattr(self.current_session, key, value)
            
            # Update runtime
            if self.current_session.start_time:
                start = datetime.fromisoformat(self.current_session.start_time)
                self.current_session.runtime_seconds = (datetime.now() - start).total_seconds()
            
            # Checkpoint if significant changes
            if any(key in ['status', 'current_attack', 'cracked_hashes'] for key in updates):
                self.checkpoint(force=True)
    
    def set_attack_queue(self, attacks: List[Dict[str, Any]]) -> None:
        """Set the pending attack queue (thread-safe)."""
        with self._session_lock:
            if self.current_session:
                self.current_session.pending_attacks = attacks
                self.checkpoint(force=True)
    
    def start_attack(self, attack: Dict[str, Any]) -> None:
        """Mark an attack as started (thread-safe)."""
        with self._session_lock:
            if self.current_session:
                # Remove from pending attacks
                self.current_session.pending_attacks = [
                    a for a in self.current_session.pending_attacks 
                    if a.get('name') != attack.get('name')
                ]
                
                # Set as current
                self.current_session.current_attack = attack
                self.current_session.status = SessionStatus.RUNNING.value
                self.checkpoint(force=True)
    
    def complete_attack(self, attack: Dict[str, Any], results: Dict[str, Any]) -> None:
        """Mark an attack as completed (thread-safe)."""
        with self._session_lock:
            if self.current_session:
                # Add to completed attacks
                completed_attack = {
                    **attack,
                    'completed_at': datetime.now().isoformat(),
                    'results': results
                }
                self.current_session.completed_attacks.append(completed_attack)
                
                # Remove from pending if present
                self.current_session.pending_attacks = [
                    a for a in self.current_session.pending_attacks 
                    if a.get('name') != attack.get('name')
                ]
                
                # Clear current attack
                self.current_session.current_attack = None
                
                # Update statistics
                self.current_session.statistics['attacks_completed'] += 1
                
                self.checkpoint(force=True)
    
    def pause_session(self) -> None:
        """Pause the current session."""
        if self.current_session:
            self.current_session.status = SessionStatus.PAUSED.value
            self.checkpoint(force=True)
            self.logger.info("Session paused", 
                           session_id=self.current_session.session_id)
    
    def resume_session(self, session_id: str) -> Optional[SessionState]:
        """
        Resume a paused or interrupted session.
        
        Args:
            session_id: Session to resume
            
        Returns:
            Loaded session state
        """
        session_state = self.load_session(session_id)
        
        if session_state:
            # Update paths
            session_path = self.session_dir / f"session_{session_id}"
            self.session_file = session_path / "session.json"
            
            # Set as current session
            self.current_session = session_state
            
            # Update status
            if session_state.status in [SessionStatus.CREATED.value, SessionStatus.PAUSED.value, SessionStatus.ERROR.value]:
                session_state.status = SessionStatus.RUNNING.value
                self.checkpoint(force=True)
            
            self.logger.info("Resumed session", 
                           session_id=session_id,
                           attacks_completed=len(session_state.completed_attacks),
                           attacks_pending=len(session_state.pending_attacks))
            
            return session_state
        
        return None
    
    def get_restore_file(self) -> Optional[Path]:
        """Get hashcat restore file path for current session."""
        if self.current_session and self.current_session.hashcat_session:
            # Hashcat stores restore files as session_name.restore
            restore_file = Path(f"{self.current_session.hashcat_session}.restore")
            if restore_file.exists():
                return restore_file
        return None
    
    def list_sessions(self, include_completed: bool = False) -> List[Dict[str, Any]]:
        """
        List all available sessions.
        
        Args:
            include_completed: Include completed sessions
            
        Returns:
            List of session summaries
        """
        sessions = []
        
        # Read sessions index
        with open(self.sessions_index_file, 'r') as f:
            sessions_index = json.load(f)
        
        # Scan session directories
        for session_dir in self.session_dir.glob("session_*"):
            if session_dir.is_dir():
                session_file = session_dir / "session.json"
                if session_file.exists():
                    try:
                        session_state = self.load_session(session_dir.name.replace("session_", ""))
                        if session_state:
                            if include_completed or session_state.status != SessionStatus.COMPLETED.value:
                                sessions.append({
                                    'id': session_state.session_id,
                                    'name': session_state.session_name,
                                    'status': session_state.status,
                                    'hash_file': session_state.hash_file,
                                    'total_hashes': session_state.total_hashes,
                                    'cracked_hashes': session_state.cracked_hashes,
                                    'start_time': session_state.start_time,
                                    'runtime_seconds': session_state.runtime_seconds,
                                    'attacks_completed': len(session_state.completed_attacks)
                                })
                    except Exception as e:
                        self.logger.warning("Failed to load session", 
                                          session_dir=session_dir,
                                          error=e)
        
        # Sort by start time (newest first)
        sessions.sort(key=lambda x: x['start_time'], reverse=True)
        
        return sessions
    
    def _update_sessions_index(self, session_id: str, session_path: Path) -> None:
        """Update the sessions index file (thread-safe with atomic write)."""
        try:
            # Read existing index
            sessions_index = {}
            if self.sessions_index_file.exists():
                with open(self.sessions_index_file, 'r') as f:
                    sessions_index = json.load(f)
            
            # Update index
            sessions_index[session_id] = {
                'path': str(session_path),
                'created': datetime.now().isoformat()
            }
            
            # Atomic write
            temp_file = self.sessions_index_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(sessions_index, f, indent=2)
            
            # Set restrictive permissions
            os.chmod(temp_file, 0o600)
            
            # Atomic replace
            if platform.system() == 'Windows' and self.sessions_index_file.exists():
                self.sessions_index_file.unlink()
            temp_file.replace(self.sessions_index_file)
                
        except Exception as e:
            self.logger.error("Failed to update sessions index", error=e)
    
    def get_session_report(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a detailed session report.
        
        Args:
            session_id: Session to report on (current if None)
            
        Returns:
            Detailed session report
        """
        session = self.current_session if not session_id else self.load_session(session_id)
        
        if not session:
            return {}
        
        # Calculate statistics
        total_attacks = len(session.completed_attacks) + len(session.pending_attacks)
        if session.current_attack:
            total_attacks += 1
        
        success_rate = 0
        if session.total_hashes > 0:
            success_rate = (session.cracked_hashes / session.total_hashes) * 100
        
        # Time formatting
        runtime_hours = session.runtime_seconds / 3600
        
        return {
            'session_id': session.session_id,
            'session_name': session.session_name,
            'status': session.status,
            'hash_file': session.hash_file,
            'start_time': session.start_time,
            'runtime_hours': round(runtime_hours, 2),
            'total_hashes': session.total_hashes,
            'cracked_hashes': session.cracked_hashes,
            'remaining_hashes': session.remaining_hashes,
            'success_rate': round(success_rate, 2),
            'total_attacks': total_attacks,
            'completed_attacks': len(session.completed_attacks),
            'pending_attacks': len(session.pending_attacks),
            'current_attack': session.current_attack.get('name') if session.current_attack else None,
            'hot_reload_enabled': session.hot_reload_enabled,
            'statistics': session.statistics
        }
    
    def get_runtime(self) -> float:
        """Get current session runtime in seconds."""
        if not self.current_session:
            return 0.0
        
        start_time = datetime.fromisoformat(self.current_session.start_time)
        return (datetime.now() - start_time).total_seconds()
    
    def _save_session(self) -> None:
        """Save current session state to disk."""
        if not self.current_session:
            return
        
        session_path = self.session_dir / f"session_{self.current_session.session_id}"
        session_file = session_path / "session.json"
        
        try:
            # Create session directory
            session_path.mkdir(exist_ok=True)
            
            # Save session state
            with open(session_file, 'w') as f:
                json.dump(asdict(self.current_session), f, indent=2)
            
            self.logger.debug("Session saved", session_id=self.current_session.session_id)
            
        except Exception as e:
            self.logger.error("Failed to save session", error=e)