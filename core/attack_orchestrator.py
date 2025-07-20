import heapq
import json
import os
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AttackPriority(Enum):
    """Priority levels for different attack types."""
    QUICK_WIN = 1      # Common passwords, top 10k
    TARGETED = 2       # Context-specific attacks
    RULE_BASED = 3     # Dictionary + rules
    HYBRID = 4         # Combination attacks
    MASK = 5           # Pattern-based attacks
    EXHAUSTIVE = 6     # Brute force


@dataclass(order=True)
class Attack:
    """Represents a single attack strategy."""
    priority: int
    name: str = field(compare=False)
    attack_type: str = field(compare=False)
    wordlist: Optional[str] = field(default=None, compare=False)
    rules: Optional[str] = field(default=None, compare=False)
    mask: Optional[str] = field(default=None, compare=False)
    mode: Optional[int] = field(default=None, compare=False)
    estimated_duration: Optional[int] = field(default=None, compare=False)
    success_probability: float = field(default=0.5, compare=False)
    
    def to_hashcat_args(self) -> List[str]:
        """Convert attack to hashcat command arguments."""
        args = []
        
        if self.mode:
            args.extend(['-m', str(self.mode)])
            
        if self.attack_type == 'dictionary':
            args.extend(['-a', '0'])
            if self.wordlist:
                args.append(self.wordlist)
            if self.rules:
                args.extend(['-r', self.rules])
                
        elif self.attack_type == 'mask':
            args.extend(['-a', '3'])
            if self.mask:
                args.append(self.mask)
                
        elif self.attack_type == 'hybrid':
            args.extend(['-a', '6'])
            if self.wordlist:
                args.append(self.wordlist)
            if self.mask:
                args.append(self.mask)
        
        return args


