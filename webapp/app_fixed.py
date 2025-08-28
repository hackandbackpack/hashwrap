#!/usr/bin/env python3
"""
HashWrap - FIXED Web Interface for Penetration Testing
Production-ready Flask app with comprehensive error handling and verbosity
"""

import os
import sqlite3
import hashlib
import threading
import time
import logging
import traceback
from datetime import datetime, timedelta
from contextlib import contextmanager
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge
import subprocess
import json
import glob
import psutil
import signal

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('hashwrap.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('HashWrap')

app = Flask(__name__)

# FIXED: Use consistent secret key (store in file for persistence)
SECRET_KEY_FILE = 'secret.key'
if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, 'rb') as f:
        app.secret_key = f.read()
        logger.info("✅ CHECKPOINT: Loaded existing secret key")
else:
    app.secret_key = os.urandom(24)
    with open(SECRET_KEY_FILE, 'wb') as f:
        f.write(app.secret_key)
    logger.info("✅ CHECKPOINT: Generated new secret key")

# Configuration with security limits
class Config:
    UPLOAD_FOLDER = 'data/uploads'
    RESULTS_FOLDER = 'data/results'
    DATABASE = 'hashwrap.db'
    ALLOWED_EXTENSIONS = {'txt', 'hash', 'lst', 'json'}
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit
    MAX_LINES_PER_FILE = 1_000_000  # 1M lines limit
    MAX_CONCURRENT_JOBS = 3
    DATABASE_TIMEOUT = 30.0
    SESSION_TIMEOUT = timedelta(hours=8)

config = Config()
app.config['MAX_CONTENT_LENGTH'] = config.MAX_FILE_SIZE

# Database connection lock for thread safety
db_lock = threading.RLock()

def log_checkpoint(message, level="INFO"):
    """Log checkpoint with consistent format"""
    checkpoint_msg = f"🔍 CHECKPOINT: {message}"
    if level == "ERROR":
        logger.error(checkpoint_msg)
    elif level == "WARNING":
        logger.warning(checkpoint_msg)
    else:
        logger.info(checkpoint_msg)
    return checkpoint_msg

