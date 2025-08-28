"""
File utilities for worker tasks.
Provides file validation, processing, and security checks.
"""

import hashlib
import mimetypes
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Tuple
import magic

from worker.utils.logging import get_task_logger
from core.security import SecurityValidator


logger = get_task_logger(__name__)


class FileValidator:
    """File validation utilities with security checks."""
    
    def __init__(self):
        self.security_validator = SecurityValidator()
        
        # Supported hash file extensions
        self.hash_extensions = {'.txt', '.hash', '.hashes', '.lst', '.list'}
        
        # Maximum file size (100MB)
        self.max_file_size = 100 * 1024 * 1024
        
        # Maximum lines in a hash file
        self.max_lines = 10_000_000
    
    def validate_hash_file(self, file_path: str) -> Dict[str, any]:
        """
        Validate a hash file for processing.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            file_path_obj = Path(file_path)
            
            # Basic existence check
            if not file_path_obj.exists():
                return {'valid': False, 'error': 'File does not exist'}
            
            if not file_path_obj.is_file():
                return {'valid': False, 'error': 'Path is not a file'}
            
            # Security validation
            try:
                safe_path = self.security_validator.validate_file_path(file_path, must_exist=True)
            except Exception as e:
                return {'valid': False, 'error': f'Security validation failed: {e}'}
            
            # File size check
            file_size = file_path_obj.stat().st_size
            if file_size == 0:
                return {'valid': False, 'error': 'File is empty'}
            
            if file_size > self.max_file_size:
                return {'valid': False, 'error': f'File too large: {file_size} bytes (max: {self.max_file_size})'}
            
            # Extension check
            if file_path_obj.suffix.lower() not in self.hash_extensions:
                logger.warning(f"Unusual file extension: {file_path_obj.suffix}")
            
            # Content validation
            content_check = self._validate_file_content(file_path_obj)
            if not content_check['valid']:
                return content_check
            
            # MIME type check
            mime_type = self._get_mime_type(file_path_obj)
            
            return {
                'valid': True,
                'file_size': file_size,
                'line_count': content_check['line_count'],
                'hash_count': content_check['hash_count'],
                'mime_type': mime_type,
                'file_hash': self._calculate_file_hash(file_path_obj)
            }
            
        except Exception as e:
            logger.error(f"Error validating file {file_path}: {e}", exc_info=True)
            return {'valid': False, 'error': str(e)}
    
    def _validate_file_content(self, file_path: Path) -> Dict[str, any]:
        """Validate file content structure."""
        try:
            line_count = 0
            hash_count = 0
            sample_lines = []
            
            # Read file and analyze content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line_count += 1
                    
                    # Limit line count
                    if line_count > self.max_lines:
                        return {'valid': False, 'error': f'Too many lines: {line_count} (max: {self.max_lines})'}
                    
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Count potential hashes
                    if self._looks_like_hash(line):
                        hash_count += 1
                    
                    # Collect sample lines for analysis
                    if len(sample_lines) < 10:
                        sample_lines.append(line)
            
            # Check if file contains reasonable hash content
            if hash_count == 0:
                return {'valid': False, 'error': 'No hash-like content found'}
            
            hash_ratio = hash_count / line_count if line_count > 0 else 0
            if hash_ratio < 0.1:  # At least 10% of lines should look like hashes
                logger.warning(f"Low hash ratio in file: {hash_ratio:.2%}")
            
            return {
                'valid': True,
                'line_count': line_count,
                'hash_count': hash_count,
                'hash_ratio': hash_ratio,
                'sample_lines': sample_lines
            }
            
        except UnicodeDecodeError:
            return {'valid': False, 'error': 'File contains invalid UTF-8 characters'}
        except Exception as e:
            return {'valid': False, 'error': f'Content validation error: {e}'}
    
    def _looks_like_hash(self, line: str) -> bool:
        """Check if a line looks like a hash."""
        # Remove whitespace
        line = line.strip()
        
        # Check for common hash patterns
        patterns = [
            r'^[a-f0-9]{32}$',  # MD5
            r'^[a-f0-9]{40}$',  # SHA1
            r'^[a-f0-9]{64}$',  # SHA256
            r'^[a-f0-9]{128}$', # SHA512
            r'^[a-f0-9]{32}:[a-f0-9]+$',  # MD5 with salt
            r'^[a-f0-9]{40}:[a-f0-9]+$',  # SHA1 with salt
            r'^\$\w+\$',        # Structured hashes ($1$, $2$, etc.)
            r'^\*[A-F0-9]{40}$', # MySQL
            r'^[a-zA-Z0-9+/]+=*$', # Base64-like (could be various formats)
        ]
        
        for pattern in patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        
        # Additional heuristics
        # Check for colon-separated format (hash:salt or hash:plaintext)
        if ':' in line:
            parts = line.split(':', 1)
            if len(parts[0]) >= 16 and all(c in '0123456789abcdefABCDEF' for c in parts[0]):
                return True
        
        # Check for reasonable length and hex characters
        if 16 <= len(line) <= 256 and all(c in '0123456789abcdefABCDEF:$+-_=/' for c in line):
            return True
        
        return False
    
    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type of file."""
        try:
            # Try python-magic first (more accurate)
            return magic.from_file(str(file_path), mime=True)
        except:
            # Fallback to mimetypes
            mime_type, _ = mimetypes.guess_type(str(file_path))
            return mime_type or 'application/octet-stream'
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()


