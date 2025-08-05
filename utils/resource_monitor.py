import subprocess
import platform
import psutil
from typing import Dict, List, Any


class ResourceMonitor:
    """Monitor system resources and GPU availability."""
    
    def __init__(self):
        self.platform = platform.system()
        
    def get_resources(self) -> Dict[str, Any]:
        """Get current system resources."""
        resources = {
            'cpu': self._get_cpu_info(),
            'memory': self._get_memory_info(),
            'gpus': self._get_gpu_info(),
            'optimal_threads': self._calculate_optimal_threads()
        }
        return resources
    
    def _get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information."""
        return {
            'count': psutil.cpu_count(logical=False),
            'threads': psutil.cpu_count(logical=True),
            'usage_percent': psutil.cpu_percent(interval=1),
            'frequency': psutil.cpu_freq().current if psutil.cpu_freq() else 0
        }
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory information."""
        mem = psutil.virtual_memory()
        return {
            'total': mem.total,
            'available': mem.available,
            'percent': mem.percent,
            'free_gb': mem.available / (1024**3)
        }
    
    def _get_gpu_info(self) -> List[Dict[str, Any]]:
        """Get GPU information using nvidia-smi or rocm-smi."""
        gpus = []
        
        # Try NVIDIA GPUs
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=index,name,memory.total,memory.free,utilization.gpu', 
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(', ')
                    gpus.append({
                        'index': int(parts[0]),
                        'name': parts[1],
                        'memory_total': int(parts[2]),
                        'memory_free': int(parts[3]),
                        'utilization': int(parts[4]),
                        'type': 'nvidia'
                    })
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Try AMD GPUs
        try:
            result = subprocess.run(
                ['rocm-smi', '--showmeminfo', 'vram'],
                capture_output=True,
                text=True,
                check=True
            )
            # Parse AMD GPU info (format varies)
            # This is a simplified version
            if 'GPU' in result.stdout:
                gpus.append({
                    'index': 0,
                    'name': 'AMD GPU',
                    'type': 'amd'
                })
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return gpus
    
    def _calculate_optimal_threads(self) -> int:
        """Calculate optimal number of threads for hashcat."""
        cpu_info = self._get_cpu_info()
        mem_info = self._get_memory_info()
        
        # Base it on CPU threads, but leave some for system
        optimal = max(1, cpu_info['threads'] - 2)
        
        # Reduce if memory is low
        if mem_info['free_gb'] < 4:
            optimal = max(1, optimal // 2)
        
        return optimal
    
    def check_hashcat_availability(self) -> Dict[str, Any]:
        """Check if hashcat is available and get version."""
        try:
            result = subprocess.run(
                ['hashcat', '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            version = result.stdout.strip()
            
            # Parse version number for compatibility checks
            version_parts = version.replace('v', '').split('.')
            major_version = int(version_parts[0]) if version_parts else 0
            
            # Check for OpenCL/CUDA support
            result = subprocess.run(
                ['hashcat', '-I'],
                capture_output=True,
                text=True,
                check=True
            )
            
            devices = []
            for line in result.stdout.split('\n'):
                if 'Backend Device ID' in line:
                    devices.append(line.strip())
            
            return {
                'available': True,
                'version': version,
                'major_version': major_version,
                'supports_autodetect': major_version >= 7,
                'devices': devices
            }
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {
                'available': False,
                'error': 'Hashcat not found or not properly installed'
            }
    
    def suggest_performance_settings(self) -> Dict[str, Any]:
        """Suggest performance settings based on available resources."""
        resources = self.get_resources()
        suggestions = {}
        
        # Workload profile
        if resources['gpus']:
            # Have GPU - use high performance
            suggestions['workload_profile'] = 4
            suggestions['optimized_kernel'] = True
        else:
            # CPU only - use balanced
            suggestions['workload_profile'] = 2
            suggestions['optimized_kernel'] = False
        
        # Memory-based suggestions
        if resources['memory']['free_gb'] > 16:
            suggestions['bitmap_max'] = 24
            suggestions['segment_size'] = 512
        else:
            suggestions['bitmap_max'] = 22
            suggestions['segment_size'] = 256
        
        # GPU-specific
        if resources['gpus']:
            total_vram = sum(gpu.get('memory_total', 0) for gpu in resources['gpus'])
            if total_vram > 8000:  # 8GB+ VRAM
                suggestions['kernel_accel'] = 32
                suggestions['kernel_loops'] = 1024
            else:
                suggestions['kernel_accel'] = 16
                suggestions['kernel_loops'] = 512
        
        return suggestions