#!/usr/bin/env python3
"""
HashWrap - Simplified Hashcat Worker
Integrates with existing hashwrap system for actual hash cracking
"""

import os
import sys
import sqlite3
import subprocess
import threading
import time
import json
import signal
import glob
from datetime import datetime

# Add the existing hashwrap modules to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from core.hash_analyzer import HashAnalyzer
    from core.hash_manager import HashManager
    from core.security import SecurityValidator
    HASHWRAP_AVAILABLE = True
except ImportError:
    print("Warning: Original hashwrap modules not available. Using basic functionality.")
    HASHWRAP_AVAILABLE = False

class SimpleHashcatWorker:
    def __init__(self, database_path="hashwrap.db"):
        self.database_path = database_path
        self.running_jobs = {}
        self.should_stop = False
        
        # Initialize existing hashwrap components if available
        if HASHWRAP_AVAILABLE:
            try:
                self.hash_analyzer = HashAnalyzer()
                self.hash_manager = HashManager()
                self.security = SecurityValidator()
            except Exception as e:
                print(f"Warning: Could not initialize hashwrap components: {e}")
                self.hash_analyzer = None
                self.hash_manager = None
                self.security = None
        else:
            self.hash_analyzer = None
            self.hash_manager = None
            self.security = None
    
    def start(self):
        """Start the worker daemon"""
        print("🚀 Starting HashWrap Worker...")
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Start background threads
        threading.Thread(target=self._job_processor, daemon=True).start()
        threading.Thread(target=self._directory_watcher, daemon=True).start()
        
        print("✅ Worker started. Monitoring for jobs...")
        
        # Main loop
        try:
            while not self.should_stop:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        
        self._shutdown()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n📡 Received signal {signum}. Shutting down gracefully...")
        self.should_stop = True
    
    def _shutdown(self):
        """Graceful shutdown"""
        print("🛑 Stopping running jobs...")
        
        for job_id, process in self.running_jobs.items():
            try:
                process.terminate()
                print(f"   Stopped job {job_id}")
            except:
                pass
        
        print("✅ Worker shutdown complete.")
    
    def _job_processor(self):
        """Main job processing loop"""
        while not self.should_stop:
            try:
                # Check for queued jobs
                conn = sqlite3.connect(self.database_path)
                conn.row_factory = sqlite3.Row
                
                jobs = conn.execute('''
                    SELECT * FROM jobs 
                    WHERE status = 'queued' 
                    ORDER BY created_at ASC
                    LIMIT 1
                ''').fetchall()
                
                conn.close()
                
                for job in jobs:
                    if not self.should_stop:
                        self._process_job(job)
                
            except Exception as e:
                print(f"❌ Job processor error: {e}")
            
            time.sleep(5)  # Check every 5 seconds
    
    def _directory_watcher(self):
        """Watch for new files in upload directory"""
        upload_dir = "data/uploads"
        processed_files = set()
        
        while not self.should_stop:
            try:
                if os.path.exists(upload_dir):
                    for file_path in glob.glob(os.path.join(upload_dir, "*")):
                        if file_path not in processed_files and os.path.isfile(file_path):
                            filename = os.path.basename(file_path)
                            
                            # Check if already in database
                            conn = sqlite3.connect(self.database_path)
                            existing = conn.execute(
                                'SELECT id FROM jobs WHERE filename = ?', 
                                (filename,)
                            ).fetchone()
                            
                            if not existing:
                                # Auto-create job for new file
                                hash_type = self._detect_hash_type(file_path)
                                total_hashes = self._count_hashes(file_path)
                                
                                conn.execute('''
                                    INSERT INTO jobs (filename, hash_type, total_hashes, status)
                                    VALUES (?, ?, ?, 'queued')
                                ''', (filename, hash_type, total_hashes))
                                conn.commit()
                                
                                print(f"📁 Auto-created job for {filename} ({hash_type})")
                            
                            conn.close()
                            processed_files.add(file_path)
                
            except Exception as e:
                print(f"❌ Directory watcher error: {e}")
            
            time.sleep(60)  # Check every minute
    
    def _detect_hash_type(self, file_path):
        """Detect hash type using hashwrap analyzer or basic detection"""
        if self.hash_analyzer:
            try:
                with open(file_path, 'r') as f:
                    sample_hashes = [line.strip() for line in f.readlines()[:10] if line.strip()]
                
                if sample_hashes:
                    detection_result = self.hash_analyzer.analyze_hashes(sample_hashes)
                    if detection_result and detection_result.get('primary_type'):
                        return detection_result['primary_type']
            except Exception as e:
                print(f"Warning: Advanced hash detection failed: {e}")
        
        # Fallback to basic detection
        return self._basic_hash_detection(file_path)
    
    def _basic_hash_detection(self, file_path):
        """Basic hash type detection"""
        try:
            with open(file_path, 'r') as f:
                first_line = f.readline().strip()
            
            if not first_line:
                return "unknown"
            
            hash_length = len(first_line)
            
            if hash_length == 32 and all(c in '0123456789abcdefABCDEF' for c in first_line):
                return "MD5"
            elif hash_length == 40 and all(c in '0123456789abcdefABCDEF' for c in first_line):
                return "SHA1"
            elif hash_length == 64 and all(c in '0123456789abcdefABCDEF' for c in first_line):
                return "SHA256"
            elif ':' in first_line and len(first_line.split(':')) >= 6:
                return "NTLM"
            elif '$' in first_line:
                if '$1$' in first_line:
                    return "MD5crypt"
                elif '$2' in first_line or '$2a$' in first_line or '$2b$' in first_line:
                    return "bcrypt"
                elif '$6$' in first_line:
                    return "SHA512crypt"
            
            return "unknown"
        except:
            return "unknown"
    
    def _count_hashes(self, file_path):
        """Count hashes in file"""
        try:
            with open(file_path, 'r') as f:
                return sum(1 for line in f if line.strip())
        except:
            return 0
    
    def _process_job(self, job):
        """Process a single job"""
        job_id = job['id']
        filename = job['filename']
        hash_type = job['hash_type']
        
        print(f"🔄 Starting job {job_id}: {filename} ({hash_type})")
        
        try:
            # Update job status
            self._update_job_status(job_id, 'running', started_at=datetime.now())
            
            # Build hashcat command
            input_file = os.path.join("data/uploads", filename)
            output_file = os.path.join("data/results", f"job_{job_id}_results.txt")
            
            # Use existing hashwrap if available, otherwise basic hashcat
            if HASHWRAP_AVAILABLE and self.hash_manager:
                success = self._run_with_hashwrap(job, input_file, output_file)
            else:
                success = self._run_basic_hashcat(job, input_file, output_file)
            
            if success:
                # Process results
                cracked_count = self._process_results(job_id, output_file)
                self._update_job_status(job_id, 'completed', 
                                      completed_at=datetime.now(),
                                      cracked_count=cracked_count)
                print(f"✅ Job {job_id} completed: {cracked_count} passwords cracked")
            else:
                self._update_job_status(job_id, 'failed', completed_at=datetime.now())
                print(f"❌ Job {job_id} failed")
                
        except Exception as e:
            print(f"❌ Job {job_id} error: {e}")
            self._update_job_status(job_id, 'failed', completed_at=datetime.now())
        finally:
            if job_id in self.running_jobs:
                del self.running_jobs[job_id]
    
    def _run_with_hashwrap(self, job, input_file, output_file):
        """Run using existing hashwrap functionality"""
        try:
            # Use hashwrap's attack orchestrator for smart cracking
            from core.attack_orchestrator import AttackOrchestrator
            orchestrator = AttackOrchestrator()
            
            # Create session using hashwrap
            session_id = f"webapp_job_{job['id']}"
            
            # This would integrate with the existing hashwrap system
            # For now, fall back to basic hashcat
            return self._run_basic_hashcat(job, input_file, output_file)
            
        except Exception as e:
            print(f"Warning: Hashwrap integration failed: {e}")
            return self._run_basic_hashcat(job, input_file, output_file)
    
    def _run_basic_hashcat(self, job, input_file, output_file):
        """Run basic hashcat command"""
        try:
            # Map hash types to hashcat modes
            hashcat_modes = {
                'MD5': '0',
                'SHA1': '100', 
                'SHA256': '1400',
                'SHA512': '1700',
                'NTLM': '1000',
                'bcrypt': '3200',
                'MD5crypt': '500',
                'SHA512crypt': '1800'
            }
            
            mode = hashcat_modes.get(job['hash_type'], '0')
            
            # Basic wordlist (you should have rockyou.txt or similar)
            wordlist = "wordlists/rockyou.txt"
            if not os.path.exists(wordlist):
                wordlist = "wordlists/common-passwords.txt"
                if not os.path.exists(wordlist):
                    print(f"⚠️ No wordlist found. Creating basic wordlist...")
                    os.makedirs("wordlists", exist_ok=True)
                    with open(wordlist, 'w') as f:
                        # Basic password list
                        passwords = [
                            'password', '123456', 'password123', 'admin', 'letmein',
                            'welcome', 'monkey', '1234567890', 'qwerty', 'abc123',
                            'Password1', 'admin123', 'root', 'toor', 'pass'
                        ]
                        f.write('\n'.join(passwords))
            
            # Build command
            cmd = [
                'hashcat',
                '-m', mode,
                '-a', '0',  # Dictionary attack
                '--force',
                '--potfile-disable',
                '-o', output_file,
                '--outfile-format=2',  # Plain text
                input_file,
                wordlist
            ]
            
            print(f"🔧 Running: {' '.join(cmd)}")
            
            # Run hashcat
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.running_jobs[job['id']] = process
            
            # Wait for completion
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                return True
            else:
                print(f"❌ Hashcat failed: {stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Basic hashcat error: {e}")
            return False
    
    def _process_results(self, job_id, output_file):
        """Process cracked results and store in database"""
        cracked_count = 0
        
        try:
            if os.path.exists(output_file):
                conn = sqlite3.connect(self.database_path)
                
                with open(output_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            # Format: hash:password
                            if ':' in line:
                                hash_val, password = line.split(':', 1)
                                
                                conn.execute('''
                                    INSERT INTO results (job_id, hash_value, password)
                                    VALUES (?, ?, ?)
                                ''', (job_id, hash_val, password))
                                
                                cracked_count += 1
                
                conn.commit()
                conn.close()
        
        except Exception as e:
            print(f"❌ Result processing error: {e}")
        
        return cracked_count
    
    def _update_job_status(self, job_id, status, **kwargs):
        """Update job status in database"""
        conn = sqlite3.connect(self.database_path)
        
        update_fields = ['status = ?']
        update_values = [status]
        
        for field, value in kwargs.items():
            update_fields.append(f'{field} = ?')
            update_values.append(value)
        
        update_values.append(job_id)
        
        conn.execute(f'''
            UPDATE jobs 
            SET {', '.join(update_fields)}
            WHERE id = ?
        ''', update_values)
        
        conn.commit()
        conn.close()


if __name__ == "__main__":
    worker = SimpleHashcatWorker()
    worker.start()