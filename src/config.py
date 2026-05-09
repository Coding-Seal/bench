# src/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "postgresql" / "config"
CONFIG_FILENAME = os.getenv("PG_CONFIG_FILE", "performance.conf")
CONFIG_PATH = CONFIG_DIR / CONFIG_FILENAME
BACKUP_PATH = CONFIG_DIR / f"{CONFIG_FILENAME}.bak"

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
PG_DB = os.getenv("POSTGRES_DB", "postgres")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_SERVICE = "postgres"

# ✅ Parameters that REQUIRE a full PostgreSQL restart
RESTART_REQUIRED_PARAMS = {
    "shared_buffers", "max_connections", "huge_pages", "wal_level",
    "max_worker_processes", "max_parallel_workers", "max_parallel_workers_per_gather",
    "max_parallel_maintenance_workers"
}

# 🗄️ Optuna Storage Configuration
STUDY_NAME = os.getenv("OPTUNA_STUDY_NAME", "pg_config_optimization")
STORAGE_DB = PROJECT_ROOT / "optuna_study.db"
STORAGE_URL = f"sqlite:///{STORAGE_DB.resolve()}"