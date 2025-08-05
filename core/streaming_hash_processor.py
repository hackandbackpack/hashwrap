"""
Memory-efficient hash file processing with streaming support.
Handles large hash files without loading everything into memory.
"""

import os
from typing import Iterator, Set, Dict, Optional, Tuple
from pathlib import Path
import mmap
from collections import deque


class StreamingHashProcessor:
    """Process large hash files efficiently using streaming and memory mapping."""
    
    def __init__(self, chunk_size: int = 64 * 1024, max_memory_mb: int = 512):
        """
        Initialize the streaming processor.
        
        Args:
            chunk_size: Size of chunks to read at once (default 64KB)
            max_memory_mb: Maximum memory to use for caching (default 512MB)
        """
        self.chunk_size = chunk_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._file_positions = {}  # Track reading positions for incremental reads
    
    def count_hashes(self, file_path: str) -> int:
        """
        Count hashes in a file without loading into memory.
        
        Args:
            file_path: Path to hash file
            
        Returns:
            Number of non-empty lines in the file
        """
        count = 0
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if line.strip():
                    count += 1
        return count
    
    def stream_hashes(self, file_path: str, batch_size: int = 10000) -> Iterator[List[str]]:
        """
        Stream hashes from file in batches to control memory usage.
        
        Args:
            file_path: Path to hash file
            batch_size: Number of hashes per batch
            
        Yields:
            Batches of hash strings
        """
        batch = []
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line:
                    batch.append(line)
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
            
            # Yield remaining hashes
            if batch:
                yield batch
    
    def read_incremental(self, file_path: str) -> Iterator[str]:
        """
        Read only new lines added to a file since last read.
        
        Args:
            file_path: Path to file to monitor
            
        Yields:
            New lines added since last read
        """
        # Get last position
        last_position = self._file_positions.get(file_path, 0)
        
        # Check if file was truncated or replaced
        try:
            file_size = os.path.getsize(file_path)
            if file_size < last_position:
                # File was truncated or replaced, start from beginning
                last_position = 0
        except OSError:
            return  # File doesn't exist
        
        # Read from last position
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(last_position)
            
            for line in f:
                line = line.strip()
                if line:
                    yield line
            
            # Update position
            self._file_positions[file_path] = f.tell()
    
    def create_filtered_file(self, input_path: str, output_path: str, 
                           exclude_hashes: Set[str], chunk_size: int = 10000) -> int:
        """
        Create a new file excluding specified hashes, using streaming.
        
        Args:
            input_path: Source hash file
            output_path: Destination file  
            exclude_hashes: Set of hashes to exclude
            chunk_size: Process in chunks for memory efficiency
            
        Returns:
            Number of hashes written
        """
        written_count = 0
        buffer = []
        
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as infile:
            with open(output_path, 'w', encoding='utf-8') as outfile:
                for line in infile:
                    line = line.strip()
                    if line and line not in exclude_hashes:
                        buffer.append(line + '\n')
                        written_count += 1
                        
                        # Write buffer when full
                        if len(buffer) >= chunk_size:
                            outfile.writelines(buffer)
                            buffer = []
                
                # Write remaining buffer
                if buffer:
                    outfile.writelines(buffer)
        
        return written_count
    
    def memory_map_search(self, file_path: str, search_hash: str) -> bool:
        """
        Search for a hash using memory mapping (efficient for large files).
        
        Args:
            file_path: Path to hash file
            search_hash: Hash to search for
            
        Returns:
            True if hash found, False otherwise
        """
        if not os.path.exists(file_path):
            return False
        
        search_bytes = (search_hash + '\n').encode('utf-8')
        
        with open(file_path, 'r+b') as f:
            # Memory map the file
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped:
                return mmapped.find(search_bytes) != -1
    
    def extract_hash_subset(self, file_path: str, indices: Set[int]) -> List[str]:
        """
        Extract specific hashes by line indices without loading entire file.
        
        Args:
            file_path: Path to hash file
            indices: Set of line indices to extract (0-based)
            
        Returns:
            List of extracted hashes
        """
        extracted = []
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f):
                if line_num in indices:
                    line = line.strip()
                    if line:
                        extracted.append(line)
                    
                    # Early exit if we've found all requested indices
                    if len(extracted) == len(indices):
                        break
        
        return extracted
    
    def analyze_hash_distribution(self, file_path: str, sample_size: int = 10000) -> Dict[str, int]:
        """
        Analyze hash type distribution by sampling the file.
        
        Args:
            file_path: Path to hash file
            sample_size: Number of hashes to sample
            
        Returns:
            Dictionary of hash patterns and their counts
        """
        patterns = {
            'md5_like': 0,      # 32 hex chars
            'sha1_like': 0,     # 40 hex chars
            'sha256_like': 0,   # 64 hex chars
            'sha512_like': 0,   # 128 hex chars
            'with_salt': 0,     # Contains :
            'special_format': 0  # Starts with $
        }
        
        sample_count = 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Analyze pattern
                if line.startswith('$'):
                    patterns['special_format'] += 1
                elif ':' in line:
                    patterns['with_salt'] += 1
                elif len(line) == 32 and all(c in '0123456789abcdefABCDEF' for c in line):
                    patterns['md5_like'] += 1
                elif len(line) == 40 and all(c in '0123456789abcdefABCDEF' for c in line):
                    patterns['sha1_like'] += 1
                elif len(line) == 64 and all(c in '0123456789abcdefABCDEF' for c in line):
                    patterns['sha256_like'] += 1
                elif len(line) == 128 and all(c in '0123456789abcdefABCDEF' for c in line):
                    patterns['sha512_like'] += 1
                
                sample_count += 1
                if sample_count >= sample_size:
                    break
        
        # Remove zero counts
        return {k: v for k, v in patterns.items() if v > 0}
    
    def split_file_by_type(self, file_path: str, output_dir: str) -> Dict[str, str]:
        """
        Split hash file by detected type for optimal processing.
        
        Args:
            file_path: Source hash file
            output_dir: Directory for output files
            
        Returns:
            Dictionary mapping hash type to output file path
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Open file handles for each type
        file_handles = {}
        output_files = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Determine hash type
                    hash_type = self._detect_hash_type_simple(line)
                    
                    # Get or create file handle
                    if hash_type not in file_handles:
                        output_path = os.path.join(output_dir, f"{hash_type}_hashes.txt")
                        file_handles[hash_type] = open(output_path, 'w', encoding='utf-8')
                        output_files[hash_type] = output_path
                    
                    # Write to appropriate file
                    file_handles[hash_type].write(line + '\n')
        
        finally:
            # Close all file handles
            for handle in file_handles.values():
                handle.close()
        
        return output_files
    
    def _detect_hash_type_simple(self, hash_string: str) -> str:
        """Simple hash type detection for file splitting."""
        if hash_string.startswith('$'):
            # Extract format identifier
            if hash_string.startswith('$2'):
                return 'bcrypt'
            elif hash_string.startswith('$6$'):
                return 'sha512crypt'
            elif hash_string.startswith('$5$'):
                return 'sha256crypt'
            elif hash_string.startswith('$1$'):
                return 'md5crypt'
            else:
                return 'special'
        elif ':' in hash_string:
            return 'salted'
        elif len(hash_string) == 32:
            return 'md5'
        elif len(hash_string) == 40:
            return 'sha1'
        elif len(hash_string) == 64:
            return 'sha256'
        elif len(hash_string) == 128:
            return 'sha512'
        else:
            return 'unknown'


class CircularHashBuffer:
    """Memory-efficient circular buffer for recently processed hashes."""
    
    def __init__(self, max_size: int = 100000):
        """
        Initialize circular buffer.
        
        Args:
            max_size: Maximum number of hashes to keep
        """
        self.buffer = deque(maxlen=max_size)
        self.hash_set = set()  # For O(1) lookups
        self.max_size = max_size
    
    def add(self, hash_value: str) -> bool:
        """
        Add hash to buffer.
        
        Args:
            hash_value: Hash to add
            
        Returns:
            True if hash was new, False if already existed
        """
        if hash_value in self.hash_set:
            return False
        
        # If at capacity, remove oldest
        if len(self.buffer) >= self.max_size:
            oldest = self.buffer[0]
            self.hash_set.discard(oldest)
        
        self.buffer.append(hash_value)
        self.hash_set.add(hash_value)
        return True
    
    def contains(self, hash_value: str) -> bool:
        """Check if hash is in buffer."""
        return hash_value in self.hash_set
    
    def clear(self):
        """Clear the buffer."""
        self.buffer.clear()
        self.hash_set.clear()