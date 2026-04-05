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
        """List the files stored for one authenticated user.

        The user's storage directory is created if it is missing so later file
        operations keep a consistent directory layout.

        :param user_id: Authenticated user identifier.
        :returns: Three-item tuple ``(success, message, files)``. ``files`` is
            a list of metadata dictionaries when the call succeeds, otherwise an
            empty list.
        """
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
        """Choose the final stored filename for an upload request.

        The method validates the requested filename, ensures the user's storage
        directory exists, and applies the duplicate-name policy before any raw
        bytes are received.

        :param user_id: Authenticated user identifier.
        :param requested_filename: Filename requested by the client.
        :returns: Three-item tuple ``(success, message, final_filename)``.
            ``final_filename`` is ``None`` only when validation fails.
        """
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
        """Persist uploaded bytes to the user's storage directory.

        Expected validation failures are returned through the tuple result.
        Unexpected filesystem write errors are raised after any partial file is
        removed.

        :param user_id: Authenticated user identifier.
        :param final_filename: Final filename chosen during upload
            preparation.
        :param file_bytes: Raw bytes received from the client.
        :returns: Two-item tuple ``(success, message)`` describing the upload
            outcome.
        :raises OSError: If the file write fails after validation succeeds.
        """
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
        """Read one stored file for download.

        :param user_id: Authenticated user identifier.
        :param filename: Requested filename inside the user's folder.
        :returns: Three-item tuple ``(success, message, file_bytes)``.
            ``file_bytes`` is ``None`` when the file is missing or validation
            fails.
        """
        try:
            validate_windows_filename(filename)
            file_path = build_user_file_path(self.storage_root, user_id, filename)
        except (TypeError, ValueError) as exc:
            return False, str(exc), None

        if not file_path.is_file():
            return False, "File not found", None

        return True, "Ready to send file", file_path.read_bytes()

    def delete_file(self, user_id: str, filename: str) -> tuple[bool, str]:
        """Delete one stored file owned by the authenticated user.

        :param user_id: Authenticated user identifier.
        :param filename: Filename to remove from the user's folder.
        :returns: Two-item tuple ``(success, message)`` describing the delete
            outcome.
        """
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
        """Return the user's storage directory, creating it when needed.

        :param user_id: Authenticated user identifier.
        :returns: Path to the user's storage directory.
        :raises TypeError: If ``user_id`` is not a string.
        :raises ValueError: If ``user_id`` is empty after normalization.
        :raises OSError: If the storage directories cannot be created.
        """

        # exists_ok=True means if the folder exists, don't raise an error and leave it as it is.
        self.storage_root.mkdir(parents=True, exist_ok=True)
        user_storage_path = get_user_storage_path(self.storage_root, user_id)
        user_storage_path.mkdir(parents=True, exist_ok=True)
        return user_storage_path
