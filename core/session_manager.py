import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path


class SessionManager:
    """Manage session persistence and recovery."""
    
    def __init__(self, session_dir: str = ".hashwrap_sessions"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(exist_ok=True)
        self.current_session = None
        self.session_file = None
        
    def create_session(self, hash_file: str, config: Dict[str, Any]) -> str:
        """Create a new session."""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_path = self.session_dir / f"session_{session_id}"
        session_path.mkdir(exist_ok=True)
        
        session_data = {
            'id': session_id,
            'hash_file': hash_file,
            'config': config,
            'start_time': datetime.now().isoformat(),
            'status': 'active',
            'completed_attacks': [],
            'pending_attacks': [],
            'statistics': {
                'total_hashes': 0,
                'cracked_hashes': 0,
                'time_elapsed': 0
            }
        }
        
        self.current_session = session_data
        self.session_file = session_path / "session.json"
        self._save_session()
        
        return session_id
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load an existing session."""
        session_path = self.session_dir / f"session_{session_id}"
        session_file = session_path / "session.json"
        
        if session_file.exists():
            with open(session_file, 'r') as f:
                self.current_session = json.load(f)
                self.session_file = session_file
                return self.current_session
        return None
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions."""
        sessions = []
        
        for session_dir in self.session_dir.iterdir():
            if session_dir.is_dir() and session_dir.name.startswith("session_"):
                session_file = session_dir / "session.json"
                if session_file.exists():
                    with open(session_file, 'r') as f:
                        session_data = json.load(f)
                        sessions.append({
                            'id': session_data['id'],
                            'start_time': session_data['start_time'],
                            'status': session_data['status'],
                            'progress': f"{session_data['statistics']['cracked_hashes']}/{session_data['statistics']['total_hashes']}"
                        })
        
        return sorted(sessions, key=lambda x: x['start_time'], reverse=True)
    
    def update_session(self, updates: Dict[str, Any]):
        """Update current session data."""
        if not self.current_session:
            return
            
        # Update nested dictionaries properly
        for key, value in updates.items():
            if key in self.current_session and isinstance(self.current_session[key], dict):
                self.current_session[key].update(value)
            else:
                self.current_session[key] = value
        
        self._save_session()
    
    def save_attack_state(self, attack_name: str, state: Dict[str, Any]):
        """Save the state of a specific attack."""
        if not self.current_session:
            return
            
        # Sanitize attack name for filename
        safe_name = "".join(c for c in attack_name if c.isalnum() or c in ('_', '-'))[:50]
        state_file = Path(self.session_file).parent / f"attack_{safe_name}.json"
        
        # Convert datetime objects to ISO format for JSON serialization
        serializable_state = self._make_json_serializable(state)
        
        with open(state_file, 'w') as f:
            json.dump(serializable_state, f, indent=2)
    
    def load_attack_state(self, attack_name: str) -> Optional[Dict[str, Any]]:
        """Load the state of a specific attack."""
        if not self.session_file:
            return None
            
        # Sanitize attack name for filename
        safe_name = "".join(c for c in attack_name if c.isalnum() or c in ('_', '-'))[:50]
        state_file = Path(self.session_file).parent / f"attack_{safe_name}.json"
        
        if state_file.exists():
            with open(state_file, 'r') as f:
                return json.load(f)
        return None
    
    def mark_attack_completed(self, attack_name: str, results: Dict[str, Any]):
        """Mark an attack as completed."""
        if not self.current_session:
            return
            
        completed_attack = {
            'name': attack_name,
            'completed_at': datetime.now().isoformat(),
            'results': results
        }
        
        self.current_session['completed_attacks'].append(completed_attack)
        
        # Remove from pending if exists
        self.current_session['pending_attacks'] = [
            a for a in self.current_session['pending_attacks'] 
            if a.get('name') != attack_name
        ]
        
        self._save_session()
    
    def get_resume_point(self) -> Optional[Dict[str, Any]]:
        """Get the point where to resume the session."""
        if not self.current_session:
            return None
            
        # Find the last incomplete attack
        if self.current_session['pending_attacks']:
            return {
                'next_attack': self.current_session['pending_attacks'][0],
                'completed_count': len(self.current_session['completed_attacks']),
                'last_statistics': self.current_session['statistics']
            }
        
        return None
    
    def close_session(self, final_stats: Dict[str, Any]):
        """Close the current session."""
        if not self.current_session:
            return
            
        self.current_session['status'] = 'completed'
        self.current_session['end_time'] = datetime.now().isoformat()
        self.current_session['final_statistics'] = final_stats
        
        # Calculate total time
        start_time = datetime.fromisoformat(self.current_session['start_time'])
        end_time = datetime.now()
        self.current_session['total_duration'] = str(end_time - start_time)
        
        self._save_session()
    
    def _save_session(self):
        """Save current session to file."""
        if self.current_session and self.session_file:
            with open(self.session_file, 'w') as f:
                json.dump(self.current_session, f, indent=2)
    
    def export_session_report(self, session_id: str, output_file: str):
        """Export a detailed session report."""
        session = self.load_session(session_id) if session_id != self.current_session.get('id') else self.current_session
        
        if not session:
            return
        
        report = f"""# Hashwrap Session Report
        
## Session Information
- **Session ID**: {session['id']}
- **Start Time**: {session['start_time']}
- **End Time**: {session.get('end_time', 'In Progress')}
- **Status**: {session['status']}
- **Total Duration**: {session.get('total_duration', 'N/A')}

## Hash Statistics
- **Total Hashes**: {session['statistics']['total_hashes']}
- **Cracked Hashes**: {session['statistics']['cracked_hashes']}
- **Success Rate**: {session['statistics']['cracked_hashes'] / session['statistics']['total_hashes'] * 100:.2f}%

## Attack Summary
### Completed Attacks ({len(session['completed_attacks'])})
"""
        
        for attack in session['completed_attacks']:
            report += f"\n#### {attack['name']}\n"
            report += f"- Completed: {attack['completed_at']}\n"
            if 'results' in attack:
                report += f"- Cracked: {attack['results'].get('cracked_count', 0)}\n"
                report += f"- Duration: {attack['results'].get('duration', 'N/A')}\n"
        
        if session['pending_attacks']:
            report += f"\n### Pending Attacks ({len(session['pending_attacks'])})\n"
            for attack in session['pending_attacks']:
                report += f"- {attack.get('name', 'Unknown')}\n"
        
        with open(output_file, 'w') as f:
            f.write(report)
    
    def _make_json_serializable(self, obj: Any) -> Any:
        """Convert non-JSON serializable objects for storage."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        else:
            return obj