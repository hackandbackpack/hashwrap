#!/usr/bin/env python3
"""
Hashwrap v2 - Intelligent Hash Cracking Orchestrator
An advanced wrapper for hashcat with minimal user interaction.
"""

import argparse
import sys
import os
import subprocess
import time
import threading
import signal
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Import our core modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.hash_manager import HashManager
from core.hash_analyzer import HashAnalyzer
from core.attack_orchestrator import AttackOrchestrator, Attack, AttackPriority
from core.session_manager import SessionManager
from utils.display import Display
from utils.resource_monitor import ResourceMonitor


class HashwrapV2:
    """Main application class for Hashwrap v2."""
    
    def __init__(self, args):
        self.args = args
        self.display = Display()
        self.session_manager = SessionManager()
        self.hash_manager = None
        self.hash_analyzer = HashAnalyzer()
        self.orchestrator = AttackOrchestrator()
        self.resource_monitor = ResourceMonitor()
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle interruption gracefully."""
        self.display.warning("\nInterrupted! Saving session state...")
        self.running = False
        if self.session_manager.current_session:
            self.session_manager.update_session({
                'status': 'paused',
                'pause_time': datetime.now().isoformat()
            })
        sys.exit(0)
    
    def run(self):
        """Main execution flow."""
        try:
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
        except Exception as e:
            self.display.error(f"Fatal error: {str(e)}")
            raise
    
    def _run_auto(self):
        """Fully automated mode - just point at a hash file."""
        hash_file = self.args.hash_file
        
        self.display.header("HASHWRAP v2 - AUTO MODE")
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
        
        # Auto-generate config
        config = {
            'hash_file': hash_file,
            'potfile': f"{hash_file}.pot",
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
        
        # Step 4: Generate attack plan
        self.display.section("Attack Planning")
        available_resources = self.resource_monitor.get_resources()
        attacks = self.orchestrator.generate_attack_plan(analysis, available_resources)
        
        self.display.info(f"Generated {len(attacks)} attack strategies")
        
        # Save pending attacks to session
        self.session_manager.update_session({
            'pending_attacks': [{'name': a.name, 'priority': a.priority} for a in attacks]
        })
        
        # Step 5: Execute attacks
        self._execute_attacks()
    
    def _execute_attacks(self):
        """Execute all planned attacks."""
        self.display.section("Attack Execution")
        
        attack_num = 0
        while self.running and self.hash_manager.should_continue():
            attack = self.orchestrator.get_next_attack()
            if not attack:
                self.display.info("No more attacks in queue")
                break
            
            attack_num += 1
            self.display.attack_header(f"Attack #{attack_num}: {attack.name}")
            
            # Update session
            self.session_manager.update_session({
                'current_attack': attack.name
            })
            
            # Execute attack
            start_time = datetime.now()
            results = self._run_hashcat_attack(attack)
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
            self.session_manager.mark_attack_completed(attack.name, results)
            
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
    
    def _run_hashcat_attack(self, attack: Attack) -> Dict[str, Any]:
        """Execute a single hashcat attack."""
        # Get hashcat command
        cmd = ['hashcat']
        
        # Add hash file (use remaining hashes file for efficiency)
        remaining_file = self.hash_manager.get_remaining_hashes_file()
        cmd.append(remaining_file)
        
        # Add attack-specific arguments
        cmd.extend(attack.to_hashcat_args())
        
        # Add potfile
        cmd.extend(['--potfile-path', self.hash_manager.potfile])
        
        # Add performance options
        cmd.extend(['--quiet', '-w', '3', '-O'])  # Workload profile 3, optimized kernel
        
        # Show command
        self.display.debug(f"Command: {' '.join(cmd)}")
        
        # Run hashcat
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitor progress in background
            monitor_thread = threading.Thread(
                target=self._monitor_attack_progress,
                args=(process,)
            )
            monitor_thread.daemon = True
            monitor_thread.start()
            
            # Wait for completion
            stdout, stderr = process.communicate()
            
            # Clean up temp file
            if os.path.exists(remaining_file):
                os.remove(remaining_file)
            
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
    
    def _show_final_summary(self):
        """Show final summary of the session."""
        self.display.section("Session Summary")
        
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
        hash_file = self.args.hash_file
        
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
        session_id = self.args.session_id
        
        self.display.header(f"Resuming Session: {session_id}")
        
        session = self.session_manager.load_session(session_id)
        if not session:
            self.display.error(f"Session {session_id} not found!")
            return
        
        # Initialize components
        self.hash_manager = HashManager(session['hash_file'], session['config']['potfile'])
        
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
        self._execute_attacks()
    
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
        description="Hashwrap v2 - Intelligent Hash Cracking Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fully automated mode - just point at a hash file
  hashwrap auto crack hashes.txt
  
  # Analyze hashes first
  hashwrap analyze hashes.txt
  
  # Resume a previous session
  hashwrap resume SESSION_ID
  
  # Check status of all sessions
  hashwrap status
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
    
    # Status mode
    status_parser = subparsers.add_parser('status', help='Show session status')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Check for sudo on Linux/Mac
    if sys.platform != "win32" and os.geteuid() != 0:
        print("This script must be run with sudo.")
        sys.exit(1)
    
    # Run the application
    app = HashwrapV2(args)
    app.run()


if __name__ == "__main__":
    main()