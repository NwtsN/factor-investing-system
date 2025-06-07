#!/usr/bin/env python3
"""
Investment Analysis System (invsys)
Logging utilities for database and console output.

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

from datetime import datetime
from typing import Any
import sqlite3

class Logger:
    def __init__(self, conn: sqlite3.Connection, cursor: sqlite3.Cursor, session_id: str) -> None:
        """
        Logger for recording messages to the database and console.
        Requires a database connection, cursor, and a unique session ID.
        """
        self.conn = conn
        self.cursor = cursor
        self.session_id = session_id

    def log(self, module: str, message: str, level: str = "INFO") -> None:
        """
        Log a message to the console and database.
        """
        log_entry = (self.session_id, datetime.now(), module, level, message)
        self._print_log(log_entry)
        self._store_log(log_entry)

    def _store_log(self, log_entry: tuple[str, datetime, str, str, str]) -> None:
        """Insert log into the database."""
        try:
            self.cursor.execute("""
                INSERT INTO logs (session_id, timestamp, module, log_level, message)
                VALUES (?, ?, ?, ?, ?);
            """, log_entry)
            self.conn.commit()
        except Exception as e:
            print(f"\033[91m[Logger Error] Failed to store log: {e}\033[0m")

    def _print_log(self, log_entry: tuple[str, datetime, str, str, str]) -> None:
        """Print log message with colour coding."""
        _, timestamp, module, level, msg = log_entry
        log_str = f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] [{module}] {level}: {msg}"

        colour_map = {
            "INFO": "\033[94m",    # Blue
            "WARNING": "\033[93m", # Yellow
            "ERROR": "\033[91m",   # Red,
        }
        colour = colour_map.get(level, "")
        reset = "\033[0m" if colour else ""
        print(f"{colour}{log_str}{reset}")
