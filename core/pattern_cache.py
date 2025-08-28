"""
Optimized pattern matching with caching for improved performance.
Pre-compiles and caches regex patterns to avoid repeated compilation.
"""

import re
import functools
from typing import Dict, Pattern, Optional, List, Tuple
from threading import RLock

from .logger import get_logger


class PatternCache:
    """Thread-safe cache for compiled regex patterns."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: Dict[str, Pattern] = {}
        self._lock = RLock()
        self._hits = 0
        self._misses = 0
        self.logger = get_logger('pattern_cache')
    
    def get_pattern(self, pattern: str, flags: int = 0) -> Pattern:
        """Get a compiled pattern from cache or compile and cache it."""
        cache_key = f"{pattern}:{flags}"
        
        with self._lock:
            if cache_key in self._cache:
                self._hits += 1
                return self._cache[cache_key]
            
            self._misses += 1
            
            # Compile pattern
            try:
                compiled = re.compile(pattern, flags)
            except re.error as e:
                self.logger.error(f"Invalid regex pattern: {pattern}", error=e)
                raise
            
            # Add to cache (with LRU eviction if needed)
            if len(self._cache) >= self.max_size:
                # Simple eviction: remove first item (could be improved with LRU)
                first_key = next(iter(self._cache))
                del self._cache[first_key]
            
            self._cache[cache_key] = compiled
            return compiled
    
    def match(self, pattern: str, text: str, flags: int = 0) -> Optional[re.Match]:
        """Match pattern against text using cached pattern."""
        compiled = self.get_pattern(pattern, flags)
        return compiled.match(text)
    
    def search(self, pattern: str, text: str, flags: int = 0) -> Optional[re.Match]:
        """Search for pattern in text using cached pattern."""
        compiled = self.get_pattern(pattern, flags)
        return compiled.search(text)
    
    def findall(self, pattern: str, text: str, flags: int = 0) -> List[str]:
        """Find all matches of pattern in text using cached pattern."""
        compiled = self.get_pattern(pattern, flags)
        return compiled.findall(text)
    
    def clear(self):
        """Clear the pattern cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            
            return {
                'size': len(self._cache),
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate
            }


# Global pattern cache instance
_pattern_cache = PatternCache()


def get_pattern_cache() -> PatternCache:
    """Get the global pattern cache instance."""
    return _pattern_cache


# Optimized hash patterns with pre-compilation
class HashPatterns:
    """Pre-compiled patterns for common hash formats."""
    
    # Initialize patterns on first use
    _patterns: Optional[Dict[str, Pattern]] = None
    _lock = RLock()
    
    @classmethod
    def _init_patterns(cls):
        """Initialize hash patterns (lazy loading)."""
        if cls._patterns is not None:
            return
        
        with cls._lock:
            if cls._patterns is not None:
                return
            
            cls._patterns = {
                'md5': re.compile(r'^[a-fA-F0-9]{32}$'),
                'sha1': re.compile(r'^[a-fA-F0-9]{40}$'),
                'sha256': re.compile(r'^[a-fA-F0-9]{64}$'),
                'sha512': re.compile(r'^[a-fA-F0-9]{128}$'),
                'bcrypt': re.compile(r'^\$2[ayb]\$[0-9]{2}\$[./0-9A-Za-z]{53}$'),
                'md5_salt': re.compile(r'^[a-fA-F0-9]{32}:[a-zA-Z0-9./+=\-_]+$'),
                'salt_md5': re.compile(r'^[a-zA-Z0-9./+=\-_]+:[a-fA-F0-9]{32}$'),
                'mysql': re.compile(r'^\*[A-F0-9]{40}$'),
                'ntlm': re.compile(r'^[a-fA-F0-9]{32}$'),  # Same as MD5 length
                'sha1_salt': re.compile(r'^[a-fA-F0-9]{40}:[a-zA-Z0-9./+=\-_]+$'),
                'unix_crypt': re.compile(r'^\$[0-9a-z]+\$[./0-9A-Za-z]+$'),
                'md5_crypt': re.compile(r'^\$1\$[a-zA-Z0-9./]{0,8}\$[a-zA-Z0-9./]{22}$'),  # MD5 crypt
                
                # Generic patterns
                'hex_hash': re.compile(r'^[a-fA-F0-9]+$'),
                'hash_salt': re.compile(r'^[a-fA-F0-9]+:[^:]+$'),
                'salt_hash': re.compile(r'^[^:]+:[a-fA-F0-9]+$'),
                
                # Validation patterns
                'safe_filename': re.compile(r'^[a-zA-Z0-9_\-\.]+$'),
                'safe_session': re.compile(r'^[a-zA-Z0-9_\-]+$'),
                'safe_mask_chars': re.compile(r'^[?ludsahHx0-9a-zA-Z]+$'),  # Allow letters for static parts
                'numeric': re.compile(r'^\d+$'),
                'alphanumeric': re.compile(r'^[a-zA-Z0-9]+$')
            }
    
    @classmethod
    def match_hash_type(cls, hash_string: str) -> Optional[str]:
        """Match hash string against known patterns and return type."""
        cls._init_patterns()
        
        # Strip whitespace
        hash_string = hash_string.strip()
        
        # Try specific patterns first (more specific to less specific)
        specific_patterns = [
            'bcrypt', 'mysql', 'md5_crypt', 'unix_crypt',
            'md5_salt', 'salt_md5', 'sha1_salt'
        ]
        
        for pattern_name in specific_patterns:
            if cls._patterns[pattern_name].match(hash_string):
                return pattern_name
        
        # Then try length-based patterns
        hash_len = len(hash_string)
        if hash_len == 32 and cls._patterns['hex_hash'].match(hash_string):
            # Could be MD5 or NTLM
            return 'md5'  # Default to MD5
        elif hash_len == 40 and cls._patterns['hex_hash'].match(hash_string):
            return 'sha1'
        elif hash_len == 64 and cls._patterns['hex_hash'].match(hash_string):
            return 'sha256'
        elif hash_len == 128 and cls._patterns['hex_hash'].match(hash_string):
            return 'sha512'
        
        # Check generic patterns
        if cls._patterns['hash_salt'].match(hash_string):
            return 'hash_salt'
        elif cls._patterns['salt_hash'].match(hash_string):
            return 'salt_hash'
        
        return None
    
    @classmethod
    def is_valid_filename(cls, filename: str) -> bool:
        """Check if filename is safe."""
        cls._init_patterns()
        return bool(cls._patterns['safe_filename'].match(filename))
    
    @classmethod
    def is_valid_session_name(cls, name: str) -> bool:
        """Check if session name is safe."""
        cls._init_patterns()
        return bool(cls._patterns['safe_session'].match(name))
    
    @classmethod
    def is_valid_mask(cls, mask: str) -> bool:
        """Check if mask contains only safe characters."""
        cls._init_patterns()
        return bool(cls._patterns['safe_mask_chars'].match(mask))


