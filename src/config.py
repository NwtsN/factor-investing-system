import os

# Define project root - this file is in src/, so go up one level
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
DB_PATH = os.path.join(DATA_DIR, "invsys_database.db")
SCHEMA_PATH = os.path.join(DATA_DIR, "database_schema.sql")
CONFIG_FILE_PATH = os.path.join(CONFIG_DIR, "invsys_environment.yml") 