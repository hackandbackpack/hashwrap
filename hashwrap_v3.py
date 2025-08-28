#!/usr/bin/env python3
"""
Hashwrap v3 - Secure Hash Cracking Orchestrator
Enhanced with security fixes and hot-reload capability.
"""

import argparse
import sys
import os
import subprocess
import time
import threading
import signal
import shlex
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Import our core modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.hash_manager import HashManager
from core.hash_analyzer import HashAnalyzer
from core.attack_orchestrator import AttackOrchestrator, Attack, AttackPriority
from core.session_manager import SessionManager
from core.enhanced_session_manager import EnhancedSessionManager, SessionStatus
from core.security import SecurityValidator, SecureFileOperations, CommandBuilder
from core.hash_watcher import HashFileWatcher, HashReloader
from core.status_monitor import StatusMonitor, StatusFormat
from core.logger import setup_logging, get_logger, log_performance
from core.error_handler import (
    ErrorHandler, get_error_handler, with_error_handling, error_context,
    HashwrapError, FileAccessError, ProcessError, ResourceError, ValidationError,
    ErrorCategory, ErrorSeverity
)
from core.resource_manager import get_resource_manager, cleanup_resources
from utils.display import Display
from utils.resource_monitor import ResourceMonitor


class HashwrapV3:
    """Main application class for Hashwrap v3 with security enhancements."""
    
    def __init__(self, args):
        self.args = args
        self.display = Display()
        
        # Setup logging
        log_level = getattr(args, 'log_level', 'INFO')
        log_file = getattr(args, 'log_file', '.hashwrap_sessions/hashwrap.log')
        setup_logging(
            log_level=log_level,
            log_file=log_file,
            console=True,
            json_format=getattr(args, 'json_logs', False)
        )
        self.logger = get_logger('main')
        self.logger.info("Initializing Hashwrap v3", args=vars(args))
        
        # Initialize security components
        self.security_config = self._load_security_config()
        self.validator = SecurityValidator(self.security_config)
        self.file_ops = SecureFileOperations(self.validator)
        self.cmd_builder = CommandBuilder(self.validator)
        
        # Initialize error handler
        self.error_handler = get_error_handler()
        self._setup_error_callbacks()
        
        # Initialize resource manager
        resource_config = {
            'max_worker_threads': self.security_config.get('max_threads', 4),
            'max_memory_gb': self.security_config.get('max_memory_gb', 8),
            'max_requests_per_minute': self.security_config.get('max_requests_per_minute', 60)
        }
        self.resource_manager = get_resource_manager(resource_config)
        
        # Initialize core components
        self.session_manager = SessionManager()
        self.enhanced_session_manager = EnhancedSessionManager()
        self.hash_manager = None
        self.hash_analyzer = HashAnalyzer()
        self.orchestrator = AttackOrchestrator()
        self.resource_monitor = ResourceMonitor()
        
        # Hot-reload components
        self.hash_watcher = None
        self.hash_reloader = None
        
        # Status monitoring
        self.status_monitor = None
        
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _cleanup_resources(self):
        """Clean up all resources."""
        try:
            # Clean up hash manager
            if hasattr(self, 'hash_manager') and self.hash_manager:
                self.hash_manager.cleanup()
            
            # Clean up resource manager
            if hasattr(self, 'resource_manager') and self.resource_manager:
                self.resource_manager.cleanup()
            
            # Clean up any other resources
            cleanup_resources()
        except Exception as e:
            self.logger.error("Error during resource cleanup", error=e)
    
    def _setup_error_callbacks(self):
        """Setup error handling callbacks."""
        # Register callbacks for specific error categories
        self.error_handler.register_callback(
            ErrorCategory.FILE_ACCESS,
            self._handle_file_access_error
        )
        
        self.error_handler.register_callback(
            ErrorCategory.PROCESS,
            self._handle_process_error
        )
        
        self.error_handler.register_callback(
            ErrorCategory.RESOURCE,
            self._handle_resource_error
        )
    
    def _handle_file_access_error(self, context):
        """Handle file access errors with user notification."""
        self.display.error(f"File access error: {context.error}")
        if context.context_data.get('file_path'):
            self.display.info(f"  File: {context.context_data['file_path']}")
    
    def _handle_process_error(self, context):
        """Handle process errors."""
        self.display.error(f"Process error: {context.error}")
        if context.context_data.get('process_name'):
            self.display.info(f"  Process: {context.context_data['process_name']}")
    
    def _handle_resource_error(self, context):
        """Handle resource errors."""
        self.display.warning(f"Resource limitation: {context.error}")
        if context.context_data.get('resource_type') == 'gpu':
            self.display.info("  Falling back to CPU mode")
    
    @with_error_handling("Load security configuration", reraise=False, default_return=None)
    def _load_security_config(self) -> Dict[str, Any]:
        """Load security configuration."""
        config_path = Path("hashwrap_security.json")
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.logger.info("Loaded security configuration", path=str(config_path))
                    return config
            except json.JSONDecodeError as e:
                raise ValidationError(
                    f"Invalid JSON in security config: {e}",
                    field="security_config",
                    value=str(config_path)
                )
            except IOError as e:
                raise FileAccessError(
                    f"Cannot read security config: {e}",
                    file_path=str(config_path)
                )
        
        # Default security config
        default_config = {
            'allowed_directories': [
                str(Path.cwd()),
                str(Path.cwd() / "wordlists"),
                str(Path.cwd() / "rules"),
                str(Path.cwd() / "hashes"),
                "/usr/share/wordlists",
                "/usr/share/hashcat"
            ],
            'max_file_size': 10 * 1024 * 1024 * 1024,  # 10GB
            'enable_hot_reload': True,
            'hashcat_timeout': 3600
        }
        
        self.logger.info("Using default security configuration")
        return default_config
    
    def _cleanup_on_error(self):
        """Cleanup function called on critical errors."""
        try:
            # Stop any running monitors
            if self.status_monitor:
                self.status_monitor.stop_monitoring()
            
            # Stop hash watcher
            if self.hash_watcher:
                self.hash_watcher.stop()
            
            # Save session state
            if self.session_manager.current_session:
                self.session_manager.update_session({
                    'status': 'error',
                    'error_time': datetime.now().isoformat(),
                    'error_summary': self.error_handler.get_error_summary()
                })
            
            # Clean up temporary files
            if hasattr(self, 'hash_manager') and self.hash_manager:
                self.hash_manager.cleanup()
            
            # Clean up resources
            self._cleanup_resources()
        except Exception as e:
            self.logger.error("Error during cleanup", error=e)
    
    def _signal_handler(self, signum, frame):
        """Handle interruption gracefully."""
        self.display.warning("\nInterrupted! Saving session state...")
        self.running = False
        
        # Stop hash watcher
        if self.hash_watcher:
            self.hash_watcher.stop()
        
        if self.session_manager.current_session:
            self.session_manager.update_session({
                'status': 'paused',
                'pause_time': datetime.now().isoformat()
            })
        
        # Cleanup resources
        self._cleanup_resources()
        sys.exit(0)
    
    def run(self):
        """Main execution flow."""
        try:
            # Verify hashcat is available for commands that need it
            if self.args.command in ['auto', 'crack', 'resume']:
                hashcat_info = self.resource_monitor.check_hashcat_availability()
                if not hashcat_info['available']:
                    self.display.error("Hashcat not found! Please install hashcat first.")
                    self.display.info("Installation: https://hashcat.net/hashcat/")
                    sys.exit(1)
            
            if self.args.command == 'crack':
                self._run_crack()
            elif self.args.command == 'analyze':
                self._run_analyze()
            elif self.args.command == 'resume':
                self._run_resume()
            elif self.args.command == 'status':
                self._show_status()
            elif self.args.command == 'auto':
                self._run_auto()
            elif self.args.command == 'add-hashes':
                self._add_hashes()
        except Exception as e:
            self.display.error(f"Fatal error: {str(e)}")
            raise
    
    def _run_auto(self):
        """Fully automated mode with security enhancements and session support."""
        # Check for restore mode
        if self.args.restore:
            if not self.args.session:
                self.display.error("--restore requires --session NAME")
                return
            
            self.logger.info("Attempting to restore session", session=self.args.session)
            with error_context("Restore session", self.error_handler):
                self._restore_session(self.args.session)
            return
        
        # Use error context for the entire auto mode operation
        with error_context("Auto mode execution", self.error_handler,
                         cleanup=self._cleanup_on_error):
            try:
                # Validate hash file path
                hash_file_path = self.validator.validate_file_path(
                    self.args.hash_file, 
                    must_exist=True
                )
                hash_file = str(hash_file_path)
                
            except (ValueError, FileNotFoundError) as e:
                raise FileAccessError(
                    f"Invalid hash file: {e}",
                    file_path=self.args.hash_file,
                    alternatives=[
                        str(Path.cwd() / "hashes" / Path(self.args.hash_file).name),
                        str(Path.cwd() / Path(self.args.hash_file).name)
                    ],
                    create_if_missing=False
                )
            
            self.display.header("HASHWRAP v3 - SECURE AUTO MODE")
            self.display.info(f"Target: {hash_file}")
            
            # Step 1: Analyze hashes
            self.display.section("Hash Analysis")
            analysis = self.hash_analyzer.analyze_file(hash_file)
            
            self.display.info(f"Total hashes: {analysis['total_hashes']}")
            for hash_type, info in analysis['detected_types'].items():
                self.display.success(f"  {hash_type}: {info['count']} hashes (mode {info['mode']})")
            
            if analysis['unknown_hashes']:
                self.display.warning(f"  Unknown: {len(analysis['unknown_hashes'])} hashes")
        
            # Step 2: Create session
            self.display.section("Session Management")
            
            # Create secure potfile path
            potfile_path = self.validator.create_secure_temp_file(
                prefix="hashwrap_pot_",
                suffix=".pot"
            )
            
            config = {
            'hash_file': hash_file,
            'potfile': potfile_path,
            'hashcat_path': 'hashcat',
            'mode': 'auto',
            'analysis': analysis,
            'workload_profile': self.args.workload_profile,
            'status_timer': self.args.status_timer,
            'enable_hot_reload': self.security_config.get('enable_hot_reload', True)
            }
            
            # Use enhanced session manager if session name provided
            if self.args.session:
            session_id = self.enhanced_session_manager.create_session(
                hash_file, 
                config,
                session_name=self.args.session
            )
                self.display.success(f"Created named session: {session_id}")
            else:
                session_id = self.session_manager.create_session(hash_file, config)
                self.display.success(f"Created session: {session_id}")
            
            # Step 3: Initialize hash manager
            self.hash_manager = HashManager(hash_file, config['potfile'])
            stats = self.hash_manager.get_statistics()
            
            self.session_manager.update_session({
                'statistics': {
                    'total_hashes': stats['total_hashes'],
                    'cracked_hashes': stats['cracked'],
                    'time_elapsed': 0
                }
            })
            
            # Step 4: Setup hot-reload if enabled
            if self.security_config.get('enable_hot_reload', True):
                self._setup_hot_reload()
            
            # Step 5: Generate attack plan
            self.display.section("Attack Planning")
            available_resources = self.resource_monitor.get_resources()
            attacks = self.orchestrator.generate_attack_plan(analysis, available_resources)
            
            self.display.info(f"Generated {len(attacks)} attack strategies")
            
            # Save pending attacks to session
            self.session_manager.update_session({
                'pending_attacks': [{'name': a.name, 'priority': a.priority} for a in attacks]
            })
            
            # Step 6: Execute attacks
            self._execute_attacks_secure()
    
    def _setup_hot_reload(self):
        """Setup hash file watching and hot-reload."""
        self.display.section("Hot-Reload Configuration")
        
        # Initialize watcher
        self.hash_watcher = HashFileWatcher(self.hash_manager, self.validator)
        self.hash_reloader = HashReloader(
            self.hash_manager,
            self.orchestrator,
            self.hash_analyzer
        )
        
        # Set callback
        self.hash_watcher.on_new_hashes_callback = self.hash_reloader.handle_new_hashes
        
        # Add main hash file to watch list
        self.hash_watcher.add_watch_file(self.hash_manager.hash_file)
        
        # Start watching
        self.hash_watcher.start()
        
        self.display.success("✓ Hot-reload enabled")
        self.display.info(f"  Watching: {self.hash_manager.hash_file}")
        self.display.info(f"  Drop new files in: {self.hash_watcher.incoming_dir}")
        self.display.info("  Or append to the main hash file")
    
    def _execute_attacks_secure(self):
        """Execute attacks with security enhancements."""
        self.display.section("Attack Execution")
        
        attack_num = 0
        last_stats_display = time.time()
        
        while self.running and self.hash_manager.should_continue():
            # Check for new hashes (hot-reload)
            if self.hash_manager.new_hashes_queue and not self.hash_manager.new_hashes_queue.empty():
                new_count = 0
                while not self.hash_manager.new_hashes_queue.empty():
                    new_count += self.hash_manager.new_hashes_queue.get()
                
                if new_count > 0:
                    self.display.success(f"\n🔄 Hot-reload: {new_count} new hashes added!")
                    stats = self.hash_manager.get_statistics()
                    self.display.info(f"   Total hashes now: {stats['total_hashes']}")
            
            # Display periodic statistics
            if time.time() - last_stats_display > 30:  # Every 30 seconds
                if self.hash_watcher:
                    watcher_stats = self.hash_watcher.get_stats()
                    if watcher_stats['hashes_added'] > 0:
                        self.display.info(f"Hot-reload stats: {watcher_stats['files_processed']} files, "
                                        f"{watcher_stats['hashes_added']} hashes added")
                last_stats_display = time.time()
            
            # Get next attack
            attack = self.orchestrator.get_next_attack()
            if not attack:
                self.display.info("No more attacks in queue")
                break
            
            attack_num += 1
            self.display.attack_header(f"Attack #{attack_num}: {attack.name}")
            
            # Validate attack name for session tracking
            try:
                safe_attack_name = self.validator.validate_attack_name(attack.name)
                self.session_manager.update_session({
                    'current_attack': safe_attack_name
                })
            except ValueError as e:
                self.display.warning(f"Invalid attack name: {e}")
                continue
            
            # Execute attack
            start_time = datetime.now()
            results = self._run_hashcat_attack_secure(attack)
            end_time = datetime.now()
            
            # Update progress
            progress = self.hash_manager.update_progress(attack.name)
            
            # Display results
            if progress['newly_cracked']:
                self.display.success(f"Cracked {len(progress['newly_cracked'])} new hashes!")
                for hash_val, plaintext in progress['newly_cracked'][:5]:
                    self.display.cracked_hash(hash_val, plaintext)
                if len(progress['newly_cracked']) > 5:
                    self.display.info(f"... and {len(progress['newly_cracked']) - 5} more")
            
            # Update orchestrator with results
            results['cracked_count'] = len(progress['newly_cracked'])
            results['duration'] = str(end_time - start_time)
            self.orchestrator.update_success_metrics(attack, results)
            
            # Mark attack completed in session
            self.session_manager.mark_attack_completed(safe_attack_name, results)
            
            # Show progress
            stats = self.hash_manager.get_statistics()
            self.display.progress_bar(stats['cracked'], stats['total_hashes'], 
                                    f"Overall Progress: {stats['cracked']}/{stats['total_hashes']} "
                                    f"({stats['success_rate']:.1f}%)")
            
            # Check if all hashes are cracked
            if progress['all_cracked']:
                self.display.success("\n🎉 All hashes cracked! 🎉")
                break
        
        # Final summary
        self._show_final_summary()
    
    def _execute_attacks_from_queue(self, attacks: List[Attack], config: Dict[str, Any]):
        """Execute attacks from a restored queue."""
        self.display.section("Attack Execution")
        self.display.info(f"Executing {len(attacks)} attacks")
        
        # Add attacks to orchestrator queue
        for attack in attacks:
            self.orchestrator.add_attack(attack)
        
        # Update enhanced session manager
        self.enhanced_session_manager.set_attack_queue(
            [{'name': a.name, 'priority': a.priority, 
              'attack_type': a.attack_type, 'wordlist': a.wordlist,
              'rules': a.rules, 'mask': a.mask, 'mode': a.mode} 
             for a in attacks]
        )
        
        # Execute attacks
        start_time = datetime.now()
        
        while self.running and self.hash_manager.should_continue():
            attack = self.orchestrator.get_next_attack()
            if not attack:
                break
            
            self.display.section(f"Attack: {attack.name}")
            
            # Update session
            self.enhanced_session_manager.start_attack({
                'name': attack.name,
                'priority': attack.priority,
                'attack_type': attack.attack_type
            })
            
            # Build attack parameters
            attack_params = {
                'mode': attack.mode,
                'attack_type': attack.attack_type,
                'wordlist': attack.wordlist,
                'rules': attack.rules,
                'mask': attack.mask,
                'potfile': config.get('potfile'),
                'session': config.get('hashcat_session'),
                'restore': config.get('restore', False),
                'status_timer': config.get('status_timer', 10),
                'workload_profile': config.get('workload_profile', 3)
            }
            
            # Run attack
            results = self._run_hashcat_attack_secure(attack)
            
            # Update progress
            progress = self.hash_manager.update_progress(attack.name)
            
            # Update session
            self.enhanced_session_manager.complete_attack(
                {'name': attack.name},
                {'success': results.get('success', False),
                 'newly_cracked': len(progress['newly_cracked'])}
            )
            
            # Display progress
            if progress['newly_cracked']:
                self.display.success(f"Cracked {len(progress['newly_cracked'])} new hashes!")
            
            self.display.info(f"Progress: {progress['total_cracked']}/{self.hash_manager.get_statistics()['total_hashes']} "
                             f"({self.hash_manager.get_statistics()['success_rate']:.1f}%)")
            
            # Clear restore flag after first attack
            if config.get('restore'):
                config['restore'] = False
            
            # Checkpoint session
            self.enhanced_session_manager.checkpoint()
        
        # Final summary
        self._show_final_summary()
    
    @log_performance("hashcat_attack")
    @with_error_handling("Execute hashcat attack", reraise=True)
    def _run_hashcat_attack_secure(self, attack: Attack) -> Dict[str, Any]:
        """Execute a single hashcat attack with security measures."""
        self.logger.info("Starting hashcat attack", 
                        attack_name=attack.name,
                        attack_type=attack.attack_type,
                        priority=attack.priority)
        
        # Use error context for better recovery handling
        with error_context(f"Hashcat attack: {attack.name}", self.error_handler,
                          attack=attack, 
                          cleanup=lambda: self._cleanup_failed_attack(attack)):
            try:
                # Build attack parameters
                attack_params = {
                'mode': attack.mode,
                'attack_type': attack.attack_type,
                'wordlist': attack.wordlist,
                'rules': attack.rules,
                'mask': attack.mask,
                'potfile': self.hash_manager.potfile
            }
            
            # Get remaining hashes file
            remaining_file = self.hash_manager.get_remaining_hashes_file()
            
            # Build secure command
            cmd = self.cmd_builder.build_hashcat_command(remaining_file, attack_params)
            
            # Show command (with paths sanitized)
            display_cmd = [self.validator.sanitize_command_argument(arg) for arg in cmd]
            self.display.debug(f"Command: {' '.join(display_cmd)}")
            
            # Run hashcat with improved timeout handling and resource management
            import signal
            
            # Configure timeout from security config
            timeout_seconds = self.security_config.get('hashcat_timeout', 3600)
            
            # Check resources before starting
            required_memory_mb = self.security_config.get('hashcat_memory_mb', 1024)
            if not self.resource_manager.check_resources(memory_mb=required_memory_mb):
                raise ResourceError(
                    "Insufficient resources to run hashcat",
                    resource_type='memory',
                    required=f"{required_memory_mb}MB",
                    available=self.resource_manager.monitor.get_resource_usage()
                )
            
            # Create process with proper group handling for cleanup
            if sys.platform == 'win32':
                # Windows: Use job objects for process group
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=False,
                    env={**os.environ, 'HASHCAT_BRAIN_HOST': 'disabled'},
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                # Unix: Use process groups
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=False,
                    env={**os.environ, 'HASHCAT_BRAIN_HOST': 'disabled'},
                    preexec_fn=os.setsid
                )
            
            # Setup status monitoring if requested
            if hasattr(self.args, 'status_json') and (self.args.status_json or self.args.status_file):
                # Initialize status monitor
                format_type = StatusFormat.JSON if self.args.status_json else StatusFormat.HUMAN
                self.status_monitor = StatusMonitor(
                    format_type=format_type,
                    update_interval=config.get('status_timer', 10),
                    output_file=self.args.status_file
                )
                
                # Start monitoring
                attack_info = {
                    'name': attack.name,
                    'hash_type': f"Mode {attack.mode}" if attack.mode else "Unknown",
                    'hash_file': hash_file,
                    'wordlist': attack.wordlist,
                    'rules': attack.rules,
                    'mask': attack.mask
                }
                
                session_id = self.enhanced_session_manager.current_session.session_id if self.enhanced_session_manager.current_session else "default"
                self.status_monitor.start_monitoring(process, session_id, attack_info)
            
            # Monitor progress in background
            monitor_thread = threading.Thread(
                target=self._monitor_attack_progress,
                args=(process,),
                daemon=False,  # Changed to non-daemon for proper cleanup
                name=f"Monitor-{attack.name}"
            )
            monitor_thread.start()
            
            # Wait for completion with improved timeout handling
            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                self.display.warning(f"Attack '{attack.name}' timed out after {timeout_seconds} seconds")
                
                # Proper process termination
                if sys.platform == 'win32':
                    # Windows: Send CTRL_BREAK_EVENT to process group
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                    time.sleep(5)  # Give hashcat time to save state
                    if process.poll() is None:
                        process.terminate()
                else:
                    # Unix: Send SIGTERM to process group
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass  # Process already terminated
                
                # Wait for process to terminate
                try:
                    stdout, stderr = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if still running
                    process.kill()
                    stdout, stderr = process.communicate()
                    self.display.error(f"Had to force-kill attack '{attack.name}'")
            
            # Ensure monitor thread terminates
            monitor_thread.join(timeout=5)
            if monitor_thread.is_alive():
                self.display.warning("Monitor thread did not terminate cleanly")
            
            # Stop status monitoring if active
            if self.status_monitor:
                self.status_monitor.stop_monitoring()
                
                # Export summary if status file was specified
                if self.args.status_file:
                    summary_file = self.args.status_file.replace('.json', '_summary.json')
                    self.status_monitor.export_summary(summary_file)
            
            # Clean up temp file securely
            if os.path.exists(remaining_file):
                self.file_ops.delete_file_secure(remaining_file)
            
            return {
                'success': process.returncode == 0,
                'return_code': process.returncode,
                'stdout': stdout,
                'stderr': stderr
            }
            
            except subprocess.TimeoutExpired as e:
                raise ProcessError(
                    f"Attack '{attack.name}' timed out",
                    process_name="hashcat",
                    return_code=-1,
                    timeout=timeout_seconds
                )
            except subprocess.CalledProcessError as e:
                raise ProcessError(
                    f"Hashcat failed with code {e.returncode}",
                    process_name="hashcat",
                    return_code=e.returncode,
                    stderr=e.stderr
                )
            except FileNotFoundError as e:
                raise FileAccessError(
                    f"Required file not found: {e}",
                    file_path=str(e.filename) if hasattr(e, 'filename') else None
                )
            except MemoryError as e:
                raise ResourceError(
                    "Out of memory during attack",
                    resource_type="memory",
                    attack=attack.name
                )
            except Exception as e:
                # Log unexpected errors
                self.logger.error("Unexpected error in attack", error=e, attack=attack.name)
                raise HashwrapError(
                    f"Attack failed: {str(e)}",
                    severity=ErrorSeverity.CRITICAL,
                    category=ErrorCategory.UNKNOWN,
                    context={'attack': attack.name, 'error_type': type(e).__name__}
                )
    
    def _cleanup_failed_attack(self, attack: Attack):
        """Cleanup after a failed attack."""
        try:
            # Stop status monitor
            if self.status_monitor:
                self.status_monitor.stop_monitoring()
                self.status_monitor = None
            
            # Update session to mark attack as failed
            if self.enhanced_session_manager.current_session:
                self.enhanced_session_manager.complete_attack(
                    {'name': attack.name},
                    {'success': False, 'error': True}
                )
            
            # Log failure
            self.logger.warning("Attack cleanup completed", attack=attack.name)
        except Exception as e:
            self.logger.error("Error during attack cleanup", error=e)
    
    def _monitor_attack_progress(self, process):
        """Monitor attack progress in background."""
        while process.poll() is None:
            # Update progress every 5 seconds
            time.sleep(5)
            progress = self.hash_manager.update_progress()
            
            if progress['newly_cracked']:
                for hash_val, plaintext in progress['newly_cracked']:
                    self.display.cracked_hash(hash_val, plaintext)
    
    def _add_hashes(self):
        """Add hashes to a running session."""
        session_id = self.args.session_id
        new_hash_file = self.args.hash_file
        
        try:
            # Validate inputs
            session_id = self.validator.validate_session_id(session_id)
            new_hash_path = self.validator.validate_file_path(new_hash_file, must_exist=True)
            
            # Copy file to incoming directory
            incoming_dir = Path(".hashwrap_sessions/incoming_hashes")
            incoming_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_file = incoming_dir / f"added_{timestamp}_{new_hash_path.name}"
            
            # Read and validate hashes before copying
            valid_hashes = []
            for line_num, line in self.file_ops.read_lines_streaming(str(new_hash_path)):
                if line and not line.startswith('#'):
                    try:
                        valid_hash = self.validator.validate_hash_format(line)
                        valid_hashes.append(valid_hash)
                    except ValueError:
                        self.display.warning(f"Skipping invalid hash on line {line_num}")
            
            # Write validated hashes
            self.file_ops.write_file(str(dest_file), '\n'.join(valid_hashes))
            
            self.display.success(f"Added {len(valid_hashes)} hashes to session {session_id}")
            self.display.info(f"File placed in: {dest_file}")
            
        except Exception as e:
            self.display.error(f"Failed to add hashes: {e}")
    
    def _show_final_summary(self):
        """Show final summary of the session."""
        self.display.section("Session Summary")
        
        # Stop hash watcher
        if self.hash_watcher:
            self.hash_watcher.stop()
            watcher_stats = self.hash_watcher.get_stats()
            if watcher_stats['hashes_added'] > 0:
                self.display.info(f"Hot-reload summary:")
                self.display.info(f"  Files processed: {watcher_stats['files_processed']}")
                self.display.info(f"  Hashes added: {watcher_stats['hashes_added']}")
        
        stats = self.hash_manager.get_statistics()
        attack_stats = self.orchestrator.get_attack_statistics()
        
        self.display.info(f"Total hashes: {stats['total_hashes']}")
        self.display.success(f"Cracked: {stats['cracked']} ({stats['success_rate']:.1f}%)")
        self.display.warning(f"Remaining: {stats['remaining']}")
        
        self.display.info(f"\nTotal attacks executed: {attack_stats['total_attacks']}")
        
        if attack_stats['most_effective']:
            self.display.success("\nMost effective attacks:")
            for attack_key, success_rate in attack_stats['most_effective']:
                self.display.info(f"  {attack_key}: {success_rate:.1%} success rate")
        
        # Password analysis
        if stats['cracked'] > 0:
            analysis = self.hash_manager.analyze_cracked_passwords()
            self.display.section("Password Analysis")
            self.display.info(f"Average length: {analysis['average_length']:.1f} characters")
            self.display.info(f"Character sets:")
            for charset, count in analysis['character_sets'].items():
                if count > 0:
                    self.display.info(f"  {charset}: {count} passwords")
        
        # Close session
        self.session_manager.close_session(stats)
        
        # Save report
        report_file = f"hashwrap_report_{self.session_manager.current_session['id']}.md"
        self.session_manager.export_session_report(
            self.session_manager.current_session['id'], 
            report_file
        )
        self.display.success(f"\nDetailed report saved to: {report_file}")
    
    def _run_analyze(self):
        """Run analysis only mode."""
        try:
            hash_file_path = self.validator.validate_file_path(
                self.args.hash_file,
                must_exist=True
            )
            hash_file = str(hash_file_path)
        except Exception as e:
            self.display.error(f"Invalid hash file: {e}")
            return
        
        self.display.header("Hash Analysis")
        analysis = self.hash_analyzer.analyze_file(hash_file)
        
        # Display results
        self.display.info(f"Total hashes: {analysis['total_hashes']}")
        
        self.display.section("Detected Hash Types")
        for hash_type, info in analysis['detected_types'].items():
            self.display.success(f"{hash_type}:")
            self.display.info(f"  Count: {info['count']}")
            self.display.info(f"  Hashcat mode: {info['mode']}")
            self.display.info(f"  Confidence: {info['confidence']:.0%}")
            if info['samples']:
                self.display.info(f"  Sample: {info['samples'][0]}")
        
        if analysis['unknown_hashes']:
            self.display.warning(f"\nUnknown hashes: {len(analysis['unknown_hashes'])}")
            for unknown in analysis['unknown_hashes'][:3]:
                self.display.info(f"  Line {unknown['line']}: {unknown['hash']}")
        
        self.display.section("Recommendations")
        for rec in analysis['recommendations']:
            priority_color = {'high': 'red', 'medium': 'yellow', 'low': 'blue'}[rec['priority']]
            self.display.colored(f"[{rec['priority'].upper()}] {rec['description']}", priority_color)
            if 'command' in rec:
                self.display.info(f"  Command: {rec['command']}")
            if 'wordlists' in rec:
                self.display.info(f"  Wordlists: {', '.join(rec['wordlists'])}")
    
    def _run_resume(self):
        """Resume a previous session."""
        try:
            session_id = self.validator.validate_session_id(self.args.session_id)
        except ValueError as e:
            self.display.error(f"Invalid session ID: {e}")
            return
        
        self.display.header(f"Resuming Session: {session_id}")
        
        session = self.session_manager.load_session(session_id)
        if not session:
            self.display.error(f"Session {session_id} not found!")
            return
        
        # Validate session paths
        try:
            hash_file_path = self.validator.validate_file_path(
                session['hash_file'],
                must_exist=True
            )
            session['hash_file'] = str(hash_file_path)
        except Exception as e:
            self.display.error(f"Session hash file no longer accessible: {e}")
            return
        
        # Initialize components
        self.hash_manager = HashManager(session['hash_file'], session['config']['potfile'])
        
        # Setup hot-reload if enabled
        if self.security_config.get('enable_hot_reload', True):
            self._setup_hot_reload()
        
        # Show current status
        stats = self.hash_manager.get_statistics()
        self.display.info(f"Progress: {stats['cracked']}/{stats['total_hashes']} "
                         f"({stats['success_rate']:.1f}%)")
        
        # Get resume point
        resume_point = self.session_manager.get_resume_point()
        if resume_point:
            self.display.info(f"Completed attacks: {resume_point['completed_count']}")
            if resume_point['next_attack']:
                self.display.info(f"Next attack: {resume_point['next_attack']['name']}")
        
        # Continue execution
        self._execute_attacks_secure()
    
    def _restore_session(self, session_name: str):
        """Restore a previous session using enhanced session manager."""
        self.display.section("Session Restore")
        
        # Load session state
        session_state = self.enhanced_session_manager.resume_session(session_name)
        if not session_state:
            self.display.error(f"Could not find session: {session_name}")
            return
        
        # Display session info
        self.display.info(f"Restored session: {session_state.session_id}")
        self.display.info(f"Status: {session_state.status}")
        self.display.info(f"Hash file: {session_state.hash_file}")
        self.display.info(f"Progress: {session_state.cracked_hashes}/{session_state.total_hashes} "
                         f"({(session_state.cracked_hashes/session_state.total_hashes*100):.1f}%)")
        
        # Validate hash file still exists
        try:
            hash_file_path = self.validator.validate_file_path(
                session_state.hash_file,
                must_exist=True
            )
        except Exception as e:
            self.display.error(f"Original hash file no longer accessible: {e}")
            return
        
        # Initialize components
        self.hash_manager = HashManager(
            session_state.hash_file, 
            session_state.potfile,
            streaming_mode=True if session_state.total_hashes > 1000000 else False
        )
        
        # Setup hot-reload if enabled
        if session_state.hot_reload_enabled:
            self._setup_hot_reload()
        
        # Check for hashcat restore file
        restore_file = self.enhanced_session_manager.get_restore_file()
        if restore_file:
            self.display.info(f"Found hashcat restore file: {restore_file}")
            # Pass restore flag to hashcat
            session_state.config['restore'] = True
        
        # Restore attack queue
        if session_state.pending_attacks:
            self.display.info(f"Resuming with {len(session_state.pending_attacks)} pending attacks")
            
            # Convert to Attack objects
            attacks = []
            for attack_data in session_state.pending_attacks:
                attack = Attack(
                    priority=attack_data.get('priority', 99),
                    name=attack_data.get('name', 'Unknown'),
                    attack_type=attack_data.get('attack_type', 'dictionary'),
                    wordlist=attack_data.get('wordlist'),
                    rules=attack_data.get('rules'),
                    mask=attack_data.get('mask'),
                    mode=attack_data.get('mode')
                )
                attacks.append(attack)
            
            # Execute remaining attacks
            self._execute_attacks_from_queue(attacks, session_state.config)
        else:
            self.display.warning("No pending attacks found in session")
    
    def _show_status(self):
        """Show status of all sessions."""
        self.display.header("Hashwrap Sessions")
        
        sessions = self.session_manager.list_sessions()
        if not sessions:
            self.display.info("No sessions found")
            return
        
        for session in sessions:
            status_color = 'green' if session['status'] == 'active' else 'yellow'
            self.display.colored(f"\nSession: {session['id']}", status_color)
            self.display.info(f"  Started: {session['start_time']}")
            self.display.info(f"  Status: {session['status']}")
            self.display.info(f"  Progress: {session['progress']}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Hashwrap v3 - Secure Hash Cracking Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fully automated mode - no sudo required!
  python hashwrap_v3.py auto crack hashes.txt
  
  # Analyze hashes first
  python hashwrap_v3.py analyze hashes.txt
  
  # Resume a previous session
  python hashwrap_v3.py resume SESSION_ID
  
  # Add hashes to running session
  python hashwrap_v3.py add-hashes SESSION_ID new_hashes.txt
  
  # Check status of all sessions
  python hashwrap_v3.py status

Hot-Reload:
  While running, you can add new hashes by:
  1. Appending to the original hash file
  2. Dropping files in: .hashwrap_sessions/incoming_hashes/
  3. Using: python hashwrap_v3.py add-hashes SESSION_ID new_file.txt
        """
    )
    
    # Global arguments
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       default='INFO', help='Set logging level (default: INFO)')
    parser.add_argument('--log-file', help='Log file path (default: .hashwrap_sessions/hashwrap.log)')
    parser.add_argument('--json-logs', action='store_true', help='Use JSON format for log files')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Auto mode
    auto_parser = subparsers.add_parser('auto', help='Fully automated cracking')
    auto_parser.add_argument('action', choices=['crack'], help='Action to perform')
    auto_parser.add_argument('hash_file', help='File containing hashes')
    auto_parser.add_argument('--session', help='Session name for checkpoint/restore')
    auto_parser.add_argument('--restore', action='store_true', help='Restore previous session')
    auto_parser.add_argument('--workload-profile', '-w', type=int, choices=[1, 2, 3, 4],
                            default=3, help='Workload profile (1=low, 2=default, 3=high, 4=nightmare)')
    auto_parser.add_argument('--status-timer', type=int, default=10,
                            help='Seconds between status updates')
    auto_parser.add_argument('--status-json', action='store_true',
                            help='Output status updates in JSON format')
    auto_parser.add_argument('--status-file', help='Write status updates to file')
    
    # Analyze mode
    analyze_parser = subparsers.add_parser('analyze', help='Analyze hash file')
    analyze_parser.add_argument('hash_file', help='File containing hashes')
    
    # Resume mode
    resume_parser = subparsers.add_parser('resume', help='Resume previous session')
    resume_parser.add_argument('session_id', help='Session ID to resume')
    
    # Add hashes mode
    add_parser = subparsers.add_parser('add-hashes', help='Add hashes to running session')
    add_parser.add_argument('session_id', help='Session ID')
    add_parser.add_argument('hash_file', help='File containing new hashes')
    
    # Status mode
    status_parser = subparsers.add_parser('status', help='Show session status')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Run the application (no sudo check!)
    app = HashwrapV3(args)
    app.run()


if __name__ == "__main__":
    main()