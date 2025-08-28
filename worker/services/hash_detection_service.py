"""
Hash type detection service using hashcat --identify and pattern matching.
Provides intelligent hash type detection with confidence scoring.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, Counter

from worker.utils.logging import get_task_logger
from core.hash_analyzer import HashAnalyzer
from core.pattern_cache import get_pattern_cache


logger = get_task_logger(__name__)


class HashDetectionService:
    """Service for detecting hash types using multiple detection methods."""
    
    def __init__(self):
        self.hash_analyzer = HashAnalyzer()
        self.pattern_cache = get_pattern_cache()
        
        # Hashcat mode to name mapping
        self.mode_to_name = {
            0: 'MD5',
            100: 'SHA1', 
            1400: 'SHA256',
            1700: 'SHA512',
            1000: 'NTLM',
            5500: 'NetNTLMv1',
            5600: 'NetNTLMv2',
            3200: 'bcrypt',
            1800: 'SHA512crypt',
            500: 'MD5crypt',
            300: 'MySQL 4.1+',
            12: 'PostgreSQL MD5',
            400: 'phpBB3/WordPress',
            13100: 'Kerberos 5 TGS-REP',
            7500: 'Kerberos 5 AS-REP',
            9400: 'MS Office',
            10500: 'PDF',
        }
        
        # Confidence thresholds
        self.min_confidence = 0.7
        self.high_confidence = 0.9
    
    def analyze_file(self, file_path: str, max_sample_size: int = 1000) -> Dict[str, any]:
        """
        Analyze a hash file to detect hash types with multiple methods.
        
        Args:
            file_path: Path to the hash file
            max_sample_size: Maximum number of hashes to sample for detection
            
        Returns:
            Dictionary containing detection results
        """
        logger.info(f"Analyzing hash file: {file_path}")
        
        try:
            if not os.path.exists(file_path):
                return {'success': False, 'error': f'File not found: {file_path}'}
            
            # Get file statistics
            file_stats = self._get_file_stats(file_path)
            
            # Sample hashes for analysis
            hash_samples = self._sample_hashes(file_path, max_sample_size)
            
            if not hash_samples:
                return {'success': False, 'error': 'No valid hashes found in file'}
            
            # Method 1: Use hashcat --identify (most accurate)
            hashcat_results = self._detect_with_hashcat(hash_samples)
            
            # Method 2: Use pattern matching (fallback)
            pattern_results = self._detect_with_patterns(hash_samples)
            
            # Method 3: Use existing hash analyzer (additional validation)
            analyzer_results = self._detect_with_analyzer(file_path)
            
            # Combine results with confidence weighting
            final_results = self._combine_detection_results(
                hashcat_results, pattern_results, analyzer_results
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(final_results, file_stats)
            
            result = {
                'success': True,
                'file_path': file_path,
                'file_stats': file_stats,
                'total_hashes': file_stats['total_lines'],
                'detected_types': final_results,
                'recommendations': recommendations,
                'detection_methods': {
                    'hashcat': hashcat_results,
                    'patterns': pattern_results,
                    'analyzer': analyzer_results
                }
            }
            
            logger.info(f"Detection completed for {file_path}: {len(final_results)} hash types found")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def detect_single_hash(self, hash_string: str) -> Dict[str, any]:
        """Detect the type of a single hash string."""
        try:
            # Clean the hash string
            hash_string = hash_string.strip()
            
            if not hash_string:
                return {'success': False, 'error': 'Empty hash string'}
            
            # Try hashcat identification first
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(hash_string + '\n')
                temp_file.flush()
                
                hashcat_result = self._detect_with_hashcat([hash_string])
                pattern_result = self._detect_with_patterns([hash_string])
                
                # Combine results
                combined_results = self._combine_detection_results(
                    hashcat_result, pattern_result, {}
                )
                
                os.unlink(temp_file.name)
                
                if combined_results:
                    # Return the highest confidence result
                    best_match = max(combined_results.items(), 
                                   key=lambda x: x[1]['confidence'])
                    
                    return {
                        'success': True,
                        'hash_type': best_match[0],
                        'confidence': best_match[1]['confidence'],
                        'hashcat_mode': best_match[1]['mode'],
                        'all_matches': combined_results
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Hash type not recognized'
                    }
                    
        except Exception as e:
            logger.error(f"Error detecting single hash: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _get_file_stats(self, file_path: str) -> Dict[str, any]:
        """Get basic statistics about the hash file."""
        stats = {
            'file_size': 0,
            'total_lines': 0,
            'non_empty_lines': 0,
            'unique_lengths': set(),
            'avg_line_length': 0,
            'has_colons': False,
            'has_dollar_signs': False
        }
        
        try:
            file_path_obj = Path(file_path)
            stats['file_size'] = file_path_obj.stat().st_size
            
            line_lengths = []
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    stats['total_lines'] += 1
                    line = line.strip()
                    
                    if line:
                        stats['non_empty_lines'] += 1
                        line_lengths.append(len(line))
                        stats['unique_lengths'].add(len(line))
                        
                        if ':' in line:
                            stats['has_colons'] = True
                        if '$' in line:
                            stats['has_dollar_signs'] = True
            
            if line_lengths:
                stats['avg_line_length'] = sum(line_lengths) / len(line_lengths)
            
            stats['unique_lengths'] = list(stats['unique_lengths'])
            
        except Exception as e:
            logger.warning(f"Error getting file stats: {e}")
        
        return stats
    
    def _sample_hashes(self, file_path: str, max_samples: int) -> List[str]:
        """Sample hashes from file for analysis."""
        hashes = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f):
                    if line_num >= max_samples:
                        break
                    
                    line = line.strip()
                    if line and not line.startswith('#'):
                        hashes.append(line)
            
            # If we have more samples than needed, take a representative sample
            if len(hashes) > max_samples:
                # Take first 50%, middle 25%, and last 25%
                first_part = hashes[:max_samples // 2]
                middle_start = len(hashes) // 2 - max_samples // 8
                middle_end = len(hashes) // 2 + max_samples // 8
                middle_part = hashes[middle_start:middle_end]
                last_part = hashes[-(max_samples // 4):]
                
                hashes = first_part + middle_part + last_part
            
        except Exception as e:
            logger.error(f"Error sampling hashes: {e}")
        
        return hashes
    
    def _detect_with_hashcat(self, hash_samples: List[str]) -> Dict[str, any]:
        """Use hashcat --identify to detect hash types."""
        results = {}
        
        try:
            # Create temporary file with sample hashes
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                for hash_str in hash_samples[:100]:  # Limit to 100 samples for performance
                    temp_file.write(hash_str + '\n')
                temp_file.flush()
                
                # Run hashcat --identify
                cmd = ['hashcat', '--identify', temp_file.name]
                
                try:
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        timeout=30,
                        check=False
                    )
                    
                    if result.returncode == 0:
                        # Parse hashcat identify output
                        results = self._parse_hashcat_identify_output(result.stdout)
                    else:
                        logger.warning(f"Hashcat identify failed: {result.stderr}")
                        
                except subprocess.TimeoutExpired:
                    logger.warning("Hashcat identify timed out")
                except FileNotFoundError:
                    logger.warning("Hashcat not found in PATH")
                
                # Clean up temp file
                os.unlink(temp_file.name)
                
        except Exception as e:
            logger.error(f"Error running hashcat identification: {e}")
        
        return results
    
    def _parse_hashcat_identify_output(self, output: str) -> Dict[str, any]:
        """Parse hashcat --identify output."""
        results = {}
        
        try:
            lines = output.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('hashcat'):
                    continue
                
                # Look for mode identification patterns
                # Example: "The following modes were found: 0, 100, 1400"
                if 'modes were found' in line.lower():
                    modes_part = line.split(':')[-1].strip()
                    modes = [int(m.strip()) for m in modes_part.split(',') if m.strip().isdigit()]
                    
                    for mode in modes:
                        if mode in self.mode_to_name:
                            hash_name = self.mode_to_name[mode]
                            if hash_name not in results:
                                results[hash_name] = {
                                    'mode': mode,
                                    'confidence': 1.0,  # Hashcat identification is highly reliable
                                    'count': 1,
                                    'method': 'hashcat'
                                }
                            else:
                                results[hash_name]['count'] += 1
                
                # Alternative parsing for different hashcat output formats
                elif re.match(r'^\s*\d+\s+', line):
                    parts = line.split()
                    if parts and parts[0].isdigit():
                        mode = int(parts[0])
                        if mode in self.mode_to_name:
                            hash_name = self.mode_to_name[mode]
                            results[hash_name] = {
                                'mode': mode,
                                'confidence': 1.0,
                                'count': 1,
                                'method': 'hashcat'
                            }
                            
        except Exception as e:
            logger.error(f"Error parsing hashcat output: {e}")
        
        return results
    
    def _detect_with_patterns(self, hash_samples: List[str]) -> Dict[str, any]:
        """Use pattern matching to detect hash types."""
        results = defaultdict(lambda: {'count': 0, 'confidence': 0, 'method': 'patterns'})
        
        try:
            for hash_str in hash_samples:
                detected = self.hash_analyzer._detect_hash_type(hash_str)
                
                if detected:
                    hash_type = detected['name']
                    results[hash_type]['count'] += 1
                    results[hash_type]['mode'] = detected['mode']
                    results[hash_type]['confidence'] = max(
                        results[hash_type]['confidence'], 
                        detected['confidence']
                    )
        
        except Exception as e:
            logger.error(f"Error in pattern detection: {e}")
        
        # Convert defaultdict to regular dict
        return dict(results)
    
    def _detect_with_analyzer(self, file_path: str) -> Dict[str, any]:
        """Use existing hash analyzer for additional validation."""
        results = {}
        
        try:
            analysis = self.hash_analyzer.analyze_file(file_path)
            
            for hash_type, info in analysis.get('detected_types', {}).items():
                results[hash_type] = {
                    'mode': info['mode'],
                    'confidence': info['confidence'],
                    'count': info['count'],
                    'method': 'analyzer'
                }
                
        except Exception as e:
            logger.error(f"Error in analyzer detection: {e}")
        
        return results
    
    def _combine_detection_results(self, hashcat_results: Dict, 
                                  pattern_results: Dict, 
                                  analyzer_results: Dict) -> Dict[str, any]:
        """Combine results from multiple detection methods."""
        combined = {}
        all_hash_types = set()
        
        # Collect all detected hash types
        all_hash_types.update(hashcat_results.keys())
        all_hash_types.update(pattern_results.keys())
        all_hash_types.update(analyzer_results.keys())
        
        for hash_type in all_hash_types:
            # Weight factors for different methods
            weights = {'hashcat': 1.0, 'patterns': 0.7, 'analyzer': 0.5}
            
            total_confidence = 0
            total_weight = 0
            count = 0
            mode = None
            
            # Combine results from each method
            for method_name, results in [
                ('hashcat', hashcat_results),
                ('patterns', pattern_results), 
                ('analyzer', analyzer_results)
            ]:
                if hash_type in results:
                    result = results[hash_type]
                    weight = weights[method_name]
                    
                    total_confidence += result['confidence'] * weight
                    total_weight += weight
                    count = max(count, result.get('count', 1))
                    
                    if mode is None:
                        mode = result.get('mode')
            
            # Calculate final confidence
            if total_weight > 0:
                final_confidence = total_confidence / total_weight
                
                # Only include if confidence meets threshold
                if final_confidence >= self.min_confidence:
                    combined[hash_type] = {
                        'mode': mode,
                        'confidence': round(final_confidence, 3),
                        'count': count
                    }
        
        return combined
    
    def _generate_recommendations(self, detection_results: Dict, 
                                 file_stats: Dict) -> List[Dict[str, any]]:
        """Generate recommendations based on detection results."""
        recommendations = []
        
        try:
            # Single hash type detected
            if len(detection_results) == 1:
                hash_type, info = list(detection_results.items())[0]
                recommendations.append({
                    'priority': 'high',
                    'action': 'single_mode_attack',
                    'description': f'File contains only {hash_type} hashes - use mode {info["mode"]}',
                    'hashcat_mode': info['mode'],
                    'confidence': info['confidence']
                })
            
            # Multiple hash types detected
            elif len(detection_results) > 1:
                recommendations.append({
                    'priority': 'high',
                    'action': 'split_by_type',
                    'description': 'Multiple hash types detected - consider splitting file by type',
                    'detected_types': list(detection_results.keys())
                })
                
                # Recommend starting with fastest/easiest hashes
                fast_hashes = []
                slow_hashes = []
                
                for hash_type, info in detection_results.items():
                    if hash_type in ['MD5', 'SHA1', 'NTLM', 'MySQL']:
                        fast_hashes.append((hash_type, info))
                    elif hash_type in ['bcrypt', 'scrypt', 'Argon2']:
                        slow_hashes.append((hash_type, info))
                
                if fast_hashes:
                    recommendations.append({
                        'priority': 'medium',
                        'action': 'prioritize_fast_hashes',
                        'description': 'Start with fast hash types for quick wins',
                        'fast_types': [h[0] for h in fast_hashes]
                    })
                
                if slow_hashes:
                    recommendations.append({
                        'priority': 'low',
                        'action': 'allocate_resources_slow',
                        'description': 'Slow hash types detected - allocate more time/resources',
                        'slow_types': [h[0] for h in slow_hashes]
                    })
            
            # File size recommendations
            if file_stats['file_size'] > 100 * 1024 * 1024:  # 100MB
                recommendations.append({
                    'priority': 'medium',
                    'action': 'consider_chunking',
                    'description': 'Large file detected - consider processing in chunks'
                })
            
            # Pattern-based recommendations
            if file_stats['has_colons']:
                recommendations.append({
                    'priority': 'low',
                    'action': 'check_salt_format',
                    'description': 'Colons detected - verify salt format and separation'
                })
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
        
        return recommendations
    
    def get_supported_hash_types(self) -> List[Dict[str, any]]:
        """Get list of all supported hash types."""
        supported = []
        
        for mode, name in self.mode_to_name.items():
            supported.append({
                'name': name,
                'hashcat_mode': mode,
                'description': f'Hashcat mode {mode}',
                'speed_class': self._get_speed_class(name)
            })
        
        return sorted(supported, key=lambda x: x['name'])
    
    def _get_speed_class(self, hash_type: str) -> str:
        """Get speed class for hash type."""
        fast = ['MD5', 'SHA1', 'NTLM', 'MySQL']
        medium = ['SHA256', 'SHA512', 'NetNTLMv1', 'NetNTLMv2']
        slow = ['bcrypt', 'scrypt', 'Argon2', 'PBKDF2']
        
        if hash_type in fast:
            return 'fast'
        elif hash_type in medium:
            return 'medium'
        elif hash_type in slow:
            return 'slow'
        else:
            return 'unknown'