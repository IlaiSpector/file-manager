"""Business logic for per-user file storage operations."""

from pathlib import Path

from server.utils.file_utils import (
    build_file_metadata,
    choose_available_filename,
)
from server.utils.path_utils import build_user_file_path, get_user_storage_path
from server.utils.validators import validate_windows_filename


class FileService:
    """Handle file listing, upload preparation, reads, and deletes."""

    def __init__(self, storage_root: Path) -> None:
        self.storage_root = Path(storage_root)

    def list_files(self, user_id: str) -> tuple[bool, str, list[dict[str, int | str]]]:
        """Return the current user's stored file metadata."""
        try:
            # creates user storage path, in case it was deleted.
            user_storage_path = self._ensure_user_storage_path(user_id)
        except (TypeError, ValueError) as exc:
            return False, str(exc), []

        files = [
            build_file_metadata(file_path)
            for file_path in sorted(user_storage_path.iterdir(), key=lambda path: path.name.lower())
            if file_path.is_file()
        ]
        return True, "Files retrieved successfully", files

    def prepare_upload(
        self,
        user_id: str,
        requested_filename: str,
    ) -> tuple[bool, str, str | None]:
        """Choose the final filename for a new upload."""
        try:
            safe_filename = validate_windows_filename(requested_filename)
            user_storage_path = self._ensure_user_storage_path(user_id)
            build_user_file_path(self.storage_root, user_id, safe_filename)
        except (TypeError, ValueError) as exc:
            return False, str(exc), None

        final_filename = choose_available_filename(user_storage_path, safe_filename)
        return True, "Ready to receive file", final_filename

    def save_file_bytes(
        self,
        user_id: str,
        final_filename: str,
        file_bytes: bytes,
    ) -> tuple[bool, str]:
        """Persist one uploaded file and clean up files on failure."""
        if not isinstance(file_bytes, bytes):
            return False, "file_bytes must be bytes."

        try:
            validate_windows_filename(final_filename)
            user_storage_path = self._ensure_user_storage_path(user_id)
            final_path = build_user_file_path(self.storage_root, user_id, final_filename)
        except (TypeError, ValueError) as exc:
            return False, str(exc)

        try:
            with final_path.open("wb") as file_object:
                file_object.write(file_bytes)
        except Exception:
            if final_path.exists():
                final_path.unlink()
            raise

        return True, "File uploaded successfully"

    def get_file_bytes(self, user_id: str, filename: str) -> tuple[bool, str, bytes | None]:
        """Return the bytes for one stored file."""
        try:
            validate_windows_filename(filename)
            file_path = build_user_file_path(self.storage_root, user_id, filename)
        except (TypeError, ValueError) as exc:
            return False, str(exc), None

        if not file_path.is_file():
            return False, "File not found", None

        return True, "Ready to send file", file_path.read_bytes()

    def delete_file(self, user_id: str, filename: str) -> tuple[bool, str]:
        """Delete one stored file from the user's folder."""
        try:
            validate_windows_filename(filename)
            file_path = build_user_file_path(self.storage_root, user_id, filename)
        except (TypeError, ValueError) as exc:
            return False, str(exc)

        if not file_path.is_file():
            return False, "File not found"

        file_path.unlink()
        return True, "File deleted successfully"

    def _ensure_user_storage_path(self, user_id: str) -> Path:
        """Create the user's storage folder if it is missing."""

        # exists_ok=True means if the folder exists, don't raise an error and leave it as it is.
        self.storage_root.mkdir(parents=True, exist_ok=True)
        user_storage_path = get_user_storage_path(self.storage_root, user_id)
        user_storage_path.mkdir(parents=True, exist_ok=True)
        return user_storage_path