@contextmanager
def get_db_connection():
    """Thread-safe database connection with proper error handling"""
    conn = None
    try:
        with db_lock:
            log_checkpoint("Acquiring database connection")
            conn = sqlite3.connect(
                config.DATABASE, 
                timeout=config.DATABASE_TIMEOUT,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            yield conn
    except sqlite3.OperationalError as e:
        log_checkpoint(f"Database connection failed: {e}", "ERROR")
        raise Exception(f"Database unavailable: {e}")
    except Exception as e:
        log_checkpoint(f"Unexpected database error: {e}", "ERROR")
        raise
    finally:
        if conn:
            conn.close()
            log_checkpoint("Database connection closed")

def init_directories():
    """Initialize required directories with proper permissions"""
    directories = [
        config.UPLOAD_FOLDER,
        config.RESULTS_FOLDER,
        'wordlists',
        'logs'
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, mode=0o755, exist_ok=True)
            log_checkpoint(f"Directory ready: {directory}")
        except PermissionError as e:
            log_checkpoint(f"Permission error creating {directory}: {e}", "ERROR")
            raise
        except Exception as e:
            log_checkpoint(f"Failed to create {directory}: {e}", "ERROR")
            raise

def validate_system_requirements():
    """Validate system has required components"""
    requirements_met = True
    
    # Check hashcat binary
    try:
        result = subprocess.run(['hashcat', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            log_checkpoint(f"Hashcat available: {version}")
        else:
            log_checkpoint("Hashcat binary not responding", "WARNING")
            requirements_met = False
    except FileNotFoundError:
        log_checkpoint("Hashcat binary not found in PATH", "ERROR")
        requirements_met = False
    except subprocess.TimeoutExpired:
        log_checkpoint("Hashcat version check timed out", "WARNING")
        requirements_met = False
    
    # Check disk space
    try:
        disk_usage = psutil.disk_usage('.')
        free_gb = disk_usage.free / (1024**3)
        log_checkpoint(f"Available disk space: {free_gb:.1f} GB")
        if free_gb < 1.0:
            log_checkpoint("Low disk space warning", "WARNING")
    except Exception as e:
        log_checkpoint(f"Disk space check failed: {e}", "WARNING")
    
    # Check GPU availability (optional)
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            gpus = result.stdout.strip().split('\n')
            log_checkpoint(f"GPUs detected: {len(gpus)} ({gpus[0] if gpus else 'none'})")
        else:
            log_checkpoint("No NVIDIA GPUs detected (CPU-only mode)")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        log_checkpoint("GPU detection skipped (nvidia-smi not available)")
    
    return requirements_met

def init_db():
    """Initialize database with comprehensive error handling"""
    log_checkpoint("Initializing database schema")
    
    try:
        with get_db_connection() as conn:
            # Jobs table with additional fields for monitoring
            conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_hash TEXT,
                    hash_type TEXT,
                    status TEXT DEFAULT 'queued',
                    total_hashes INTEGER DEFAULT 0,
                    cracked_count INTEGER DEFAULT 0,
                    progress_percent REAL DEFAULT 0.0,
                    current_speed TEXT,
                    estimated_time TEXT,
                    error_message TEXT,
                    started_at DATETIME,
                    completed_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Results table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER,
                    hash_value TEXT,
                    password TEXT,
                    cracked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs (id)
                )
            ''')
            
            # Users table with session management
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    last_login DATETIME,
                    login_attempts INTEGER DEFAULT 0,
                    locked_until DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # System status table for monitoring
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_value TEXT,
                    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Check if admin user exists
            cursor = conn.execute('SELECT COUNT(*) FROM users')
            user_count = cursor.fetchone()[0]
            
            if user_count == 0:
                admin_hash = generate_password_hash('admin')
                conn.execute(
                    'INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                    ('admin', admin_hash)
                )
                conn.commit()
                log_checkpoint("Created default admin user (admin/admin)")
            else:
                log_checkpoint(f"Database has {user_count} existing users")
            
            log_checkpoint("Database initialization completed successfully")
            
    except Exception as e:
        log_checkpoint(f"Database initialization failed: {e}", "ERROR")
        raise

def allowed_file(filename):
    """Validate file extension with additional security checks"""
    if not filename or '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    
    # Check allowed extensions
    if extension not in config.ALLOWED_EXTENSIONS:
        log_checkpoint(f"Rejected file extension: {extension}", "WARNING")
        return False
    
    # Additional security: check for suspicious patterns
    suspicious_patterns = ['..', '/', '\\', '\0', '<', '>', '|', '&', ';']
    if any(pattern in filename for pattern in suspicious_patterns):
        log_checkpoint(f"Rejected suspicious filename: {filename}", "WARNING")
        return False
    
    return True

def secure_file_upload(file):
    """Securely handle file upload with comprehensive validation"""
    if not file or not file.filename:
        raise ValueError("No file provided")
    
    if not allowed_file(file.filename):
        raise ValueError(f"File type not allowed: {file.filename}")
    
    # Generate secure filename
    filename = secure_filename(file.filename)
    if not filename:
        raise ValueError("Invalid filename after security filtering")
    
    # Add timestamp to prevent conflicts
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(filename)
    secure_filename_final = f"{timestamp}_{name}{ext}"
    
    file_path = os.path.join(config.UPLOAD_FOLDER, secure_filename_final)
    
    # Check file doesn't already exist
    if os.path.exists(file_path):
        raise ValueError("File already exists")
    
    # Save file
    file.save(file_path)
    
    # Validate file size after save
    file_size = os.path.getsize(file_path)
    if file_size > config.MAX_FILE_SIZE:
        os.remove(file_path)
        raise ValueError(f"File too large: {file_size} bytes")
    
    log_checkpoint(f"File uploaded successfully: {secure_filename_final} ({file_size} bytes)")
    return secure_filename_final, file_path

def detect_hash_type(file_path):
    """Enhanced hash type detection with error handling"""
    try:
        log_checkpoint(f"Analyzing hash types in: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Read first few lines for analysis
            sample_lines = []
            line_count = 0
            
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty and comment lines
                    sample_lines.append(line)
                    line_count += 1
                    
                    if len(sample_lines) >= 5:  # Analyze first 5 valid lines
                        break
                
                # Safety check for extremely large files
                if line_count > config.MAX_LINES_PER_FILE:
                    raise ValueError(f"File too large: {line_count} lines exceeds limit")
        
        if not sample_lines:
            log_checkpoint("No valid hash lines found in file", "WARNING")
            return "empty", 0
        
        # Analyze first line for hash type
        first_line = sample_lines[0]
        hash_type = _analyze_hash_format(first_line)
        
        log_checkpoint(f"Detected hash type: {hash_type} from {len(sample_lines)} samples")
        return hash_type, line_count
        
    except Exception as e:
        log_checkpoint(f"Hash detection failed: {e}", "ERROR")
        return "unknown", 0

def _analyze_hash_format(hash_line):
    """Analyze individual hash line format"""
    if not hash_line:
        return "unknown"
    
    # NTLM dump format (username:RID:LMhash:NThash:::)
    if ':' in hash_line and len(hash_line.split(':')) >= 6:
        parts = hash_line.split(':')
        if len(parts[3]) == 32:  # NT hash length
            return "NTLM"
    
    # Hash:salt format
    if ':' in hash_line:
        hash_part = hash_line.split(':')[0]
        hash_length = len(hash_part)
    else:
        hash_length = len(hash_line)
    
    # Detect by length and characters
    if all(c in '0123456789abcdefABCDEF' for c in hash_line.replace(':', '')):
        if hash_length == 32:
            return "MD5"
        elif hash_length == 40:
            return "SHA1"
        elif hash_length == 64:
            return "SHA256"
        elif hash_length == 128:
            return "SHA512"
    
    # Detect hashed formats
    if hash_line.startswith('$'):
        if '$1$' in hash_line:
            return "MD5crypt"
        elif '$2a$' in hash_line or '$2b$' in hash_line or '$2y$' in hash_line:
            return "bcrypt"
        elif '$5$' in hash_line:
            return "SHA256crypt"
        elif '$6$' in hash_line:
            return "SHA512crypt"
    
    return "unknown"

@app.before_request
def before_request():
    """Pre-request security and session checks"""
    # Skip security checks for static files and login
    if request.endpoint in ['static', 'login']:
        return
    
    # Check session timeout
    if 'user_id' in session:
        last_activity = session.get('last_activity')
        if last_activity:
            last_activity = datetime.fromisoformat(last_activity)
            if datetime.now() - last_activity > config.SESSION_TIMEOUT:
                session.clear()
                log_checkpoint("Session expired due to inactivity", "WARNING")
                flash("Session expired. Please login again.")
                return redirect(url_for('login'))
        
        # Update last activity
        session['last_activity'] = datetime.now().isoformat()

@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def file_too_large(e):
    """Handle file too large error"""
    log_checkpoint(f"File upload rejected: too large", "WARNING")
    flash(f"File too large. Maximum size: {config.MAX_FILE_SIZE // 1024 // 1024}MB")
    return redirect(url_for('upload_file'))

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler"""
    error_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_checkpoint(f"Unhandled exception [{error_id}]: {str(e)}", "ERROR")
    logger.error(f"Exception [{error_id}] traceback:", exc_info=True)
    
    if request.is_json:
        return jsonify({'error': f'Internal error [{error_id}]'}), 500
    else:
        flash(f'An error occurred [{error_id}]. Check logs for details.')
        return redirect(url_for('index'))

# Routes with comprehensive logging and error handling

@app.route('/')
def index():
    """Dashboard with enhanced monitoring"""
    try:
        log_checkpoint("Loading dashboard")
        
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        with get_db_connection() as conn:
            # Get recent jobs with enhanced status info
            jobs = conn.execute('''
                SELECT *, 
                       CASE 
                           WHEN status = 'running' AND updated_at < datetime('now', '-5 minutes') 
                           THEN 'stalled' 
                           ELSE status 
                       END as display_status
                FROM jobs 
                ORDER BY created_at DESC 
                LIMIT 20
            ''').fetchall()
            
            # Get comprehensive stats
            stats = conn.execute('''
                SELECT 
                    COUNT(*) as total_jobs,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_jobs,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_jobs,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_jobs,
                    SUM(COALESCE(cracked_count, 0)) as total_cracked,
                    SUM(COALESCE(total_hashes, 0)) as total_hashes_processed
                FROM jobs
            ''').fetchone()
            
            # System health check
            running_jobs = stats['running_jobs'] or 0
            system_health = {
                'status': 'healthy' if running_jobs < config.MAX_CONCURRENT_JOBS else 'overloaded',
                'running_jobs': running_jobs,
                'max_jobs': config.MAX_CONCURRENT_JOBS
            }
        
        log_checkpoint(f"Dashboard loaded: {stats['total_jobs']} total jobs, {running_jobs} running")
        return render_template('dashboard.html', jobs=jobs, stats=stats, system_health=system_health)
        
    except Exception as e:
        log_checkpoint(f"Dashboard error: {e}", "ERROR")
        flash("Error loading dashboard. Check system status.")
        return render_template('dashboard.html', jobs=[], stats={}, system_health={'status': 'error'})

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Enhanced file upload with comprehensive validation"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            log_checkpoint("Processing file upload")
            
            if 'file' not in request.files:
                raise ValueError("No file in request")
            
            file = request.files['file']
            if file.filename == '':
                raise ValueError("No file selected")
            
            # Secure file upload
            secure_filename_final, file_path = secure_file_upload(file)
            
            # Calculate file hash for deduplication
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Check for duplicate files
            with get_db_connection() as conn:
                existing = conn.execute(
                    'SELECT id, filename FROM jobs WHERE file_hash = ?', 
                    (file_hash,)
                ).fetchone()
                
                if existing:
                    os.remove(file_path)  # Remove duplicate
                    log_checkpoint(f"Duplicate file rejected: matches job {existing['id']}")
                    flash(f'Duplicate file detected. Matches existing job: {existing["filename"]}')
                    return redirect(request.url)
            
            # Detect hash type and validate content
            hash_type, line_count = detect_hash_type(file_path)
            
            if hash_type == "empty":
                os.remove(file_path)
                raise ValueError("File contains no valid hashes")
            
            if line_count == 0:
                os.remove(file_path)
                raise ValueError("Unable to count hashes in file")
            
            # Create job record
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    INSERT INTO jobs (filename, file_hash, hash_type, total_hashes, status)
                    VALUES (?, ?, ?, ?, 'queued')
                ''', (secure_filename_final, file_hash, hash_type, line_count))
                job_id = cursor.lastrowid
                conn.commit()
            
            log_checkpoint(f"Job created: ID={job_id}, type={hash_type}, hashes={line_count}")
            flash(f'File uploaded successfully! Job #{job_id} created: {hash_type} ({line_count:,} hashes)')
            return redirect(url_for('job_detail', job_id=job_id))
            
        except ValueError as e:
            log_checkpoint(f"Upload validation error: {e}", "WARNING")
            flash(str(e))
        except Exception as e:
            log_checkpoint(f"Upload processing error: {e}", "ERROR")
            flash('Upload failed. Please try again or contact administrator.')
    
    return render_template('upload.html')

@app.route('/jobs/<int:job_id>')
def job_detail(job_id):
    """Enhanced job detail page with real-time monitoring"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        log_checkpoint(f"Loading job detail: {job_id}")
        
        with get_db_connection() as conn:
            job = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
            if not job:
                log_checkpoint(f"Job {job_id} not found", "WARNING")
                flash('Job not found')
                return redirect(url_for('index'))
            
            # Get results with pagination (first 100)
            results = conn.execute('''
                SELECT * FROM results 
                WHERE job_id = ? 
                ORDER BY cracked_at DESC
                LIMIT 100
            ''', (job_id,)).fetchall()
            
            # Get total result count
            result_count = conn.execute(
                'SELECT COUNT(*) FROM results WHERE job_id = ?', 
                (job_id,)
            ).fetchone()[0]
        
        log_checkpoint(f"Job {job_id} detail loaded: {result_count} results found")
        return render_template('job_detail.html', job=job, results=results, result_count=result_count)
        
    except Exception as e:
        log_checkpoint(f"Job detail error: {e}", "ERROR")
        flash('Error loading job details')
        return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Secure login with rate limiting"""
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            if not username or not password:
                raise ValueError("Username and password required")
            
            log_checkpoint(f"Login attempt for user: {username}")
            
            with get_db_connection() as conn:
                user = conn.execute(
                    'SELECT * FROM users WHERE username = ?', 
                    (username,)
                ).fetchone()
                
                if not user:
                    log_checkpoint(f"Login failed: user {username} not found", "WARNING")
                    flash('Invalid username or password')
                    return render_template('login.html')
                
                # Check if account is locked
                if user['locked_until'] and datetime.fromisoformat(user['locked_until']) > datetime.now():
                    log_checkpoint(f"Login failed: user {username} account locked", "WARNING")
                    flash('Account temporarily locked. Try again later.')
                    return render_template('login.html')
                
                # Verify password
                if check_password_hash(user['password_hash'], password):
                    # Successful login
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['last_activity'] = datetime.now().isoformat()
                    
                    # Update login info and reset attempts
                    conn.execute('''
                        UPDATE users 
                        SET last_login = CURRENT_TIMESTAMP, 
                            login_attempts = 0, 
                            locked_until = NULL
                        WHERE id = ?
                    ''', (user['id'],))
                    conn.commit()
                    
                    log_checkpoint(f"Successful login for user: {username}")
                    return redirect(url_for('index'))
                else:
                    # Failed login
                    attempts = user['login_attempts'] + 1
                    locked_until = None
                    
                    # Lock account after 5 failed attempts
                    if attempts >= 5:
                        locked_until = (datetime.now() + timedelta(minutes=15)).isoformat()
                        log_checkpoint(f"Account locked for user {username} after {attempts} attempts", "WARNING")
                    
                    conn.execute('''
                        UPDATE users 
                        SET login_attempts = ?, locked_until = ?
                        WHERE id = ?
                    ''', (attempts, locked_until, user['id']))
                    conn.commit()
                    
                    log_checkpoint(f"Login failed for user {username}: attempt {attempts}", "WARNING")
                    flash('Invalid username or password')
                    
        except Exception as e:
            log_checkpoint(f"Login error: {e}", "ERROR")
            flash('Login error. Please try again.')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Secure logout"""
    username = session.get('username', 'unknown')
    session.clear()
    log_checkpoint(f"User logged out: {username}")
    flash('Logged out successfully')
    return redirect(url_for('login'))

@app.route('/api/jobs/<int:job_id>/status')
def job_status_api(job_id):
    """Enhanced API endpoint for real-time job status"""
    try:
        with get_db_connection() as conn:
            job = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
            if not job:
                return jsonify({'error': 'Job not found'}), 404
            
            # Calculate additional metrics
            progress = 0.0
            if job['total_hashes'] and job['total_hashes'] > 0:
                progress = round((job['cracked_count'] or 0) / job['total_hashes'] * 100, 2)
            
            status_info = {
                'id': job['id'],
                'status': job['status'],
                'progress': progress,
                'cracked_count': job['cracked_count'] or 0,
                'total_hashes': job['total_hashes'] or 0,
                'current_speed': job['current_speed'],
                'estimated_time': job['estimated_time'],
                'error_message': job['error_message'],
                'last_updated': job['updated_at']
            }
            
            return jsonify(status_info)
            
    except Exception as e:
        log_checkpoint(f"Status API error for job {job_id}: {e}", "ERROR")
        return jsonify({'error': 'Status unavailable'}), 500

@app.route('/api/system/status')
def system_status_api():
    """System health API endpoint"""
    try:
        # Check system resources
        disk_usage = psutil.disk_usage('.')
        memory_info = psutil.virtual_memory()
        
        with get_db_connection() as conn:
            job_counts = conn.execute('''
                SELECT status, COUNT(*) as count 
                FROM jobs 
                GROUP BY status
            ''').fetchall()
        
        status = {
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'disk_free_gb': round(disk_usage.free / (1024**3), 2),
            'memory_percent': memory_info.percent,
            'job_counts': {row['status']: row['count'] for row in job_counts}
        }
        
        return jsonify(status)
        
    except Exception as e:
        log_checkpoint(f"System status API error: {e}", "ERROR")
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'database': 'error',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    try:
        log_checkpoint("=== HashWrap Web Application Starting ===")
        
        # Initialize system
        init_directories()
        system_ready = validate_system_requirements()
        init_db()
        
        if not system_ready:
            log_checkpoint("System requirements not fully met - some features may not work", "WARNING")
        
        log_checkpoint("=== HashWrap Ready - Starting Flask Server ===")
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        log_checkpoint("=== HashWrap Shutdown Requested ===")
    except Exception as e:
        log_checkpoint(f"=== HashWrap Startup Failed: {e} ===", "ERROR")
        raise