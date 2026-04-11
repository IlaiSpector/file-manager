"""Server-side configuration values."""

from pathlib import Path
import ssl

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "app.db"
STORAGE_ROOT = PROJECT_ROOT / "storage"
CERTS_DIR = PROJECT_ROOT / "certs"

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 41021

SERVER_BACKLOG = 5

MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024
TLS_CERT_PATH = CERTS_DIR / "server.crt"
TLS_KEY_PATH = CERTS_DIR / "server.key"
TLS_MINIMUM_VERSION = ssl.TLSVersion.TLSv1_2