class AttackOrchestrator:
    """Intelligent attack scheduling and prioritization."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.attack_queue: List[Attack] = []
        self.completed_attacks: List[Tuple[Attack, Dict[str, Any]]] = []
        self.success_tracker: Dict[str, float] = {}
        self.config = self._load_config(config_path) if config_path else {}
        
    def _load_config(self, config_path: str) -> Dict:
        """Load orchestrator configuration."""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def add_attack(self, attack: Attack):
        """Add an attack to the priority queue."""
        heapq.heappush(self.attack_queue, attack)
    
    def get_next_attack(self) -> Optional[Attack]:
        """Get the highest priority attack from the queue."""
        if self.attack_queue:
            return heapq.heappop(self.attack_queue)
        return None
    
    def generate_attack_plan(self, hash_analysis: Dict[str, Any], 
                           available_resources: Dict[str, Any]) -> List[Attack]:
        """Generate a comprehensive attack plan based on hash analysis."""
        attacks = []
        
        # Get hash mode from analysis
        hash_mode = None
        if hash_analysis.get('detected_types'):
            # Use the most common hash type
            most_common = max(hash_analysis['detected_types'].items(), 
                            key=lambda x: x[1]['count'])
            hash_mode = most_common[1]['mode']
        
        # Phase 1: Quick wins
        quick_attacks = self._generate_quick_attacks(hash_mode, hash_analysis)
        attacks.extend(quick_attacks)
        
        # Phase 2: Targeted attacks based on context
        if self._looks_like_ad_dump(hash_analysis):
            attacks.extend(self._generate_ad_attacks(hash_mode))
        elif self._looks_like_web_app(hash_analysis):
            attacks.extend(self._generate_web_attacks(hash_mode))
        
        # Phase 3: Rule-based attacks
        attacks.extend(self._generate_rule_attacks(hash_mode))
        
        # Phase 4: Mask attacks based on policy
        if hash_analysis.get('password_policy'):
            attacks.extend(self._generate_policy_masks(hash_mode, 
                                                      hash_analysis['password_policy']))
        
        # Add all attacks to queue
        for attack in attacks:
            self.add_attack(attack)
        
        return attacks
    
    def _generate_quick_attacks(self, mode: Optional[int], 
                               analysis: Dict[str, Any]) -> List[Attack]:
        """Generate quick win attacks."""
        attacks = []
        
        # Common passwords
        attacks.append(Attack(
            priority=AttackPriority.QUICK_WIN.value,
            name="Top 100k passwords",
            attack_type="dictionary",
            wordlist="wordlists/top100k.txt",
            mode=mode,
            estimated_duration=60,
            success_probability=0.8
        ))
        
        # Common patterns
        attacks.append(Attack(
            priority=AttackPriority.QUICK_WIN.value,
            name="Common patterns",
            attack_type="mask",
            mask="?u?l?l?l?l?l?d?d",  # Ulllldd pattern
            mode=mode,
            estimated_duration=120,
            success_probability=0.6
        ))
        
        return attacks
    
    def _generate_ad_attacks(self, mode: Optional[int]) -> List[Attack]:
        """Generate Active Directory specific attacks."""
        attacks = []
        
        # Season + Year
        attacks.append(Attack(
            priority=AttackPriority.TARGETED.value,
            name="Season + Year patterns",
            attack_type="dictionary",
            wordlist="wordlists/seasons_years.txt",
            mode=mode,
            success_probability=0.7
        ))
        
        # Company name variations
        attacks.append(Attack(
            priority=AttackPriority.TARGETED.value,
            name="Company variations",
            attack_type="dictionary",
            wordlist="wordlists/company_variations.txt",
            rules="rules/ad_common.rule",
            mode=mode,
            success_probability=0.6
        ))
        
        return attacks
    
    def _generate_web_attacks(self, mode: Optional[int]) -> List[Attack]:
        """Generate web application specific attacks."""
        attacks = []
        
        attacks.append(Attack(
            priority=AttackPriority.TARGETED.value,
            name="Web app defaults",
            attack_type="dictionary",
            wordlist="wordlists/web_defaults.txt",
            mode=mode,
            success_probability=0.5
        ))
        
        return attacks
    
    def _generate_rule_attacks(self, mode: Optional[int]) -> List[Attack]:
        """Generate rule-based attacks."""
        attacks = []
        
        # Best64 rule with rockyou
        attacks.append(Attack(
            priority=AttackPriority.RULE_BASED.value,
            name="RockYou + Best64",
            attack_type="dictionary",
            wordlist="wordlists/rockyou.txt",
            rules="rules/best64.rule",
            mode=mode,
            estimated_duration=3600,
            success_probability=0.7
        ))
        
        # Leetspeak variations
        attacks.append(Attack(
            priority=AttackPriority.RULE_BASED.value,
            name="Leetspeak variations",
            attack_type="dictionary",
            wordlist="wordlists/common_words.txt",
            rules="rules/leetspeak.rule",
            mode=mode,
            success_probability=0.5
        ))
        
        return attacks
    
    def _generate_policy_masks(self, mode: Optional[int], 
                              policy: Dict[str, Any]) -> List[Attack]:
        """Generate masks based on password policy."""
        attacks = []
        
        min_len = policy.get('min_length', 8)
        requires_upper = policy.get('requires_uppercase', False)
        requires_lower = policy.get('requires_lowercase', False)
        requires_digit = policy.get('requires_digit', False)
        requires_special = policy.get('requires_special', False)
        
        # Build mask based on requirements
        mask_parts = []
        if requires_upper:
            mask_parts.append('?u')
        if requires_lower:
            mask_parts.extend(['?l'] * (min_len - len(mask_parts) - 2))
        if requires_digit:
            mask_parts.append('?d')
        if requires_special:
            mask_parts.append('?s')
            
        # Pad to minimum length
        while len(mask_parts) < min_len:
            mask_parts.append('?a')
            
        mask = ''.join(mask_parts)
        
        attacks.append(Attack(
            priority=AttackPriority.MASK.value,
            name=f"Policy-based mask ({min_len} chars)",
            attack_type="mask",
            mask=mask,
            mode=mode,
            success_probability=0.4
        ))
        
        return attacks
    
    def _looks_like_ad_dump(self, analysis: Dict[str, Any]) -> bool:
        """Detect if hashes look like Active Directory dump."""
        if not analysis.get('detected_types'):
            return False
            
        # Check for NTLM or NetNTLM
        for hash_type in analysis['detected_types']:
            if 'NTLM' in hash_type:
                return True
        return False
    
    def _looks_like_web_app(self, analysis: Dict[str, Any]) -> bool:
        """Detect if hashes look like web application."""
        if not analysis.get('detected_types'):
            return False
            
        # Check for web app hash types
        web_indicators = ['phpBB', 'WordPress', 'Django', 'bcrypt', 'MD5']
        for hash_type in analysis['detected_types']:
            if any(indicator in hash_type for indicator in web_indicators):
                return True
        return False
    
    def update_success_metrics(self, attack: Attack, results: Dict[str, Any]):
        """Update success tracking for adaptive learning."""
        attack_key = f"{attack.attack_type}_{attack.wordlist}_{attack.rules}"
        
        if results.get('cracked_count', 0) > 0:
            # Calculate success rate
            success_rate = results['cracked_count'] / results.get('total_attempts', 1)
            
            # Update rolling average
            if attack_key in self.success_tracker:
                old_rate = self.success_tracker[attack_key]
                self.success_tracker[attack_key] = (old_rate + success_rate) / 2
            else:
                self.success_tracker[attack_key] = success_rate
        
        # Store completed attack
        self.completed_attacks.append((attack, results))
    
    def get_attack_statistics(self) -> Dict[str, Any]:
        """Get statistics about attack effectiveness."""
        stats = {
            'total_attacks': len(self.completed_attacks),
            'attacks_remaining': len(self.attack_queue),
            'most_effective': [],
            'least_effective': []
        }
        
        # Sort by effectiveness
        sorted_attacks = sorted(self.success_tracker.items(), 
                              key=lambda x: x[1], reverse=True)
        
        stats['most_effective'] = sorted_attacks[:5]
        stats['least_effective'] = sorted_attacks[-5:] if len(sorted_attacks) > 5 else []
        
        return stats