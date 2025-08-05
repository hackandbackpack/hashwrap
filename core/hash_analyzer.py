import re
from typing import Dict, List, Tuple, Optional
from collections import defaultdict


class HashAnalyzer:
    """Intelligent hash type detection and analysis."""
    
    # Hash patterns with their hashcat mode numbers
    HASH_PATTERNS = {
        # MD5 variants
        r'^[a-f0-9]{32}$': {'name': 'MD5', 'mode': 0, 'confidence': 0.9},
        r'^[a-f0-9]{32}:[a-f0-9]+$': {'name': 'MD5 with salt', 'mode': 10, 'confidence': 0.9},
        r'^\$1\$[a-zA-Z0-9./]{8}\$[a-zA-Z0-9./]{22}$': {'name': 'MD5 Crypt', 'mode': 500, 'confidence': 1.0},
        
        # SHA variants
        r'^[a-f0-9]{40}$': {'name': 'SHA1', 'mode': 100, 'confidence': 0.9},
        r'^[a-f0-9]{64}$': {'name': 'SHA256', 'mode': 1400, 'confidence': 0.9},
        r'^[a-f0-9]{96}$': {'name': 'SHA384', 'mode': 10800, 'confidence': 0.9},
        r'^[a-f0-9]{128}$': {'name': 'SHA512', 'mode': 1700, 'confidence': 0.9},
        r'^\$6\$[a-zA-Z0-9./]{8,16}\$[a-zA-Z0-9./]{86}$': {'name': 'SHA512 Crypt', 'mode': 1800, 'confidence': 1.0},
        
        # NTLM/Windows
        r'^[a-f0-9]{32}$': {'name': 'NTLM', 'mode': 1000, 'confidence': 0.7},  # Same as MD5, lower confidence
        r'^[a-f0-9]{32}:[a-f0-9]{32}$': {'name': 'NetNTLMv1', 'mode': 5500, 'confidence': 0.95},
        r'^[a-zA-Z0-9+/]{27,}=$': {'name': 'NetNTLMv2', 'mode': 5600, 'confidence': 0.9},
        
        # bcrypt
        r'^\$2[ayb]\$[0-9]{2}\$[a-zA-Z0-9./]{53}$': {'name': 'bcrypt', 'mode': 3200, 'confidence': 1.0},
        
        # MySQL
        r'^\*[A-F0-9]{40}$': {'name': 'MySQL 4.1+', 'mode': 300, 'confidence': 1.0},
        r'^[a-f0-9]{16}$': {'name': 'MySQL 3.x', 'mode': 200, 'confidence': 0.8},
        
        # PostgreSQL
        r'^md5[a-f0-9]{32}$': {'name': 'PostgreSQL MD5', 'mode': 12, 'confidence': 1.0},
        
        # Kerberos
        r'^\$krb5tgs\$': {'name': 'Kerberos 5 TGS-REP', 'mode': 13100, 'confidence': 1.0},
        r'^\$krb5pa\$': {'name': 'Kerberos 5 AS-REP', 'mode': 7500, 'confidence': 1.0},
        
        # Office/Documents
        r'^\$office\$': {'name': 'MS Office', 'mode': 9400, 'confidence': 1.0},
        r'^\$pdf\$': {'name': 'PDF', 'mode': 10500, 'confidence': 1.0},
        
        # Web Applications
        r'^\$P\$[a-zA-Z0-9./]{31}$': {'name': 'phpBB3/WordPress', 'mode': 400, 'confidence': 1.0},
        r'^\$H\$[a-zA-Z0-9./]{31}$': {'name': 'phpBB3/WordPress (alt)', 'mode': 400, 'confidence': 1.0},
        r'^sha1\$[a-f0-9]{8}\$[a-f0-9]{40}$': {'name': 'Django SHA1', 'mode': 800, 'confidence': 1.0},
        
        # New hash types for hashcat v7.0.0
        # Argon2 variants
        r'^\$argon2i\$': {'name': 'Argon2i', 'mode': 10900, 'confidence': 1.0},
        r'^\$argon2d\$': {'name': 'Argon2d', 'mode': 11300, 'confidence': 1.0},
        r'^\$argon2id\$': {'name': 'Argon2id', 'mode': 11900, 'confidence': 1.0},
        
        # Cryptocurrency wallets
        r'^\$ethereum\$': {'name': 'Ethereum Wallet', 'mode': 15700, 'confidence': 1.0},
        r'^\$bitcoin\$': {'name': 'Bitcoin Wallet', 'mode': 11300, 'confidence': 1.0},
        r'^metamask:': {'name': 'MetaMask Wallet', 'mode': 26600, 'confidence': 1.0},
        
        # Modern encryption
        r'^\$luks\$': {'name': 'LUKS2', 'mode': 29543, 'confidence': 1.0},
        r'^\$ansible\$': {'name': 'Ansible Vault', 'mode': 16900, 'confidence': 1.0},
        r'^\$zip3\$': {'name': 'ZIP3 AES-256', 'mode': 24700, 'confidence': 1.0},
        
        # Cloud/Modern services  
        r'^\$okta\$': {'name': 'Okta PBKDF2-SHA512', 'mode': 10900, 'confidence': 1.0},
        r'^\$mongodb-scram\$': {'name': 'MongoDB SCRAM', 'mode': 24700, 'confidence': 1.0},
        r'^\$msonline\$': {'name': 'Microsoft Online Account', 'mode': 27800, 'confidence': 1.0},
        
        # Additional protocols
        r'^\$snmpv3\$': {'name': 'SNMPv3 HMAC-SHA*-AES*', 'mode': 25000, 'confidence': 1.0},
        r'^\$ssh\$': {'name': 'OpenSSH Private Key', 'mode': 22921, 'confidence': 1.0},
        r'^\$gpg\$': {'name': 'GPG Secret Key', 'mode': 17010, 'confidence': 1.0},
        
        # JWT tokens
        r'^ey[A-Za-z0-9-_]+\.ey[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$': {'name': 'JWT Token', 'mode': 16500, 'confidence': 1.0},
    }
    
    def __init__(self):
        self.detected_types = defaultdict(int)
        self.hash_samples = defaultdict(list)
        
    def analyze_file(self, hash_file: str) -> Dict[str, any]:
        """Analyze a hash file and detect hash types."""
        results = {
            'total_hashes': 0,
            'detected_types': {},
            'unknown_hashes': [],
            'recommendations': []
        }
        
        with open(hash_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                results['total_hashes'] += 1
                detected = self._detect_hash_type(line)
                
                if detected:
                    hash_type = detected['name']
                    if hash_type not in results['detected_types']:
                        results['detected_types'][hash_type] = {
                            'count': 0,
                            'mode': detected['mode'],
                            'confidence': detected['confidence'],
                            'samples': []
                        }
                    
                    results['detected_types'][hash_type]['count'] += 1
                    if len(results['detected_types'][hash_type]['samples']) < 3:
                        results['detected_types'][hash_type]['samples'].append(line[:50] + '...' if len(line) > 50 else line)
                else:
                    if len(results['unknown_hashes']) < 10:
                        results['unknown_hashes'].append({
                            'line': line_num,
                            'hash': line[:50] + '...' if len(line) > 50 else line
                        })
        
        # Generate recommendations
        results['recommendations'] = self._generate_recommendations(results)
        
        return results
    
    def _detect_hash_type(self, hash_string: str) -> Optional[Dict[str, any]]:
        """Detect the type of a single hash."""
        hash_string = hash_string.strip()
        
        # Check against all patterns
        matches = []
        for pattern, info in self.HASH_PATTERNS.items():
            if re.match(pattern, hash_string, re.IGNORECASE):
                matches.append(info.copy())
        
        # If multiple matches, return the one with highest confidence
        if matches:
            return max(matches, key=lambda x: x['confidence'])
        
        # Additional heuristics for common formats
        if ':' in hash_string:
            parts = hash_string.split(':')
            if len(parts) == 2 and all(c in '0123456789abcdef' for c in parts[0].lower()):
                # Likely a hash with salt
                hash_len = len(parts[0])
                if hash_len == 32:
                    return {'name': 'MD5 with salt', 'mode': 10, 'confidence': 0.7}
                elif hash_len == 40:
                    return {'name': 'SHA1 with salt', 'mode': 110, 'confidence': 0.7}
        
        return None
    
    def _generate_recommendations(self, analysis: Dict[str, any]) -> List[Dict[str, any]]:
        """Generate attack recommendations based on hash analysis."""
        recommendations = []
        
        # If we have a single hash type with high confidence
        if len(analysis['detected_types']) == 1:
            hash_type, info = list(analysis['detected_types'].items())[0]
            recommendations.append({
                'priority': 'high',
                'action': 'single_mode_attack',
                'description': f'Use mode {info["mode"]} for {hash_type} hashes',
                'command': f'-m {info["mode"]}'
            })
        
        # If we have multiple hash types
        elif len(analysis['detected_types']) > 1:
            recommendations.append({
                'priority': 'high',
                'action': 'split_by_type',
                'description': 'Split hashes by type for optimal performance',
                'types': {k: v['mode'] for k, v in analysis['detected_types'].items()}
            })
        
        # Check for specific hash types that suggest context
        for hash_type in analysis['detected_types']:
            if 'NTLM' in hash_type or 'NetNTLM' in hash_type:
                recommendations.append({
                    'priority': 'medium',
                    'action': 'use_ad_wordlists',
                    'description': 'Detected Windows hashes - use Active Directory focused wordlists',
                    'wordlists': ['rockyou.txt', 'ad_common.txt', 'corporate_passwords.txt']
                })
            
            elif 'MySQL' in hash_type or 'PostgreSQL' in hash_type:
                recommendations.append({
                    'priority': 'medium',
                    'action': 'use_db_defaults',
                    'description': 'Detected database hashes - try default credentials',
                    'wordlists': ['db_defaults.txt', 'common_passwords.txt']
                })
            
            elif 'bcrypt' in hash_type:
                recommendations.append({
                    'priority': 'high',
                    'action': 'optimize_bcrypt',
                    'description': 'bcrypt is slow - use targeted wordlists and limit iterations',
                    'settings': {'workload_profile': 3, 'limit_rules': True}
                })
        
        # If we have unknown hashes
        if analysis['unknown_hashes']:
            recommendations.append({
                'priority': 'low',
                'action': 'investigate_unknown',
                'description': f'Found {len(analysis["unknown_hashes"])} unknown hash formats - manual review needed',
                'samples': analysis['unknown_hashes'][:3]
            })
        
        return sorted(recommendations, key=lambda x: {'high': 0, 'medium': 1, 'low': 2}[x['priority']])
    
    def suggest_mode(self, hash_sample: str) -> Optional[int]:
        """Quick mode suggestion for a single hash."""
        detected = self._detect_hash_type(hash_sample)
        return detected['mode'] if detected else None