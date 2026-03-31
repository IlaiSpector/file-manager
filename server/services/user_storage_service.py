"""Storage-related operations for per-user server folders."""

from pathlib import Path

from server.utils.path_utils import get_user_storage_path


class UserStorageService:
    """Manage the server-side storage location for each user."""

    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root

    def get_user_storage_path(self, user_id: str) -> Path:
        """Return the expected storage path for a specific user."""
        return get_user_storage_path(self.storage_root, user_id)

    def create_user_storage_folder(self, user_id: str) -> Path:
        """Create and return the per-user storage folder.

        ''parents=True'' create parents foldersif missing 
        """
        # exists_ok=True means if the folder exists, don't raise an error and leave it as it is.
        self.storage_root.mkdir(parents=True, exist_ok=True)
        user_storage_path = self.get_user_storage_path(user_id)
        # exists_ok=False means if the folder exists, raise an error. useful to show bugs in folder creation
        user_storage_path.mkdir(parents=True, exist_ok=False)
        return user_storage_path
