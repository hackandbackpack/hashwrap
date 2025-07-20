import sys
import os
from datetime import datetime
from typing import Optional


class Display:
    """Handle all display/output formatting."""
    
    COLORS = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'orange': '\033[38;5;208m',
        'reset': '\033[0m',
        'bold': '\033[1m',
        'underline': '\033[4m'
    }
    
    def __init__(self, use_color: bool = True):
        self.use_color = use_color and self._supports_color()
    
    def _supports_color(self) -> bool:
        """Check if terminal supports colors."""
        # Windows
        if sys.platform == 'win32':
            return os.environ.get('ANSICON') is not None or 'WT_SESSION' in os.environ
        # Unix/Linux/Mac
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    
    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if supported."""
        if not self.use_color or color not in self.COLORS:
            return text
        return f"{self.COLORS[color]}{text}{self.COLORS['reset']}"
    
    def header(self, text: str):
        """Display a header."""
        print("\n" + "=" * 60)
        print(self._colorize(text.center(60), 'bold'))
        print("=" * 60)
    
    def section(self, text: str):
        """Display a section header."""
        print(f"\n{self._colorize('>> ' + text, 'cyan')}")
        print(self._colorize("-" * (len(text) + 3), 'cyan'))
    
    def info(self, text: str):
        """Display info message."""
        print(f"  {text}")
    
    def success(self, text: str):
        """Display success message."""
        print(self._colorize(f"[OK] {text}", 'green'))
    
    def warning(self, text: str):
        """Display warning message."""
        print(self._colorize(f"[!] {text}", 'yellow'))
    
    def error(self, text: str):
        """Display error message."""
        print(self._colorize(f"[X] {text}", 'red'))
    
    def debug(self, text: str):
        """Display debug message."""
        print(self._colorize(f"[DEBUG] {text}", 'magenta'))
    
    def colored(self, text: str, color: str):
        """Display colored text."""
        print(self._colorize(text, color))
    
    def attack_header(self, text: str):
        """Display attack header."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n{self._colorize('=' * 60, 'blue')}")
        print(f"{self._colorize(f'[{timestamp}]', 'blue')} {self._colorize(text, 'bold')}")
        print(f"{self._colorize('=' * 60, 'blue')}")
    
    def cracked_hash(self, hash_val: str, plaintext: str):
        """Display a cracked hash."""
        # Truncate long hashes for display
        display_hash = hash_val[:32] + "..." if len(hash_val) > 32 else hash_val
        print(self._colorize(f"  [CRACKED] {display_hash} -> {plaintext}", 'orange'))
    
    def progress_bar(self, current: int, total: int, prefix: str = "", width: int = 40):
        """Display a progress bar."""
        if total == 0:
            return
            
        percent = current / total
        filled = int(width * percent)
        bar = "#" * filled + "-" * (width - filled)
        
        # Color based on progress
        if percent < 0.33:
            color = 'red'
        elif percent < 0.66:
            color = 'yellow'
        else:
            color = 'green'
        
        bar_display = self._colorize(bar, color)
        print(f"\r{prefix} [{bar_display}] {percent:.1%}", end="", flush=True)
        
        if current == total:
            print()  # New line when complete
    
    def table(self, headers: list, rows: list):
        """Display a formatted table."""
        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))
        
        # Print header
        header_str = " | ".join(h.ljust(w) for h, w in zip(headers, widths))
        print(self._colorize(header_str, 'bold'))
        print(self._colorize("-" * len(header_str), 'white'))
        
        # Print rows
        for row in rows:
            row_str = " | ".join(str(cell).ljust(w) for cell, w in zip(row, widths))
            print(row_str)
    
    def clear_line(self):
        """Clear the current line."""
        print('\r' + ' ' * 80 + '\r', end='', flush=True)