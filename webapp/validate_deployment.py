#!/usr/bin/env python3
"""
HashWrap Pre-Deployment Validation
Quick system check before going live
"""

import os
import sys
import subprocess
import sqlite3
from pathlib import Path

def check_mark(condition, message):
    """Print check result with visual indicator"""
    icon = "✅" if condition else "❌"
    print(f"{icon} {message}")
    return condition

def validate_files():
    """Check all required files exist"""
    print("📁 FILE STRUCTURE CHECK")
    
    required_files = [
        'app_fixed.py',
        'hashcat_worker.py', 
        'templates/base.html',
        'templates/dashboard.html',
        'templates/login.html',
        'templates/upload.html',
        'templates/job_detail.html'
    ]
    
    all_good = True
    for file_path in required_files:
        exists = os.path.exists(file_path)
        check_mark(exists, f"Required file: {file_path}")
        all_good = all_good and exists
    
    return all_good

def validate_dependencies():
    """Check Python dependencies"""
    print("\n🐍 PYTHON DEPENDENCIES CHECK")
    
    required_modules = [
        'flask', 'werkzeug', 'sqlite3', 'psutil', 
        'hashlib', 'threading', 'subprocess'
    ]
    
    all_good = True
    for module in required_modules:
        try:
            __import__(module)
            check_mark(True, f"Module: {module}")
        except ImportError:
            check_mark(False, f"Module: {module} - NOT FOUND")
            all_good = False
    
    return all_good

def validate_directories():
    """Check directory structure"""
    print("\n📂 DIRECTORY STRUCTURE CHECK")
    
    required_dirs = [
        'data/uploads',
        'data/results', 
        'wordlists',
        'logs'
    ]
    
    all_good = True
    for directory in required_dirs:
        dir_path = Path(directory)
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                check_mark(True, f"Created directory: {directory}")
            except Exception as e:
                check_mark(False, f"Cannot create directory {directory}: {e}")
                all_good = False
        else:
            check_mark(True, f"Directory exists: {directory}")
    
    return all_good

def validate_database():
    """Check database initialization"""
    print("\n🗄️ DATABASE CHECK")
    
    try:
        conn = sqlite3.connect('hashwrap.db', timeout=5.0)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        required_tables = {'jobs', 'results', 'users', 'system_status'}
        all_good = True
        
        for table in required_tables:
            exists = table in tables
            check_mark(exists, f"Table: {table}")
            all_good = all_good and exists
        
        # Check admin user
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        admin_exists = cursor.fetchone()[0] > 0
        check_mark(admin_exists, "Admin user exists")
        all_good = all_good and admin_exists
        
        conn.close()
        return all_good
        
    except Exception as e:
        check_mark(False, f"Database connection failed: {e}")
        return False

def validate_system_tools():
    """Check system tools availability"""
    print("\n🔧 SYSTEM TOOLS CHECK")
    
    # Check hashcat
    try:
        result = subprocess.run(['hashcat', '--version'], 
                              capture_output=True, text=True, timeout=5)
        hashcat_ok = result.returncode == 0
        check_mark(hashcat_ok, "Hashcat binary accessible")
    except FileNotFoundError:
        check_mark(False, "Hashcat binary - NOT FOUND")
        hashcat_ok = False
    except Exception as e:
        check_mark(False, f"Hashcat check failed: {e}")
        hashcat_ok = False
    
    # Check GPU (optional)
    try:
        result = subprocess.run(['nvidia-smi'], 
                              capture_output=True, text=True, timeout=3)
        gpu_ok = result.returncode == 0
        check_mark(gpu_ok, "NVIDIA GPU available (optional)")
    except FileNotFoundError:
        check_mark(True, "GPU check skipped (nvidia-smi not found)")
        gpu_ok = True  # GPU is optional
    
    return hashcat_ok  # GPU is optional, only hashcat is required

def validate_permissions():
    """Check file permissions"""
    print("\n🔐 PERMISSIONS CHECK")
    
    # Check write permissions
    test_dirs = ['data/uploads', 'data/results', 'logs']
    all_good = True
    
    for test_dir in test_dirs:
        try:
            test_file = Path(test_dir) / 'permission_test.tmp'
            test_file.write_text('test')
            test_file.unlink()
            check_mark(True, f"Write access: {test_dir}")
        except Exception as e:
            check_mark(False, f"Write access failed for {test_dir}: {e}")
            all_good = False
    
    return all_good

def main():
    """Main validation routine"""
    print("🚀 HashWrap Pre-Deployment Validation")
    print("=" * 50)
    
    checks = [
        ("Files", validate_files),
        ("Dependencies", validate_dependencies), 
        ("Directories", validate_directories),
        ("Database", validate_database),
        ("System Tools", validate_system_tools),
        ("Permissions", validate_permissions)
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} check crashed: {e}")
            results.append((check_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 VALIDATION SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        icon = "✅" if result else "❌"
        print(f"{icon} {check_name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL CHECKS PASSED - Ready for deployment!")
        return True
    else:
        print("⚠️ Some checks failed - Review issues before deployment")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)