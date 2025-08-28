#!/usr/bin/env python3
"""
HashWrap Worker Startup Script

Provides easy startup for different worker types and configurations.
Handles environment validation, dependency checks, and worker initialization.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.core.config import get_settings
from worker.celery_app import CeleryConfig


class WorkerManager:
    """Manages HashWrap worker processes."""
    
    def __init__(self):
        self.settings = get_settings()
        self.config = CeleryConfig()
    
    def validate_environment(self) -> Dict[str, bool]:
        """Validate that the environment is ready for workers."""
        checks = {}
        
        # Check Redis connectivity
        try:
            import redis
            r = redis.Redis.from_url(self.settings.REDIS_URL)
            r.ping()
            checks['redis'] = True
        except Exception as e:
            print(f"Redis check failed: {e}")
            checks['redis'] = False
        
        # Check database connectivity
        try:
            from worker.utils.database import DatabaseHealthCheck
            checks['database'] = DatabaseHealthCheck.check_connection()
        except Exception as e:
            print(f"Database check failed: {e}")
            checks['database'] = False
        
        # Check required directories
        directories = [
            self.settings.UPLOAD_DIR,
            self.settings.RESULTS_DIR,
            self.settings.WORDLISTS_DIR,
            self.settings.RULES_DIR
        ]
        
        checks['directories'] = True
        for dir_path in directories:
            path = Path(dir_path)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    print(f"Created directory: {path}")
                except Exception as e:
                    print(f"Failed to create directory {path}: {e}")
                    checks['directories'] = False
        
        # Check hashcat availability
        try:
            result = subprocess.run(
                ['hashcat', '--version'], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            checks['hashcat'] = result.returncode == 0
            if checks['hashcat']:
                version_line = result.stdout.split('\n')[0] if result.stdout else result.stderr.split('\n')[0]
                print(f"Hashcat found: {version_line}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("Hashcat not found in PATH")
            checks['hashcat'] = False
        
        # Check Python dependencies
        required_packages = [
            'celery', 'redis', 'structlog', 'psutil', 
            'sqlalchemy', 'aiohttp', 'pydantic'
        ]
        
        checks['dependencies'] = True
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                print(f"Missing required package: {package}")
                checks['dependencies'] = False
        
        return checks
    
    def start_worker(self, queue: str = 'default', **kwargs) -> subprocess.Popen:
        """Start a Celery worker for the specified queue."""
        queue_info = self.config.get_queue_info()
        
        if queue not in queue_info:
            raise ValueError(f"Unknown queue: {queue}. Available: {list(queue_info.keys())}")
        
        info = queue_info[queue]
        
        # Build command
        cmd = [
            'celery', '-A', 'worker.celery_app', 'worker',
            '-Q', queue,
            '--concurrency', str(kwargs.get('concurrency', info['concurrency'])),
            '--prefetch-multiplier', str(kwargs.get('prefetch', info['prefetch'])),
            '--loglevel', kwargs.get('loglevel', 'info')
        ]
        
        # Add optional arguments
        if kwargs.get('hostname'):
            cmd.extend(['--hostname', kwargs['hostname']])
        
        if kwargs.get('max_tasks'):
            cmd.extend(['--max-tasks-per-child', str(kwargs['max_tasks'])])
        
        print(f"Starting worker for queue '{queue}': {' '.join(cmd)}")
        
        # Start worker process
        process = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        
        return process
    
    def start_beat(self, **kwargs) -> subprocess.Popen:
        """Start Celery Beat scheduler."""
        cmd = [
            'celery', '-A', 'worker.celery_app', 'beat',
            '--loglevel', kwargs.get('loglevel', 'info')
        ]
        
        if kwargs.get('pidfile'):
            cmd.extend(['--pidfile', kwargs['pidfile']])
        
        if kwargs.get('schedule'):
            cmd.extend(['--schedule', kwargs['schedule']])
        
        print(f"Starting Beat scheduler: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        
        return process
    
    def start_flower(self, **kwargs) -> subprocess.Popen:
        """Start Celery Flower monitoring."""
        cmd = [
            'celery', '-A', 'worker.celery_app', 'flower',
            '--port', str(kwargs.get('port', 5555)),
            '--address', kwargs.get('address', '0.0.0.0')
        ]
        
        if kwargs.get('basic_auth'):
            cmd.extend(['--basic_auth', kwargs['basic_auth']])
        
        print(f"Starting Flower monitoring: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        
        return process
    
    def get_worker_recommendations(self) -> Dict[str, Dict]:
        """Get worker deployment recommendations based on system resources."""
        try:
            import psutil
            
            cpu_count = psutil.cpu_count()
            memory_gb = psutil.virtual_memory().total / (1024**3)
            
            recommendations = {
                'hashcat': {
                    'instances': min(2, max(1, self.settings.MAX_CONCURRENT_JOBS)),
                    'reason': 'Limited by MAX_CONCURRENT_JOBS setting'
                },
                'monitoring': {
                    'instances': 1,
                    'reason': 'Single instance sufficient for metrics collection'
                },
                'watcher': {
                    'instances': 1,
                    'reason': 'Single instance to avoid file processing conflicts'
                },
                'control': {
                    'instances': 1,
                    'reason': 'Single instance sufficient for job control'
                },
                'maintenance': {
                    'instances': 1,
                    'reason': 'Single instance sufficient for cleanup tasks'
                },
                'default': {
                    'instances': max(2, cpu_count // 2),
                    'reason': 'Scale with CPU cores for general tasks'
                }
            }
            
            return recommendations
            
        except ImportError:
            # Fallback if psutil not available
            return {
                'hashcat': {'instances': 2, 'reason': 'Default recommendation'},
                'monitoring': {'instances': 1, 'reason': 'Default recommendation'},
                'watcher': {'instances': 1, 'reason': 'Default recommendation'},
                'control': {'instances': 1, 'reason': 'Default recommendation'},
                'maintenance': {'instances': 1, 'reason': 'Default recommendation'},
                'default': {'instances': 2, 'reason': 'Default recommendation'}
            }


def main():
    """Main entry point for worker management."""
    parser = argparse.ArgumentParser(description='HashWrap Worker Management')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check environment')
    
    # Worker command
    worker_parser = subparsers.add_parser('worker', help='Start worker')
    worker_parser.add_argument('queue', nargs='?', default='default', 
                             help='Queue name to process')
    worker_parser.add_argument('--concurrency', type=int, 
                             help='Number of concurrent processes')
    worker_parser.add_argument('--prefetch', type=int,
                             help='Prefetch multiplier')
    worker_parser.add_argument('--loglevel', default='info',
                             choices=['debug', 'info', 'warning', 'error'],
                             help='Log level')
    worker_parser.add_argument('--hostname', help='Worker hostname')
    worker_parser.add_argument('--max-tasks', type=int, default=50,
                             help='Max tasks per child process')
    
    # Beat command  
    beat_parser = subparsers.add_parser('beat', help='Start beat scheduler')
    beat_parser.add_argument('--loglevel', default='info',
                           choices=['debug', 'info', 'warning', 'error'],
                           help='Log level')
    beat_parser.add_argument('--pidfile', help='PID file path')
    beat_parser.add_argument('--schedule', help='Schedule file path')
    
    # Flower command
    flower_parser = subparsers.add_parser('flower', help='Start flower monitoring')
    flower_parser.add_argument('--port', type=int, default=5555,
                             help='Flower port')
    flower_parser.add_argument('--address', default='0.0.0.0',
                             help='Flower bind address')
    flower_parser.add_argument('--basic-auth', help='Basic auth credentials (user:pass)')
    
    # Multi command
    multi_parser = subparsers.add_parser('multi', help='Start multiple workers')
    multi_parser.add_argument('--recommended', action='store_true',
                            help='Use recommended worker configuration')
    multi_parser.add_argument('--with-beat', action='store_true',
                            help='Also start beat scheduler')
    multi_parser.add_argument('--with-flower', action='store_true',
                            help='Also start flower monitoring')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show worker status')
    
    # Recommendations command
    rec_parser = subparsers.add_parser('recommend', help='Show deployment recommendations')
    
    args = parser.parse_args()
    
    manager = WorkerManager()
    
    if args.command == 'check':
        print("Checking HashWrap worker environment...")
        checks = manager.validate_environment()
        
        all_passed = True
        for check, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"{status} {check.title()}: {'OK' if passed else 'FAILED'}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print("\n✓ Environment is ready for workers!")
            sys.exit(0)
        else:
            print("\n✗ Environment checks failed. Please fix the issues above.")
            sys.exit(1)
    
    elif args.command == 'worker':
        checks = manager.validate_environment()
        if not all(checks.values()):
            print("Environment checks failed. Run 'check' command for details.")
            sys.exit(1)
        
        try:
            process = manager.start_worker(
                queue=args.queue,
                concurrency=args.concurrency,
                prefetch=args.prefetch,
                loglevel=args.loglevel,
                hostname=args.hostname,
                max_tasks=args.max_tasks
            )
            
            process.wait()
            
        except KeyboardInterrupt:
            print("\nShutting down worker...")
            process.terminate()
            process.wait()
    
    elif args.command == 'beat':
        checks = manager.validate_environment()
        if not all(checks.values()):
            print("Environment checks failed. Run 'check' command for details.")
            sys.exit(1)
        
        try:
            process = manager.start_beat(
                loglevel=args.loglevel,
                pidfile=args.pidfile,
                schedule=args.schedule
            )
            
            process.wait()
            
        except KeyboardInterrupt:
            print("\nShutting down beat scheduler...")
            process.terminate()
            process.wait()
    
    elif args.command == 'flower':
        try:
            process = manager.start_flower(
                port=args.port,
                address=args.address,
                basic_auth=args.basic_auth
            )
            
            print(f"Flower monitoring available at http://{args.address}:{args.port}")
            process.wait()
            
        except KeyboardInterrupt:
            print("\nShutting down flower...")
            process.terminate()
            process.wait()
    
    elif args.command == 'multi':
        checks = manager.validate_environment()
        if not all(checks.values()):
            print("Environment checks failed. Run 'check' command for details.")
            sys.exit(1)
        
        processes = []
        
        try:
            if args.recommended:
                recommendations = manager.get_worker_recommendations()
                
                for queue, rec in recommendations.items():
                    for i in range(rec['instances']):
                        hostname = f"{queue}-{i+1}" if rec['instances'] > 1 else queue
                        process = manager.start_worker(
                            queue=queue,
                            hostname=hostname
                        )
                        processes.append((f"{queue}-{i+1}", process))
            
            if args.with_beat:
                beat_process = manager.start_beat()
                processes.append(('beat', beat_process))
            
            if args.with_flower:
                flower_process = manager.start_flower()
                processes.append(('flower', flower_process))
            
            # Wait for all processes
            print(f"Started {len(processes)} processes. Press Ctrl+C to stop all.")
            
            for name, process in processes:
                process.wait()
                
        except KeyboardInterrupt:
            print("\nShutting down all processes...")
            for name, process in processes:
                print(f"Terminating {name}...")
                process.terminate()
            
            for name, process in processes:
                process.wait()
                print(f"{name} stopped.")
    
    elif args.command == 'status':
        print("HashWrap Worker Status")
        print("=" * 50)
        
        # Check environment
        checks = manager.validate_environment()
        print("\nEnvironment Checks:")
        for check, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"  {status} {check.title()}")
        
        # Try to get worker stats
        try:
            from worker.celery_app import celery
            
            inspect = celery.control.inspect()
            
            print("\nActive Workers:")
            stats = inspect.stats()
            if stats:
                for worker, worker_stats in stats.items():
                    print(f"  • {worker}")
                    print(f"    Pool: {worker_stats.get('pool', {}).get('max-concurrency', 'unknown')} processes")
                    print(f"    Broker: {worker_stats.get('broker', {}).get('transport', 'unknown')}")
            else:
                print("  No active workers found")
            
            print("\nActive Tasks:")
            active = inspect.active()
            if active:
                total_tasks = sum(len(tasks) for tasks in active.values())
                print(f"  {total_tasks} tasks currently running")
                
                for worker, tasks in active.items():
                    if tasks:
                        print(f"  {worker}: {len(tasks)} tasks")
            else:
                print("  No active tasks")
                
        except Exception as e:
            print(f"  Could not connect to workers: {e}")
    
    elif args.command == 'recommend':
        recommendations = manager.get_worker_recommendations()
        
        print("HashWrap Worker Deployment Recommendations")
        print("=" * 50)
        
        total_instances = 0
        for queue, rec in recommendations.items():
            print(f"\n{queue.upper()} Queue:")
            print(f"  Recommended instances: {rec['instances']}")
            print(f"  Reason: {rec['reason']}")
            
            queue_info = manager.config.get_queue_info()[queue]
            print(f"  Concurrency per instance: {queue_info['concurrency']}")
            print(f"  Prefetch: {queue_info['prefetch']}")
            
            total_instances += rec['instances']
        
        print(f"\nTotal recommended instances: {total_instances}")
        
        print("\nStartup commands:")
        for queue, rec in recommendations.items():
            if rec['instances'] == 1:
                print(f"  python worker_startup.py worker {queue}")
            else:
                for i in range(rec['instances']):
                    hostname = f"{queue}-{i+1}"
                    print(f"  python worker_startup.py worker {queue} --hostname {hostname}")
        
        print("\nOr use: python worker_startup.py multi --recommended")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()