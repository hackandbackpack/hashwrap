"""
Hashcat execution service with real-time monitoring and job control.
Handles hashcat process management, status parsing, and result processing.
"""

import json
import os
import signal
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import psutil

from sqlalchemy.orm import Session

from worker.utils.logging import get_task_logger
from core.attack_orchestrator import AttackOrchestrator, Attack
from core.security import SecurityValidator, SecureFileOperations
from backend.app.models.job import Job, JobStatus
from backend.app.core.config import get_settings


logger = get_task_logger(__name__)


class HashcatService:
    """Service for executing hashcat jobs with monitoring and control."""
    
    def __init__(self, job: Job, db_session: Session):
        self.job = job
        self.db = db_session
        self.settings = get_settings()
        
        # Security components
        self.validator = SecurityValidator()
        self.file_ops = SecureFileOperations(self.validator)
        
        # Process management
        self.process: Optional[subprocess.Popen] = None
        self.process_pid: Optional[int] = None
        
        # Monitoring
        self.status_monitor = None
        self.monitoring_thread = None
        self.is_monitoring = False
        
        # Attack orchestration
        self.orchestrator = AttackOrchestrator()
        self.current_attack: Optional[Attack] = None
        
        # File paths
        self.work_dir = Path(self.settings.RESULTS_DIR) / f"job_{self.job.id}"
        self.status_file = self.work_dir / "status.json"
        self.potfile = self.work_dir / "hashcat.pot"
        self.session_file = self.work_dir / "hashcat.session"
        
        # Status tracking
        self.last_status = {}
        self.start_time = None
        
    def prepare_execution(self) -> Dict[str, Any]:
        """Prepare hashcat execution environment."""
        logger.info(f"Preparing execution for job {self.job.id}")
        
        try:
            # Create work directory
            self.work_dir.mkdir(parents=True, exist_ok=True)
            
            # Validate input files
            upload_file_path = Path(self.job.upload.file_path)
            if not upload_file_path.exists():
                return {'success': False, 'error': f'Upload file not found: {upload_file_path}'}
            
            # Security validation
            try:
                safe_upload_path = self.validator.validate_file_path(
                    str(upload_file_path), must_exist=True
                )
            except Exception as e:
                return {'success': False, 'error': f'Security validation failed: {e}'}
            
            # Generate attack plan based on hash type
            if self.job.hash_type and self.job.profile_name:
                attack_plan = self._generate_attack_plan()
                if not attack_plan:
                    return {'success': False, 'error': 'Failed to generate attack plan'}
                
                # Add attacks to orchestrator
                for attack in attack_plan:
                    self.orchestrator.add_attack(attack)
            else:
                return {'success': False, 'error': 'Hash type or profile not specified'}
            
            # Create session file
            self._initialize_session()
            
            logger.info(f"Execution preparation completed for job {self.job.id}")
            return {'success': True, 'work_dir': str(self.work_dir)}
            
        except Exception as e:
            logger.error(f"Error preparing execution for job {self.job.id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def execute_with_monitoring(self, progress_callback: Callable, 
                               job_control: 'HashcatJobControl') -> Dict[str, Any]:
        """Execute hashcat with real-time monitoring."""
        logger.info(f"Starting hashcat execution for job {self.job.id}")
        
        try:
            self.start_time = datetime.utcnow()
            execution_results = []
            
            # Execute attacks in priority order
            while not job_control.should_stop():
                attack = self.orchestrator.get_next_attack()
                if not attack:
                    logger.info(f"No more attacks to execute for job {self.job.id}")
                    break
                
                self.current_attack = attack
                logger.info(f"Executing attack: {attack.name} for job {self.job.id}")
                
                # Execute single attack
                attack_result = self._execute_single_attack(
                    attack, progress_callback, job_control
                )
                
                execution_results.append({
                    'attack': attack.name,
                    'result': attack_result
                })
                
                # Check if job should stop
                if attack_result.get('stopped'):
                    break
                
                # Check if we've cracked enough hashes
                if self._should_stop_execution(attack_result):
                    logger.info(f"Stopping execution - success criteria met for job {self.job.id}")
                    break
            
            # Calculate final results
            final_result = self._calculate_final_results(execution_results)
            
            logger.info(f"Hashcat execution completed for job {self.job.id}")
            return final_result
            
        except Exception as e:
            logger.error(f"Error during hashcat execution for job {self.job.id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'execution_results': execution_results}
        
        finally:
            self._cleanup_process()
    
    def _execute_single_attack(self, attack: Attack, progress_callback: Callable,
                              job_control: 'HashcatJobControl') -> Dict[str, Any]:
        """Execute a single hashcat attack."""
        try:
            # Build hashcat command
            cmd = self._build_hashcat_command(attack)
            if not cmd:
                return {'success': False, 'error': 'Failed to build hashcat command'}
            
            logger.info(f"Executing command: {' '.join(cmd)}")
            
            # Start hashcat process
            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.process_pid = self.process.pid
            
            # Start monitoring
            self._start_monitoring(progress_callback)
            
            # Wait for completion or external control
            while self.process.poll() is None:
                if job_control.should_stop():
                    logger.info(f"Stopping attack due to job control for job {self.job.id}")
                    self._terminate_process()
                    return {'success': True, 'stopped': True}
                
                time.sleep(1)  # Check every second
            
            # Get final return code
            return_code = self.process.returncode
            
            # Stop monitoring
            self._stop_monitoring()
            
            # Process results
            return self._process_attack_results(attack, return_code)
            
        except Exception as e:
            logger.error(f"Error executing attack {attack.name}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
        
        finally:
            self._cleanup_process()
    
    def _build_hashcat_command(self, attack: Attack) -> Optional[List[str]]:
        """Build hashcat command line arguments."""
        try:
            cmd = ['hashcat']
            
            # Add attack-specific arguments
            cmd.extend(attack.to_hashcat_args())
            
            # Add job-specific arguments
            upload_file = Path(self.job.upload.file_path)
            cmd.append(str(upload_file))
            
            # Session management
            cmd.extend(['--session', str(self.session_file)])
            
            # Status output
            cmd.extend(['--status', '--status-json'])
            
            # Output settings
            cmd.extend(['--potfile-path', str(self.potfile)])
            cmd.extend(['--outfile', str(self.work_dir / 'cracked.txt')])
            cmd.extend(['--outfile-format', '2'])  # hash:plaintext format
            
            # Performance settings
            cmd.extend(['--workload-profile', '3'])  # High performance
            
            # GPU settings if available
            if self.settings.CUDA_VISIBLE_DEVICES:
                cmd.extend(['--opencl-devices', self.settings.CUDA_VISIBLE_DEVICES.replace(',', ' ')])
            
            # Validation
            for arg in cmd[1:]:  # Skip 'hashcat'
                if not self.validator.validate_command_arg(arg):
                    logger.error(f"Invalid command argument: {arg}")
                    return None
            
            return cmd
            
        except Exception as e:
            logger.error(f"Error building hashcat command: {e}")
            return None
    
    def _start_monitoring(self, progress_callback: Callable):
        """Start real-time monitoring of hashcat status."""
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(progress_callback,),
            daemon=True
        )
        self.monitoring_thread.start()
    
    def _stop_monitoring(self):
        """Stop monitoring thread."""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
    
    def _monitoring_loop(self, progress_callback: Callable):
        """Main monitoring loop for parsing hashcat status."""
        logger.info(f"Starting monitoring loop for job {self.job.id}")
        
        while self.is_monitoring and self.process and self.process.poll() is None:
            try:
                # Read status from hashcat process
                status_data = self._read_hashcat_status()
                
                if status_data:
                    # Process status update
                    progress_data = self._parse_status_data(status_data)
                    
                    if progress_data:
                        # Call progress callback
                        progress_callback(progress_data)
                        
                        # Update internal status
                        self.last_status = progress_data
                
                time.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                time.sleep(10)  # Wait longer on error
    
    def _read_hashcat_status(self) -> Optional[Dict]:
        """Read status from hashcat process."""
        try:
            # Try to get status via SIGUSR1 signal (Linux/Mac)
            if hasattr(signal, 'SIGUSR1') and self.process_pid:
                try:
                    os.kill(self.process_pid, signal.SIGUSR1)
                    time.sleep(0.5)  # Allow hashcat to write status
                except (OSError, ProcessLookupError):
                    pass
            
            # Read from status file if it exists
            if self.status_file.exists():
                try:
                    with open(self.status_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            return json.loads(content)
                except (json.JSONDecodeError, IOError):
                    pass
            
            # Fallback: try to read from process stdout
            if self.process and self.process.stdout:
                try:
                    # Non-blocking read
                    import select
                    if select.select([self.process.stdout], [], [], 0)[0]:
                        line = self.process.stdout.readline()
                        if line.strip().startswith('{'):
                            return json.loads(line.strip())
                except (json.JSONDecodeError, Exception):
                    pass
                    
        except Exception as e:
            logger.debug(f"Error reading hashcat status: {e}")
        
        return None
    
    def _parse_status_data(self, status_data: Dict) -> Optional[Dict]:
        """Parse hashcat status data into progress information."""
        try:
            progress_data = {}
            
            # Extract basic information
            if 'progress' in status_data:
                progress_data['progress_percentage'] = status_data['progress'][0] / status_data['progress'][1] * 100 if status_data['progress'][1] > 0 else 0
            
            if 'recovered_hashes' in status_data:
                progress_data['cracked_count'] = status_data['recovered_hashes'][0]
                progress_data['total_hashes'] = status_data['recovered_hashes'][1]
                
                # Calculate newly cracked since last update
                last_cracked = self.last_status.get('cracked_count', 0)
                progress_data['newly_cracked'] = progress_data['cracked_count'] - last_cracked
            
            if 'recovered_salts' in status_data:
                progress_data['cracked_salts'] = status_data['recovered_salts'][0]
                progress_data['total_salts'] = status_data['recovered_salts'][1]
            
            # Speed information
            if 'devices' in status_data:
                total_speed = 0
                for device in status_data['devices']:
                    if 'speed' in device:
                        total_speed += device['speed']
                progress_data['speed_hashes_per_second'] = total_speed
                progress_data['speed_human'] = self._format_speed(total_speed)
            
            # Time information
            if 'time_start' in status_data:
                progress_data['runtime_seconds'] = status_data.get('time_start', 0)
            
            # ETA
            if 'estimated_stop' in status_data:
                eta_timestamp = status_data['estimated_stop']
                if eta_timestamp > 0:
                    eta_seconds = eta_timestamp - time.time()
                    progress_data['eta_seconds'] = max(0, int(eta_seconds))
                    progress_data['eta_human'] = self._format_time(eta_seconds)
            
            # Current attack information
            if self.current_attack:
                progress_data['current_attack'] = self.current_attack.name
                progress_data['attack_type'] = self.current_attack.attack_type
            
            # Temperature and GPU info
            if 'devices' in status_data:
                temps = []
                utils = []
                for device in status_data['devices']:
                    if 'temp' in device:
                        temps.append(device['temp'])
                    if 'util' in device:
                        utils.append(device['util'])
                
                if temps:
                    progress_data['max_temp'] = max(temps)
                    progress_data['avg_temp'] = sum(temps) / len(temps)
                if utils:
                    progress_data['avg_gpu_util'] = sum(utils) / len(utils)
            
            return progress_data
            
        except Exception as e:
            logger.error(f"Error parsing status data: {e}")
            return None
    
    def _format_speed(self, speed: int) -> str:
        """Format speed in human-readable format."""
        if speed >= 1e9:
            return f"{speed/1e9:.2f} GH/s"
        elif speed >= 1e6:
            return f"{speed/1e6:.2f} MH/s"
        elif speed >= 1e3:
            return f"{speed/1e3:.2f} kH/s"
        else:
            return f"{speed} H/s"
    
    def _format_time(self, seconds: float) -> str:
        """Format time in human-readable format."""
        if seconds < 0:
            return "Unknown"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    def _terminate_process(self):
        """Terminate hashcat process gracefully."""
        if self.process:
            try:
                # First try graceful termination
                self.process.terminate()
                
                # Wait up to 10 seconds for graceful shutdown
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if necessary
                    self.process.kill()
                    self.process.wait()
                    
            except (ProcessLookupError, OSError):
                pass  # Process already dead
    
    def _cleanup_process(self):
        """Clean up process resources."""
        self._stop_monitoring()
        
        if self.process:
            self._terminate_process()
            self.process = None
            self.process_pid = None
    
    def _generate_attack_plan(self) -> List[Attack]:
        """Generate attack plan based on job configuration."""
        # This would integrate with the existing attack orchestrator
        # For now, return a basic plan
        attacks = []
        
        # Quick dictionary attack
        attacks.append(Attack(
            priority=1,
            name="Quick Dictionary",
            attack_type="dictionary",
            wordlist=str(Path(self.settings.WORDLISTS_DIR) / "rockyou.txt"),
            mode=self._get_hashcat_mode(),
            estimated_duration=300
        ))
        
        # Rule-based attack
        attacks.append(Attack(
            priority=2,
            name="Dictionary + Rules",
            attack_type="dictionary",
            wordlist=str(Path(self.settings.WORDLISTS_DIR) / "rockyou.txt"),
            rules=str(Path(self.settings.RULES_DIR) / "best64.rule"),
            mode=self._get_hashcat_mode(),
            estimated_duration=1800
        ))
        
        return attacks
    
    def _get_hashcat_mode(self) -> Optional[int]:
        """Get hashcat mode for job's hash type."""
        # This should map hash types to hashcat modes
        mode_mapping = {
            'MD5': 0,
            'SHA1': 100,
            'SHA256': 1400,
            'SHA512': 1700,
            'NTLM': 1000,
            'NetNTLMv1': 5500,
            'NetNTLMv2': 5600,
            'bcrypt': 3200
        }
        
        return mode_mapping.get(self.job.hash_type)
    
    def _should_stop_execution(self, attack_result: Dict) -> bool:
        """Determine if execution should stop based on results."""
        # Stop if we've cracked a high percentage of hashes
        if self.last_status.get('cracked_count', 0) > 0:
            total = self.job.total_hashes or 1
            cracked = self.last_status['cracked_count']
            percentage = (cracked / total) * 100
            
            # Stop if we've cracked more than 80%
            if percentage > 80:
                return True
        
        return False
    
    def _process_attack_results(self, attack: Attack, return_code: int) -> Dict[str, Any]:
        """Process results from a completed attack."""
        result = {
            'success': return_code == 0,
            'return_code': return_code,
            'attack_name': attack.name
        }
        
        # Read cracked passwords if available
        cracked_file = self.work_dir / 'cracked.txt'
        if cracked_file.exists():
            try:
                with open(cracked_file, 'r') as f:
                    cracked_lines = f.readlines()
                    result['cracked_count'] = len(cracked_lines)
            except IOError:
                result['cracked_count'] = 0
        
        return result
    
    def _calculate_final_results(self, execution_results: List[Dict]) -> Dict[str, Any]:
        """Calculate final execution results."""
        total_cracked = 0
        successful_attacks = 0
        
        for result in execution_results:
            attack_result = result['result']
            if attack_result.get('success'):
                successful_attacks += 1
            total_cracked += attack_result.get('cracked_count', 0)
        
        return {
            'success': successful_attacks > 0,
            'total_attacks': len(execution_results),
            'successful_attacks': successful_attacks,
            'final_cracked_count': total_cracked,
            'exhausted': successful_attacks == 0,
            'execution_results': execution_results
        }
    
    def _initialize_session(self):
        """Initialize hashcat session file."""
        try:
            # Create empty session file
            self.session_file.touch()
        except Exception as e:
            logger.error(f"Error initializing session: {e}")
    
    def cleanup(self):
        """Clean up service resources."""
        self._cleanup_process()
    
    def cleanup_job_files(self) -> Dict[str, Any]:
        """Clean up job-specific files."""
        try:
            if self.work_dir.exists():
                import shutil
                shutil.rmtree(self.work_dir)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error cleaning up job files: {e}")
            return {'success': False, 'error': str(e)}


class HashcatJobControl:
    """Service for controlling running hashcat jobs."""
    
    def __init__(self, job: Job, db_session: Session):
        self.job = job
        self.db = db_session
        self._stop_requested = False
        self._pause_requested = False
    
    def pause(self) -> Dict[str, Any]:
        """Pause the running job."""
        try:
            self._pause_requested = True
            # Implementation would send SIGSTOP to hashcat process
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def resume(self) -> Dict[str, Any]:
        """Resume a paused job."""
        try:
            self._pause_requested = False
            # Implementation would send SIGCONT to hashcat process  
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def cancel(self) -> Dict[str, Any]:
        """Cancel the running job."""
        try:
            self._stop_requested = True
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def should_stop(self) -> bool:
        """Check if job should stop execution."""
        return self._stop_requested
    
    def get_live_status(self) -> Dict[str, Any]:
        """Get live status of the job."""
        try:
            # This would read current status from hashcat
            return {'success': True, 'data': {}}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def cleanup(self):
        """Clean up control resources."""
        pass