class FileProcessor:
    """File processing utilities for hash files."""
    
    def __init__(self):
        self.chunk_size = 4096
    
    def read_hashes_streaming(self, file_path: str, chunk_lines: int = 1000) -> Iterator[List[str]]:
        """
        Read hashes from file in streaming chunks.
        
        Args:
            file_path: Path to hash file
            chunk_lines: Number of lines to read per chunk
            
        Yields:
            Lists of hash strings
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                chunk = []
                
                for line in f:
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    chunk.append(line)
                    
                    if len(chunk) >= chunk_lines:
                        yield chunk
                        chunk = []
                
                # Yield remaining hashes
                if chunk:
                    yield chunk
                    
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise
    
    def split_hash_file_by_type(self, file_path: str, output_dir: str) -> Dict[str, str]:
        """
        Split a hash file into separate files by hash type.
        
        Args:
            file_path: Input hash file path
            output_dir: Directory to write split files
            
        Returns:
            Dictionary mapping hash types to output file paths
        """
        from worker.services.hash_detection_service import HashDetectionService
        
        output_files = {}
        file_handles = {}
        detection_service = HashDetectionService()
        
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            base_name = Path(file_path).stem
            
            # Process file line by line
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    if not line or line.startswith('#'):
                        continue
                    
                    # Detect hash type
                    detection_result = detection_service.detect_single_hash(line)
                    
                    if detection_result['success']:
                        hash_type = detection_result['hash_type']
                        
                        # Create file handle if needed
                        if hash_type not in file_handles:
                            output_file = output_path / f"{base_name}_{hash_type.lower().replace(' ', '_')}.txt"
                            file_handles[hash_type] = open(output_file, 'w')
                            output_files[hash_type] = str(output_file)
                        
                        # Write hash to appropriate file
                        file_handles[hash_type].write(line + '\n')
                    else:
                        # Unknown hash type - write to unknown file
                        if 'unknown' not in file_handles:
                            unknown_file = output_path / f"{base_name}_unknown.txt"
                            file_handles['unknown'] = open(unknown_file, 'w')
                            output_files['unknown'] = str(unknown_file)
                        
                        file_handles['unknown'].write(line + '\n')
            
            return output_files
            
        except Exception as e:
            logger.error(f"Error splitting hash file {file_path}: {e}")
            raise
        
        finally:
            # Close all file handles
            for handle in file_handles.values():
                try:
                    handle.close()
                except:
                    pass
    
    def count_lines(self, file_path: str) -> int:
        """Count lines in file efficiently."""
        try:
            with open(file_path, 'rb') as f:
                count = 0
                buffer = f.read(1024 * 1024)  # Read 1MB at a time
                
                while buffer:
                    count += buffer.count(b'\n')
                    buffer = f.read(1024 * 1024)
                
                return count
                
        except Exception as e:
            logger.error(f"Error counting lines in {file_path}: {e}")
            raise
    
    def deduplicate_hashes(self, file_path: str, output_path: str) -> Dict[str, any]:
        """
        Remove duplicate hashes from file.
        
        Args:
            file_path: Input file path
            output_path: Output file path
            
        Returns:
            Statistics about deduplication
        """
        try:
            seen_hashes = set()
            original_count = 0
            unique_count = 0
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile, \
                 open(output_path, 'w', encoding='utf-8') as outfile:
                
                for line in infile:
                    original_count += 1
                    line = line.strip()
                    
                    if not line or line.startswith('#'):
                        outfile.write(line + '\n')
                        continue
                    
                    # Use lowercase hash for comparison
                    hash_key = line.lower()
                    
                    if hash_key not in seen_hashes:
                        seen_hashes.add(hash_key)
                        outfile.write(line + '\n')
                        unique_count += 1
            
            duplicates_removed = original_count - unique_count
            
            return {
                'success': True,
                'original_count': original_count,
                'unique_count': unique_count,
                'duplicates_removed': duplicates_removed,
                'deduplication_ratio': duplicates_removed / original_count if original_count > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error deduplicating file {file_path}: {e}")
            return {'success': False, 'error': str(e)}
    
    def sample_hashes(self, file_path: str, sample_size: int, output_path: str) -> Dict[str, any]:
        """
        Create a sample of hashes from a large file.
        
        Args:
            file_path: Input file path
            sample_size: Number of hashes to sample
            output_path: Output file path
            
        Returns:
            Sampling statistics
        """
        try:
            # First, count total lines
            total_lines = self.count_lines(file_path)
            
            if total_lines <= sample_size:
                # File is small enough, just copy it
                import shutil
                shutil.copy2(file_path, output_path)
                return {
                    'success': True,
                    'total_lines': total_lines,
                    'sampled_lines': total_lines,
                    'sampling_ratio': 1.0
                }
            
            # Calculate sampling interval
            interval = max(1, total_lines // sample_size)
            
            sampled_count = 0
            line_count = 0
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile, \
                 open(output_path, 'w', encoding='utf-8') as outfile:
                
                for line in infile:
                    line_count += 1
                    
                    # Sample every nth line
                    if line_count % interval == 0 or sampled_count < sample_size:
                        outfile.write(line)
                        sampled_count += 1
                        
                        if sampled_count >= sample_size:
                            break
            
            return {
                'success': True,
                'total_lines': total_lines,
                'sampled_lines': sampled_count,
                'sampling_ratio': sampled_count / total_lines,
                'interval': interval
            }
            
        except Exception as e:
            logger.error(f"Error sampling file {file_path}: {e}")
            return {'success': False, 'error': str(e)}


class SecureFileOperations:
    """Secure file operations with validation."""
    
    def __init__(self, security_validator: SecurityValidator):
        self.validator = security_validator
    
    def read_lines_streaming(self, file_path: str) -> Iterator[Tuple[int, str]]:
        """Safely read file lines with line numbers."""
        try:
            safe_path = self.validator.validate_file_path(file_path, must_exist=True)
            
            with open(safe_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    yield line_num, line.strip()
                    
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise
    
    def write_lines(self, file_path: str, lines: List[str]) -> bool:
        """Safely write lines to file."""
        try:
            # Validate output path
            safe_path = self.validator.validate_file_path(file_path, must_exist=False)
            
            with open(safe_path, 'w', encoding='utf-8') as f:
                for line in lines:
                    f.write(line + '\n')
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            return False