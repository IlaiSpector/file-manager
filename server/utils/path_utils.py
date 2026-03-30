"""Helpers for building server-side storage paths safely."""

from pathlib import Path


def get_user_storage_path(storage_root: Path, user_id: str) -> Path:
    """Return the storage path for a specific user id."""
    if not isinstance(user_id, str):
        raise TypeError("user_id must be a string.")
    if not user_id.strip():
        raise ValueError("user_id cannot be empty.")
    return storage_root / f"user_{user_id}"
