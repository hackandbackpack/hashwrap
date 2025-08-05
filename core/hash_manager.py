import os
import time
import threading
import queue
from typing import Set, Dict, List, Tuple, Optional
from datetime import datetime
from .streaming_hash_processor import StreamingHashProcessor


class HashManager:
    """Intelligent hash management with real-time tracking and optimization."""
    
    def __init__(self, hash_file: str, potfile: str, streaming_mode: bool = False, 
                 max_memory_mb: int = 512):
        self.hash_file = hash_file
        self.potfile = potfile
        self.streaming_mode = streaming_mode
        self.original_hashes: Set[str] = set()
        self.cracked_hashes: Dict[str, str] = {}  # hash -> plaintext
        self.remaining_hashes: Set[str] = set()
        self.crack_times: Dict[str, datetime] = {}  # Track when each hash was cracked
        self.attack_effectiveness: Dict[str, int] = {}  # Track which attacks crack most hashes
        
        # Thread safety for hot-reload
        self.hash_lock = threading.Lock()
        self.new_hashes_queue = queue.Queue()
        
        # Streaming support for large files
        self.stream_processor = StreamingHashProcessor(max_memory_mb=max_memory_mb) if streaming_mode else None
        self.total_hash_count = 0  # Track total without loading all into memory
        
        self._load_initial_state()
        
    def _load_initial_state(self):
        """Load initial hashes and check potfile for already cracked ones."""
        # Load all hashes from file
        if os.path.exists(self.hash_file):
            if self.streaming_mode and self.stream_processor:
                # Streaming mode: count hashes without loading all into memory
                self.total_hash_count = self.stream_processor.count_hashes(self.hash_file)
                # Only load a sample for quick analysis
                for batch in self.stream_processor.stream_hashes(self.hash_file, batch_size=10000):
                    self.original_hashes.update(batch)
                    if len(self.original_hashes) >= 100000:  # Limit sample size
                        break
            else:
                # Traditional mode: load all hashes
                with open(self.hash_file, 'r', encoding='utf-8', errors='ignore') as f:
                    self.original_hashes = {line.strip() for line in f if line.strip()}
        
        # Load already cracked hashes from potfile
        if os.path.exists(self.potfile):
            with open(self.potfile, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if ':' in line:
                        parts = line.strip().split(':', 1)
                        if len(parts) == 2:
                            hash_val, plaintext = parts
                            self.cracked_hashes[hash_val] = plaintext
        
        # Calculate remaining hashes
        cracked_hash_values = set(self.cracked_hashes.keys())
        self.remaining_hashes = self.original_hashes - cracked_hash_values
        
    def update_progress(self, attack_name: str = None) -> Dict[str, any]:
        """Update progress by checking potfile for new cracks."""
        newly_cracked = []
        
        if os.path.exists(self.potfile):
            with open(self.potfile, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if ':' in line:
                        parts = line.strip().split(':', 1)
                        if len(parts) == 2:
                            hash_val, plaintext = parts
                            if hash_val not in self.cracked_hashes:
                                self.cracked_hashes[hash_val] = plaintext
                                self.crack_times[hash_val] = datetime.now()
                                newly_cracked.append((hash_val, plaintext))
                                
                                # Track attack effectiveness
                                if attack_name:
                                    self.attack_effectiveness[attack_name] = \
                                        self.attack_effectiveness.get(attack_name, 0) + 1
        
        # Update remaining hashes
        cracked_hash_values = set(self.cracked_hashes.keys())
        self.remaining_hashes = self.original_hashes - cracked_hash_values
        
        return {
            'newly_cracked': newly_cracked,
            'total_cracked': len(self.cracked_hashes),
            'remaining': len(self.remaining_hashes),
            'all_cracked': len(self.remaining_hashes) == 0
        }
    
    def get_statistics(self) -> Dict[str, any]:
        """Get comprehensive statistics about the cracking session."""
        total = len(self.original_hashes)
        cracked = len(self.cracked_hashes)
        remaining = len(self.remaining_hashes)
        
        return {
            'total_hashes': total,
            'cracked': cracked,
            'remaining': remaining,
            'success_rate': (cracked / total * 100) if total > 0 else 0,
            'attack_effectiveness': self.attack_effectiveness,
            'recent_cracks': self._get_recent_cracks(5)
        }
    
    def _get_recent_cracks(self, limit: int = 5) -> List[Tuple[str, str, datetime]]:
        """Get the most recently cracked hashes."""
        recent = sorted(
            [(h, p, t) for h, (p, t) in 
             [(h, (self.cracked_hashes[h], self.crack_times.get(h, datetime.now()))) 
              for h in self.cracked_hashes]],
            key=lambda x: x[2],
            reverse=True
        )[:limit]
        return recent
    
    def should_continue(self) -> bool:
        """Determine if we should continue attacking."""
        return len(self.remaining_hashes) > 0
    
    def get_remaining_hashes_file(self) -> str:
        """Create a temporary file with only uncracked hashes for efficiency."""
        temp_file = f"{self.hash_file}.remaining"
        with open(temp_file, 'w') as f:
            for hash_val in self.remaining_hashes:
                f.write(f"{hash_val}\n")
        return temp_file
    
    def analyze_cracked_passwords(self) -> Dict[str, any]:
        """Analyze patterns in cracked passwords to inform future attacks."""
        if not self.cracked_hashes:
            return {}
        
        passwords = list(self.cracked_hashes.values())
        
        analysis = {
            'total_cracked': len(passwords),
            'average_length': sum(len(p) for p in passwords) / len(passwords),
            'length_distribution': {},
            'character_sets': {
                'lowercase_only': 0,
                'uppercase_only': 0,
                'mixed_case': 0,
                'with_numbers': 0,
                'with_special': 0,
                'alphanumeric_only': 0
            },
            'common_patterns': []
        }
        
        # Analyze each password
        for pwd in passwords:
            # Length distribution
            pwd_len = len(pwd)
            analysis['length_distribution'][pwd_len] = \
                analysis['length_distribution'].get(pwd_len, 0) + 1
            
            # Character set analysis
            has_lower = any(c.islower() for c in pwd)
            has_upper = any(c.isupper() for c in pwd)
            has_digit = any(c.isdigit() for c in pwd)
            has_special = any(not c.isalnum() for c in pwd)
            
            if has_lower and not has_upper and not has_digit and not has_special:
                analysis['character_sets']['lowercase_only'] += 1
            elif has_upper and not has_lower and not has_digit and not has_special:
                analysis['character_sets']['uppercase_only'] += 1
            elif has_lower and has_upper:
                analysis['character_sets']['mixed_case'] += 1
            if has_digit:
                analysis['character_sets']['with_numbers'] += 1
            if has_special:
                analysis['character_sets']['with_special'] += 1
            if not has_special:
                analysis['character_sets']['alphanumeric_only'] += 1
        
        return analysis
    
    def suggest_next_attack(self) -> Optional[Dict[str, any]]:
        """Suggest the next attack based on analysis of cracked passwords."""
        analysis = self.analyze_cracked_passwords()
        
        if not analysis:
            return None
        
        suggestions = []
        
        # Suggest based on length distribution
        if analysis['length_distribution']:
            most_common_length = max(analysis['length_distribution'].items(), 
                                   key=lambda x: x[1])[0]
            suggestions.append({
                'type': 'mask_attack',
                'reason': f'Most passwords are {most_common_length} characters',
                'mask': '?a' * most_common_length
            })
        
        # Suggest based on character sets
        char_sets = analysis['character_sets']
        if char_sets['lowercase_only'] > char_sets['with_special']:
            suggestions.append({
                'type': 'dictionary_attack',
                'reason': 'Many passwords are lowercase only',
                'wordlist': 'lowercase_words.txt'
            })
        
        if char_sets['with_numbers'] > len(self.cracked_hashes) * 0.5:
            suggestions.append({
                'type': 'rule_attack',
                'reason': 'Many passwords contain numbers',
                'rule': 'append_numbers.rule'
            })
        
        return suggestions[0] if suggestions else None
    
    def add_hashes_dynamically(self, new_hashes: List[str]) -> int:
        """Add new hashes to the working set (thread-safe)."""
        added_count = 0
        
        with self.hash_lock:
            # Add to original hashes
            for hash_val in new_hashes:
                hash_val = hash_val.strip()
                if hash_val and hash_val not in self.original_hashes:
                    self.original_hashes.add(hash_val)
                    
                    # Only add to remaining if not already cracked
                    if hash_val not in self.cracked_hashes:
                        self.remaining_hashes.add(hash_val)
                        added_count += 1
            
            # Signal that new hashes are available
            if added_count > 0:
                self.new_hashes_queue.put(added_count)
        
        return added_count