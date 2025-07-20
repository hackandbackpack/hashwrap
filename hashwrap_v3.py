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
from core.security import SecurityValidator, SecureFileOperations, CommandBuilder
from core.hash_watcher import HashFileWatcher, HashReloader
from utils.display import Display
from utils.resource_monitor import ResourceMonitor


class HashwrapV3:
    """Main application class for Hashwrap v3 with security enhancements."""
    
    def __init__(self, args):
        self.args = args
        self.display = Display()
        
        # Initialize security components
        self.security_config = self._load_security_config()
        self.validator = SecurityValidator(self.security_config)
        self.file_ops = SecureFileOperations(self.validator)
        self.cmd_builder = CommandBuilder(self.validator)
        
        # Initialize core components
        self.session_manager = SessionManager()
        self.hash_manager = None
        self.hash_analyzer = HashAnalyzer()
        self.orchestrator = AttackOrchestrator()
        self.resource_monitor = ResourceMonitor()
        
        # Hot-reload components
        self.hash_watcher = None
        self.hash_reloader = None
        
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_security_config(self) -> Dict[str, Any]:
        """Load security configuration."""
        config_path = Path("hashwrap_security.json")
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Default security config
        return {
            'allowed_directories': [
                str(Path.cwd()),
                str(Path.cwd() / "wordlists"),
                str(Path.cwd() / "rules"),
                str(Path.cwd() / "hashes"),
                "/usr/share/wordlists",
                "/usr/share/hashcat"
            ],
            'max_file_size': 10 * 1024 * 1024 * 1024,  # 10GB
            'enable_hot_reload': True
        }
    
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
        """Fully automated mode with security enhancements."""
        try:
            # Validate hash file path
            hash_file_path = self.validator.validate_file_path(
                self.args.hash_file, 
                must_exist=True
            )
            hash_file = str(hash_file_path)
            
        except (ValueError, FileNotFoundError) as e:
            self.display.error(f"Invalid hash file: {e}")
            return
        
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
            'analysis': analysis
        }
        
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
    
    def _run_hashcat_attack_secure(self, attack: Attack) -> Dict[str, Any]:
        """Execute a single hashcat attack with security measures."""
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
            
            # Run hashcat
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                # Security: Don't pass shell=True
                shell=False,
                # Limit environment variables
                env={**os.environ, 'HASHCAT_BRAIN_HOST': 'disabled'}
            )
            
            # Monitor progress in background
            monitor_thread = threading.Thread(
                target=self._monitor_attack_progress,
                args=(process,),
                daemon=True
            )
            monitor_thread.start()
            
            # Wait for completion with timeout
            try:
                stdout, stderr = process.communicate(timeout=3600)  # 1 hour timeout
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                self.display.warning("Attack timed out after 1 hour")
            
            # Clean up temp file securely
            if os.path.exists(remaining_file):
                self.file_ops.delete_file_secure(remaining_file)
            
            return {
                'success': process.returncode == 0,
                'return_code': process.returncode,
                'stdout': stdout,
                'stderr': stderr
            }
            
        except Exception as e:
            self.display.error(f"Attack failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
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
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Auto mode
    auto_parser = subparsers.add_parser('auto', help='Fully automated cracking')
    auto_parser.add_argument('action', choices=['crack'], help='Action to perform')
    auto_parser.add_argument('hash_file', help='File containing hashes')
    
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