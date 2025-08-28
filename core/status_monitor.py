"""
Real-time status monitoring for hashcat processes with JSON output support.
Provides live updates on cracking progress, performance metrics, and estimates.
"""

import json
import re
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

from .logger import get_logger


class StatusFormat(Enum):
    """Status output formats."""
    HUMAN = "human"
    JSON = "json"
    MACHINE = "machine"


@dataclass
class HashcatStatus:
    """Hashcat status information."""
    status: str
    speed: List[int]  # Speed per device
    speed_unit: str
    progress: int
    progress_total: int
    progress_percent: float
    time_started: str
    estimated_stop: str
    recovered: int
    recovered_total: int
    recovered_percent: float
    rejected: int
    restore_point: int
    temperature: List[int]  # Temperature per device
    util: List[int]  # Utilization per device


@dataclass
class AttackStatus:
    """Complete attack status information."""
    session_id: str
    attack_name: str
    hash_type: str
    hash_target: str
    time_started: str
    time_running: str
    time_estimated: str
    speed_total: int
    speed_unit: str
    progress_percent: float
    hashes_total: int
    hashes_recovered: int
    hashes_remaining: int
    recovery_rate: float
    devices: List[Dict[str, Any]]
    current_wordlist: Optional[str]
    current_rule: Optional[str]
    current_mask: Optional[str]


