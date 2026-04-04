"""Helpers for building server-side storage paths safely."""

from pathlib import Path

from server.utils.validators import require_non_empty_text


def get_user_storage_path(storage_root: Path, user_id: str) -> Path:
    """Return the storage path for a specific user id."""
    normalized_user_id = require_non_empty_text(user_id, "user_id")
    return Path(storage_root) / f"user_{normalized_user_id}"


def build_user_file_path(storage_root: Path, user_id: str, filename: str) -> Path:
    """Return a safe path inside the user's storage folder for one filename."""
    if not isinstance(filename, str):
        raise TypeError("filename must be a string.")
    if not filename:
        raise ValueError("filename cannot be empty.")
    if "/" in filename or "\\" in filename:
        raise ValueError("filename must not contain path separators.")

    user_storage_path = get_user_storage_path(storage_root, user_id)
    # resolve makes sure that .. is treated normalized. for example f1/f2/../c.txt => f1/c.txt. needed to be done to avoid using file  name to escape user folder, for security reasons.
    # strict=False, the path doesn't have to exist yet
    resolved_user_storage_path = user_storage_path.resolve(strict=False)
    candidate_path = (user_storage_path / filename).resolve(strict=False)

    if candidate_path.parent != resolved_user_storage_path:
        raise ValueError("filename escapes the user storage folder.")

    return candidate_path
