#!/usr/bin/env python3
"""
HashWrap - Simple Web Interface for Penetration Testing
Simplified Flask app focused on essential pentest workflow
"""

import os
import sqlite3
import hashlib
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import subprocess
import json
import glob

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuration
UPLOAD_FOLDER = 'data/uploads'
RESULTS_FOLDER = 'data/results'
DATABASE = 'hashwrap.db'
ALLOWED_EXTENSIONS = {'txt', 'hash', 'lst'}

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

def init_db():
    """Initialize simple SQLite database"""
    conn = sqlite3.connect(DATABASE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            hash_type TEXT,
            status TEXT DEFAULT 'queued',
            total_hashes INTEGER DEFAULT 0,
            cracked_count INTEGER DEFAULT 0,
            started_at DATETIME,
            completed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create default admin user if none exists
    cursor = conn.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        admin_hash = generate_password_hash('admin')
        conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                    ('admin', admin_hash))
        print("Created default admin user (username: admin, password: admin)")
    
    conn.commit()
    conn.close()

def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def detect_hash_type(file_path):
    """Simple hash type detection based on hash length and format"""
    with open(file_path, 'r') as f:
        first_line = f.readline().strip()
    
    if not first_line:
        return "unknown"
    
    # Basic hash type detection by length
    hash_length = len(first_line)
    
    if hash_length == 32:
        return "MD5"
    elif hash_length == 40:
        return "SHA1"  
    elif hash_length == 64:
        return "SHA256"
    elif ':' in first_line and len(first_line.split(':')) >= 6:
        return "NTLM"
    elif '$' in first_line:
        if '$1$' in first_line:
            return "MD5crypt"
        elif '$2' in first_line:
            return "bcrypt"
        elif '$6$' in first_line:
            return "SHA512crypt"
    
    return "unknown"

def count_hashes(file_path):
    """Count number of hashes in file"""
    try:
        with open(file_path, 'r') as f:
            return sum(1 for line in f if line.strip())
    except:
        return 0

@app.route('/')
def index():
    """Dashboard showing job queue and status"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    
    # Get recent jobs
    jobs = conn.execute('''
        SELECT * FROM jobs 
        ORDER BY created_at DESC 
        LIMIT 10
    ''').fetchall()
    
    # Get summary stats
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_jobs,
            SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_jobs,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_jobs,
            SUM(cracked_count) as total_cracked
        FROM jobs
    ''').fetchone()
    
    conn.close()
    
    return render_template('dashboard.html', jobs=jobs, stats=stats)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Handle file upload and job creation"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            
            # Detect hash type and count
            hash_type = detect_hash_type(file_path)
            total_hashes = count_hashes(file_path)
            
            # Create job record
            conn = sqlite3.connect(DATABASE)
            conn.execute('''
                INSERT INTO jobs (filename, hash_type, total_hashes, status)
                VALUES (?, ?, ?, 'queued')
            ''', (filename, hash_type, total_hashes))
            conn.commit()
            conn.close()
            
            flash(f'File uploaded successfully! Detected: {hash_type} ({total_hashes} hashes)')
            return redirect(url_for('index'))
        else:
            flash('Invalid file type. Use .txt, .hash, or .lst files')
    
    return render_template('upload.html')

@app.route('/jobs/<int:job_id>')
def job_detail(job_id):
    """Show job details and results"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    
    job = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    if not job:
        flash('Job not found')
        return redirect(url_for('index'))
    
    # Get results for this job
    results = conn.execute('''
        SELECT * FROM results 
        WHERE job_id = ? 
        ORDER BY cracked_at DESC
    ''', (job_id,)).fetchall()
    
    conn.close()
    
    return render_template('job_detail.html', job=job, results=results)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Simple login system"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DATABASE)
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/jobs/<int:job_id>/status')
def job_status_api(job_id):
    """API endpoint for real-time job status"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    job = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    conn.close()
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({
        'id': job['id'],
        'status': job['status'],
        'progress': round((job['cracked_count'] / max(job['total_hashes'], 1)) * 100, 1) if job['total_hashes'] else 0,
        'cracked_count': job['cracked_count'],
        'total_hashes': job['total_hashes']
    })

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)