class StatusMonitor:
    """Monitor hashcat process status in real-time."""
    
    def __init__(self, format_type: StatusFormat = StatusFormat.HUMAN,
                 update_interval: int = 10,
                 output_file: Optional[str] = None):
        """
        Initialize status monitor.
        
        Args:
            format_type: Output format (human, json, machine)
            update_interval: Seconds between updates
            output_file: Optional file to write status updates
        """
        self.format_type = format_type
        self.update_interval = update_interval
        self.output_file = output_file
        self.logger = get_logger('status_monitor')
        
        # Status tracking
        self.current_status: Optional[AttackStatus] = None
        self.status_history: List[AttackStatus] = []
        self.monitor_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Callbacks
        self.status_callbacks: List[Callable[[AttackStatus], None]] = []
        
        # Regex patterns for parsing hashcat output
        self.patterns = {
            'status': re.compile(r'Status\.*: (.+)'),
            'speed': re.compile(r'Speed\.#\d+\.*: *(\d+(?:\.\d+)?)\s*([kMGT]?H/s)'),
            'speed_total': re.compile(r'Speed\.#\*\.*: *(\d+(?:\.\d+)?)\s*([kMGT]?H/s)'),
            'progress': re.compile(r'Progress\.*: (\d+)/(\d+) \((\d+(?:\.\d+)?%)\)'),
            'recovered': re.compile(r'Recovered\.*: (\d+)/(\d+) \((\d+(?:\.\d+)?%)\)'),
            'time_started': re.compile(r'Time\.Started\.*: (.+)'),
            'time_estimated': re.compile(r'Time\.Estimated\.*: (.+)'),
            'temperature': re.compile(r'Temp:\s*(\d+)c'),
            'util': re.compile(r'Util\.#\d+\.*: *(\d+)%'),
            'rejected': re.compile(r'Rejected\.*: (\d+)'),
            'restore_point': re.compile(r'Restore\.Point\.*: (\d+)'),
            'candidates': re.compile(r'Candidates\.#\d+\.*: (.+)'),
            'hardware': re.compile(r'Backend Device ID #(\d+).*')
        }
    
    def start_monitoring(self, process, session_id: str, attack_info: Dict[str, Any]):
        """
        Start monitoring a hashcat process.
        
        Args:
            process: Subprocess.Popen instance
            session_id: Session identifier
            attack_info: Attack information
        """
        if self.running:
            self.logger.warning("Monitor already running, stopping previous instance")
            self.stop_monitoring()
        
        self.running = True
        self.session_id = session_id
        self.attack_info = attack_info
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(process,),
            daemon=True,
            name="StatusMonitor"
        )
        self.monitor_thread.start()
        
        self.logger.info("Started status monitoring", 
                        session_id=session_id,
                        attack=attack_info.get('name'))
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            self.monitor_thread = None
        
        self.logger.info("Stopped status monitoring")
    
    def add_callback(self, callback: Callable[[AttackStatus], None]):
        """Add a status update callback."""
        self.status_callbacks.append(callback)
    
    def _monitor_loop(self, process):
        """Main monitoring loop."""
        last_update = 0
        output_buffer = ""
        
        while self.running and process.poll() is None:
            # Read process output
            try:
                # Non-blocking read from stdout
                line = process.stdout.readline()
                if line:
                    output_buffer += line
                    
                    # Check if we have a complete status block
                    if self._is_status_block_complete(output_buffer):
                        # Parse status
                        status = self._parse_hashcat_status(output_buffer)
                        if status:
                            self._update_status(status)
                        output_buffer = ""
                
                # Send periodic updates
                current_time = time.time()
                if current_time - last_update >= self.update_interval:
                    if self.current_status:
                        self._send_status_update()
                    last_update = current_time
                    
            except Exception as e:
                self.logger.error("Error in monitor loop", error=e)
                
            time.sleep(0.1)  # Small delay to prevent CPU spinning
    
    def _is_status_block_complete(self, output: str) -> bool:
        """Check if output contains a complete status block."""
        # Hashcat status blocks typically end with a specific pattern
        return ("Time.Estimated" in output or "Rejected" in output or 
                "[s]tatus" in output or output.count('\n') > 10)
    
    def _parse_hashcat_status(self, output: str) -> Optional[HashcatStatus]:
        """Parse hashcat status output."""
        try:
            status = HashcatStatus(
                status="Running",
                speed=[],
                speed_unit="H/s",
                progress=0,
                progress_total=0,
                progress_percent=0.0,
                time_started="",
                estimated_stop="",
                recovered=0,
                recovered_total=0,
                recovered_percent=0.0,
                rejected=0,
                restore_point=0,
                temperature=[],
                util=[]
            )
            
            lines = output.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Status
                match = self.patterns['status'].search(line)
                if match:
                    status.status = match.group(1).strip()
                
                # Speed per device
                match = self.patterns['speed'].search(line)
                if match:
                    speed_val = float(match.group(1))
                    speed_unit = match.group(2)
                    # Convert to H/s
                    speed_h = self._convert_speed_to_hs(speed_val, speed_unit)
                    status.speed.append(speed_h)
                    status.speed_unit = "H/s"
                
                # Progress
                match = self.patterns['progress'].search(line)
                if match:
                    status.progress = int(match.group(1))
                    status.progress_total = int(match.group(2))
                    status.progress_percent = float(match.group(3).rstrip('%'))
                
                # Recovered
                match = self.patterns['recovered'].search(line)
                if match:
                    status.recovered = int(match.group(1))
                    status.recovered_total = int(match.group(2))
                    status.recovered_percent = float(match.group(3).rstrip('%'))
                
                # Time started
                match = self.patterns['time_started'].search(line)
                if match:
                    status.time_started = match.group(1).strip()
                
                # Estimated stop
                match = self.patterns['time_estimated'].search(line)
                if match:
                    status.estimated_stop = match.group(1).strip()
                
                # Temperature
                match = self.patterns['temperature'].search(line)
                if match:
                    status.temperature.append(int(match.group(1)))
                
                # Utilization
                match = self.patterns['util'].search(line)
                if match:
                    status.util.append(int(match.group(1)))
                
                # Rejected
                match = self.patterns['rejected'].search(line)
                if match:
                    status.rejected = int(match.group(1))
                
                # Restore point
                match = self.patterns['restore_point'].search(line)
                if match:
                    status.restore_point = int(match.group(1))
            
            # Validate we got meaningful data
            if status.progress_total > 0 or status.recovered_total > 0:
                return status
            
        except Exception as e:
            self.logger.error("Failed to parse status", error=e, output=output[:200])
        
        return None
    
    def _convert_speed_to_hs(self, value: float, unit: str) -> int:
        """Convert speed to hashes per second."""
        multipliers = {
            'H/s': 1,
            'kH/s': 1000,
            'MH/s': 1000000,
            'GH/s': 1000000000,
            'TH/s': 1000000000000
        }
        
        multiplier = multipliers.get(unit, 1)
        return int(value * multiplier)
    
    def _update_status(self, hashcat_status: HashcatStatus):
        """Update current attack status."""
        # Calculate runtime
        start_time = datetime.now()
        if hashcat_status.time_started:
            try:
                # Parse hashcat time format
                start_time = datetime.strptime(
                    hashcat_status.time_started,
                    "%a %b %d %H:%M:%S %Y"
                )
            except:
                pass
        
        runtime = datetime.now() - start_time
        
        # Build device information
        devices = []
        for i, speed in enumerate(hashcat_status.speed):
            device_info = {
                'id': i,
                'speed': speed,
                'speed_unit': 'H/s',
                'temperature': hashcat_status.temperature[i] if i < len(hashcat_status.temperature) else 0,
                'utilization': hashcat_status.util[i] if i < len(hashcat_status.util) else 0
            }
            devices.append(device_info)
        
        # Create attack status
        self.current_status = AttackStatus(
            session_id=self.session_id,
            attack_name=self.attack_info.get('name', 'Unknown'),
            hash_type=self.attack_info.get('hash_type', 'Unknown'),
            hash_target=self.attack_info.get('hash_file', 'Unknown'),
            time_started=hashcat_status.time_started,
            time_running=str(runtime).split('.')[0],  # Remove microseconds
            time_estimated=hashcat_status.estimated_stop,
            speed_total=sum(hashcat_status.speed),
            speed_unit='H/s',
            progress_percent=hashcat_status.progress_percent,
            hashes_total=hashcat_status.recovered_total,
            hashes_recovered=hashcat_status.recovered,
            hashes_remaining=hashcat_status.recovered_total - hashcat_status.recovered,
            recovery_rate=hashcat_status.recovered_percent,
            devices=devices,
            current_wordlist=self.attack_info.get('wordlist'),
            current_rule=self.attack_info.get('rules'),
            current_mask=self.attack_info.get('mask')
        )
        
        # Add to history
        self.status_history.append(self.current_status)
        
        # Trigger callbacks
        for callback in self.status_callbacks:
            try:
                callback(self.current_status)
            except Exception as e:
                self.logger.error("Status callback error", error=e)
    
    def _send_status_update(self):
        """Send status update in configured format."""
        if not self.current_status:
            return
        
        output = self._format_status(self.current_status)
        
        # Print to console
        print(output)
        
        # Write to file if configured
        if self.output_file:
            try:
                with open(self.output_file, 'a') as f:
                    f.write(output + '\n')
            except Exception as e:
                self.logger.error("Failed to write status file", error=e)
    
    def _format_status(self, status: AttackStatus) -> str:
        """Format status based on output type."""
        if self.format_type == StatusFormat.JSON:
            return json.dumps(asdict(status), default=str)
        
        elif self.format_type == StatusFormat.MACHINE:
            # Machine-readable format (key=value pairs)
            parts = [
                f"session={status.session_id}",
                f"attack={status.attack_name}",
                f"progress={status.progress_percent:.2f}",
                f"speed={status.speed_total}",
                f"recovered={status.hashes_recovered}/{status.hashes_total}",
                f"runtime={status.time_running}",
                f"eta={status.time_estimated}"
            ]
            return " ".join(parts)
        
        else:  # HUMAN format
            lines = [
                f"\n[Status Update - {datetime.now().strftime('%H:%M:%S')}]",
                f"Session: {status.session_id}",
                f"Attack: {status.attack_name}",
                f"Progress: {status.progress_percent:.1f}%",
                f"Speed: {self._format_speed(status.speed_total)}",
                f"Recovered: {status.hashes_recovered}/{status.hashes_total} ({status.recovery_rate:.1f}%)",
                f"Runtime: {status.time_running}",
                f"ETA: {status.time_estimated}"
            ]
            
            # Add device info
            if status.devices:
                lines.append("\nDevices:")
                for dev in status.devices:
                    lines.append(f"  GPU #{dev['id']}: {self._format_speed(dev['speed'])} "
                               f"(Temp: {dev['temperature']}°C, Util: {dev['utilization']}%)")
            
            return "\n".join(lines)
    
    def _format_speed(self, speed_hs: int) -> str:
        """Format speed in human-readable format."""
        if speed_hs >= 1000000000000:
            return f"{speed_hs / 1000000000000:.2f} TH/s"
        elif speed_hs >= 1000000000:
            return f"{speed_hs / 1000000000:.2f} GH/s"
        elif speed_hs >= 1000000:
            return f"{speed_hs / 1000000:.2f} MH/s"
        elif speed_hs >= 1000:
            return f"{speed_hs / 1000:.2f} kH/s"
        else:
            return f"{speed_hs} H/s"
    
    def get_current_status(self) -> Optional[AttackStatus]:
        """Get current status."""
        return self.current_status
    
    def get_status_history(self) -> List[AttackStatus]:
        """Get status history."""
        return self.status_history.copy()
    
    def export_summary(self, output_file: str):
        """Export status summary to file."""
        if not self.status_history:
            return
        
        summary = {
            'session_id': self.session_id,
            'attack_info': self.attack_info,
            'total_updates': len(self.status_history),
            'start_time': self.status_history[0].time_started if self.status_history else None,
            'end_time': self.status_history[-1].time_started if self.status_history else None,
            'final_status': asdict(self.status_history[-1]) if self.status_history else None,
            'performance_history': [
                {
                    'timestamp': status.time_started,
                    'speed': status.speed_total,
                    'progress': status.progress_percent,
                    'recovered': status.hashes_recovered
                }
                for status in self.status_history
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        self.logger.info("Exported status summary", file=output_file)