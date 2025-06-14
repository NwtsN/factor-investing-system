#!/usr/bin/env python3
"""
Investment Analysis System (invsys)
Program Timer - Simple timeout functionality for limiting program execution time.

Copyright (C) 2025 Neil Donald Watson

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import sys
import threading
import time
from typing import Optional, Union


class Timeout:
    """
    Simple timeout class to limit program execution time.
    
    Usage:
        # As context manager
        with Timeout(minutes=30):
            # Your program logic here
            pass
            
        # Manual start/stop
        timeout = Timeout(minutes=15)
        timeout.start()
        # Your program logic here
        timeout.stop()
    """
    
    def __init__(self, minutes: Union[int, float], message: Optional[str] = None) -> None:
        """
        Initialize timeout.
        
        Args:
            minutes: Number of minutes before timeout (must be positive)
            message: Custom message to display on timeout
            
        Raises:
            ValueError: If minutes is not positive
        """
        if minutes <= 0:
            raise ValueError("Timeout minutes must be a positive number")
            
        self.minutes = minutes
        self.seconds = minutes * 60
        self.message = message or f"Program timed out after {minutes} minutes"
        self.timer: Optional[threading.Timer] = None
        self.active = False
        self.start_time: Optional[float] = None
        
    def _timeout_handler(self) -> None:
        """Handle timeout by printing message and exiting."""
        print(f"\n[TIMEOUT] {self.message}")
        print(f"[INFO] Program execution limited to {self.minutes} minutes")
        sys.exit(0)
        
    def start(self) -> None:
        """Start the timeout timer."""
        if self.active:
            return
            
        self.start_time = time.time()
        self.timer = threading.Timer(self.seconds, self._timeout_handler)
        self.timer.daemon = True  # Dies with main thread
        self.timer.start()
        self.active = True
        print(f"[INFO] Program timeout set to {self.minutes} minutes")
        
    def stop(self) -> None:
        """Stop the timeout timer."""
        if self.timer and self.active:
            self.timer.cancel()
            self.active = False
            self.start_time = None
            print(f"[INFO] Program timeout cancelled")
            
    def __enter__(self) -> "Timeout":
        """Context manager entry."""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Context manager exit."""
        self.stop()
        
    def time_remaining(self) -> Optional[float]:
        """
        Get time remaining in seconds.
        
        Returns:
            Remaining time in seconds, or None if timer is not active
        """
        if not self.active or self.start_time is None:
            return None
            
        elapsed = time.time() - self.start_time
        remaining = self.seconds - elapsed
        return max(0.0, remaining) 