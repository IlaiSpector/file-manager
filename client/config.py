"""Client-side configuration values."""

from pathlib import Path

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 41021

SOCKET_TIMEOUT_SECONDS = 30.0


def get_default_downloads_path() -> Path:
    """Return the default operating-system downloads directory.

    The folder is intentionally not created here. If it is missing, the
    download operation should fail with a normal filesystem error.

    :returns: Default path to the current user's Downloads directory.
    """
    return Path.home() / "Downloads"
