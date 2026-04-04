"""Helpers for server-side file storage behavior."""

from pathlib import Path

def build_file_metadata(file_path: Path) -> dict[str, int | str]:
    """Build the GUI-facing metadata for one stored file."""
    return {
        "filename": file_path.name,
        "size": file_path.stat().st_size,
        "extension": file_path.suffix,
    }


def choose_available_filename(user_storage_path: Path, requested_filename: str) -> str:
    """Return the first non-conflicting filename using the project's duplicate rule."""
    candidate_path = user_storage_path / requested_filename
    if not candidate_path.exists():
        return requested_filename

    original_path = Path(requested_filename)
    stem = original_path.stem
    suffix = original_path.suffix
    duplicate_index = 2

    while True:
        candidate_name = f"{stem}({duplicate_index}){suffix}"
        if not (user_storage_path / candidate_name).exists():
            return candidate_name
        duplicate_index += 1
