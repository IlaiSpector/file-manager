"""Server-side configuration values."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "app.db"
STORAGE_ROOT = PROJECT_ROOT / "storage"
