"""Server entrypoint."""

from server.config import STORAGE_ROOT
from server.database.db_manager import DatabaseManager
from server.network.server_socket import ServerSocket
from server.services.auth_service import AuthService
from server.services.file_service import FileService


def main() -> None:
    """Initialize server dependencies and start the listening loop.

    The function wires together the database manager, authentication service,
    file service, and listening socket before handing control to the server's
    forever-running accept loop.
    """
    db_manager = DatabaseManager()
    db_manager.initialize_database()

    auth_service = AuthService(db_manager=db_manager, storage_root=STORAGE_ROOT)
    file_service = FileService(storage_root=STORAGE_ROOT)
    server_socket = ServerSocket(auth_service=auth_service, file_service=file_service)
    server_socket.serve_forever()


if __name__ == "__main__":
    main()
