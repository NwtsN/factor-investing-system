#!/usr/bin/env python3
"""
Investment Analysis System (invsys)
Configuration constants and paths.

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

import os

# Define project root - this file is in src/, so go up one level
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
DB_PATH = os.path.join(DATA_DIR, "invsys_database.db")
SCHEMA_PATH = os.path.join(DATA_DIR, "database_schema.sql")
CONFIG_FILE_PATH = os.path.join(CONFIG_DIR, "invsys_environment.yml") 