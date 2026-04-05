"""Helpers for server-side file storage behavior."""

from pathlib import Path

def build_file_metadata(file_path: Path) -> dict[str, int | str]:
    """Build the GUI-facing metadata dictionary for one stored file.

    :param file_path: Stored file to describe.
    :returns: Dictionary containing the filename, byte size, and extension.
    """
    return {
        "filename": file_path.name,
        "size": file_path.stat().st_size,
        "extension": file_path.suffix,
    }


def choose_available_filename(user_storage_path: Path, requested_filename: str) -> str:
    """Choose the first non-conflicting filename for a user upload.

    The duplicate rule follows the project convention of appending
    ``(2)``, ``(3)``, and so on before the original extension.

    :param user_storage_path: Directory that holds the user's files.
    :param requested_filename: Filename originally requested by the client.
    :returns: The requested filename or the first available duplicate-safe
        variant.
    """
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
