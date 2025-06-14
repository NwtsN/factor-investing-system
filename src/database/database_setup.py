#!/usr/bin/env python3
"""
Investment Analysis System (invsys)
Database setup and management.

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

import sqlite3
import os
import uuid
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utils.logging import Logger
from config import DATA_DIR, DB_PATH, SCHEMA_PATH

class DatabaseManager:
    """
    Manages the SQLite database connection, schema setup, and initial logging.
    """
    def __init__(self):
        self.error_cache = []
        self.db_name = DB_PATH
        self.session_id = str(uuid.uuid4())  # For internal DB setup logs

        try:
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR)

            db_exists = os.path.exists(self.db_name)
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()
            
            # Initialise internal logger
            self._logger = Logger(self.conn, self.cursor, self.session_id)

            if not db_exists:
                self._execute_schema()
            else:
                self._ensure_tables_exist()

            self._clear_old_setup_logs()
            self._log("Database Initialisation", "Setup complete.", level="INFO")
        except Exception as e:
            self._log("Database Initialisation", str(e), level="ERROR")

    def _execute_schema(self):
        try:
            if not os.path.exists(SCHEMA_PATH):
                raise FileNotFoundError(f"Schema file not found at {SCHEMA_PATH}.")

            with open(SCHEMA_PATH, "r") as file:
                schema_sql = file.read()

            self.cursor.executescript(schema_sql)
            self.conn.commit()
            self._log("Database Setup", "Schema applied successfully.", level="INFO")
        except Exception as e:
            self._log("Schema Execution", str(e), level="ERROR")

    def _ensure_tables_exist(self):
        required_tables = [
            "stocks", "fundamental_data", "extracted_fundamental_data", "eps_last_5_qs",
            "price_data", "technical_indicators",
            "risk_metrics", "scoring_system", "portfolio_allocation",
            "price_prediction_results", "risk_management", "portfolio_performance",
            "logs", "raw_api_responses"
        ]

        try:
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            existing_tables = {row[0] for row in self.cursor.fetchall()}

            missing_tables = set(required_tables) - existing_tables
            if missing_tables:
                self._execute_schema()
                self._log("Schema Update", f"Created missing tables: {', '.join(missing_tables)}", level="INFO")
            else:
                self._log("Schema Check", "All required tables already exist.", level="INFO")
        except Exception as e:
            self._log("Schema Validation", str(e), level="ERROR")

    def _clear_old_setup_logs(self):
        try:
            self.cursor.execute("DELETE FROM logs WHERE module = 'Database Initialisation';")
            self.conn.commit()
            self._log("Logging Setup", "Old setup logs cleared.", level="INFO")
        except Exception as e:
            self._log("Logging Cleanup", str(e), level="ERROR")

    def _log(self, module: str, message: str, level: str = "INFO") -> None:
        """Use internal Logger instance for setup logs."""
        self._logger.log(module, message, level)

    def get_logger(self, session_id: str) -> Logger:
        """
        Returns a Logger instance using the same DB connection and provided session ID.
        """
        return Logger(self.conn, self.cursor, session_id)

    def close(self):
        try:
            if self.conn:
                self.conn.close()
                self._log("Database Manager", "Connection closed.", level="INFO")
        except Exception as e:
            self._log("Database Close", str(e), level="ERROR")

    def __enter__(self):
        """Enable use of 'with' statement."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Ensure connection is closed when exiting 'with' block."""
        self.close()