# Cached validators using functools.lru_cache
@functools.lru_cache(maxsize=10000)
def is_valid_hash_cached(hash_string: str) -> bool:
    """Cached validation of hash format."""
    # Quick length check
    if len(hash_string) < 8 or len(hash_string) > 1024:
        return False
    
    # Check against patterns
    return HashPatterns.match_hash_type(hash_string) is not None


@functools.lru_cache(maxsize=1000)
def validate_path_cached(path: str) -> bool:
    """Cached validation of file paths."""
    # Basic checks
    if not path or '..' in path:
        return False
    
    # Check for null bytes
    if '\x00' in path:
        return False
    
    # Platform-specific checks
    import sys
    if sys.platform == 'win32':
        # Windows reserved names
        reserved = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                   'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
                   'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
        
        import os
        basename = os.path.basename(path).upper()
        if basename in reserved or basename.split('.')[0] in reserved:
            return False
    
    return True


# Optimized mask validation
class MaskOptimizer:
    """Optimize mask-based attacks."""
    
    # Charset definitions
    CHARSETS = {
        '?l': 'abcdefghijklmnopqrstuvwxyz',
        '?u': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
        '?d': '0123456789',
        '?s': ' !"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~',
        '?a': None,  # All printable ASCII
        '?h': '0123456789abcdef',
        '?H': '0123456789ABCDEF'
    }
    
    @classmethod
    def calculate_keyspace(cls, mask: str) -> int:
        """Calculate the keyspace size for a mask."""
        keyspace = 1
        i = 0
        
        while i < len(mask):
            if i + 1 < len(mask) and mask[i:i+2] in cls.CHARSETS:
                charset = mask[i:i+2]
                if charset == '?a':
                    keyspace *= 95  # All printable ASCII
                else:
                    keyspace *= len(cls.CHARSETS[charset])
                i += 2
            else:
                keyspace *= 1  # Static character
                i += 1
        
        return keyspace
    
    @classmethod
    def is_mask_too_large(cls, mask: str, max_keyspace: int = 10**15) -> bool:
        """Check if mask keyspace is too large."""
        return cls.calculate_keyspace(mask) > max_keyspace
    
    @classmethod
    def optimize_mask(cls, mask: str) -> List[str]:
        """Optimize mask by breaking it into smaller chunks if needed."""
        keyspace = cls.calculate_keyspace(mask)
        
        if keyspace <= 10**12:  # Reasonable size
            return [mask]
        
        # For large masks, suggest alternatives
        suggestions = []
        
        # Try common password patterns
        if '?a' in mask:
            # Replace ?a with more specific charsets
            suggestions.append(mask.replace('?a', '?l?d'))
            suggestions.append(mask.replace('?a', '?u?l?d'))
        
        return suggestions if suggestions else [mask]