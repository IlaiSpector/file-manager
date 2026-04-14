"""Listening socket setup and client-thread creation for the server."""


from pathlib import Path
import socket
import ssl
import threading

from server.config import (
    CLIENT_SOCKET_TIMEOUT_SECONDS,
    SERVER_BACKLOG,
    SERVER_HOST,
    SERVER_PORT,
    TLS_CERT_PATH,
    TLS_KEY_PATH,
    TLS_MINIMUM_VERSION,
)
from server.network.client_handler import ClientHandler
from server.services.auth_service import AuthService
from server.services.file_service import FileService


class ServerSocket:
    """Accept incoming clients and hand each one to its own handler thread."""

    def __init__(
        self,
        auth_service: AuthService,
        file_service: FileService,
        host: str = SERVER_HOST,
        port: int = SERVER_PORT,
        backlog: int = SERVER_BACKLOG,
        client_socket_timeout: float | None = CLIENT_SOCKET_TIMEOUT_SECONDS,
        tls_cert_path: Path | str = TLS_CERT_PATH,
        tls_key_path: Path | str = TLS_KEY_PATH,
    ) -> None:
        self.auth_service = auth_service
        self.file_service = file_service
        self.host = host
        self.port = port
        # amount of clients that can wait in queue before accepting.
        self.backlog = backlog
        self.client_socket_timeout = client_socket_timeout
        self.tls_cert_path = Path(tls_cert_path)
        self.tls_key_path = Path(tls_key_path)
        self.listening_socket: socket.socket | None = None
        self._tls_context: ssl.SSLContext | None = None

    def serve_forever(self) -> None:
        """Create the listening socket and accept clients indefinitely.

        Each accepted client is handed off to a dedicated daemon thread so the
        main server thread can continue accepting new connections. Closing the
        listening socket causes the loop to exit cleanly; other socket errors
        are re-raised.
        """
        self._tls_context = self._create_tls_context()
        self.listening_socket = self._create_listening_socket()
        self.port = self.listening_socket.getsockname()[1]
        print(f"running on ({self.host}, {self.port})")
        while True:
            try:
                client_socket, client_address = self.listening_socket.accept()
                print(f"recieved client {client_address}")
            except OSError:
                # checks if the listening socket has been closed. if it, exits cleanly. if it not raises the error.
                if self.listening_socket.fileno() == -1:
                    break
                raise

            self._start_client_thread(client_socket, client_address)

    def _create_listening_socket(self) -> socket.socket:
        """Create, bind, and start listening on the server socket.

        :returns: Listening TCP socket configured with ``SO_REUSEADDR``.
        """

        # AF_INET - uses IPv4 addresses
        # SOCK_STREAM - uses TCP

        listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


        # setsockopt() changes a setting on this socket.
        # SOL_SOCKET is the setting category,
        # SO_REUSEADDR tells the OS to allow reusing the same address/port quickly after restart,
        # and 1 means this option is enabled.

        listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listening_socket.bind((self.host, self.port))
        listening_socket.listen(self.backlog)
        return listening_socket

    def _create_tls_context(self) -> ssl.SSLContext:
        """Create the fixed server TLS context used for incoming clients."""
        tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls_context.minimum_version = TLS_MINIMUM_VERSION
        tls_context.load_cert_chain(
            certfile=str(self.tls_cert_path),
            keyfile=str(self.tls_key_path),
        )
        return tls_context

    def _start_client_thread(
        self,
        client_socket: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        """Start a daemon thread for one accepted client connection.

        :param client_socket: Accepted client socket.
        :param client_address: Remote client address reported by ``accept``.
        """
        client_thread = threading.Thread(
            target=self._run_client_handler,
            args=(client_socket, client_address),
            daemon=True, # means these threads run on the backround. if the non-daemon threads (the main thread in this case) will exit,
                         # the program can exit without waiting for these threads to exit 
        )
        client_thread.start()

    def _run_client_handler(
        self,
        client_socket: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        """Instantiate and run the handler for one client connection.

        :param client_socket: Accepted client socket.
        :param client_address: Remote client address reported by ``accept``.
        """
        assert self._tls_context is not None
        if self.client_socket_timeout is not None:
            client_socket.settimeout(self.client_socket_timeout)

        try:
            tls_client_socket = self._tls_context.wrap_socket(
                client_socket,
                server_side=True,
            )
            # makes sure that tls_client_socket has timeout as well
            if self.client_socket_timeout is not None:
                tls_client_socket.settimeout(self.client_socket_timeout)
        except (ssl.SSLError, OSError) as exc:
            print(f"failed tls handshake with {client_address}: {exc}")
            client_socket.close()
            return

        handler = ClientHandler(
            client_socket=tls_client_socket,
            auth_service=self.auth_service,
            file_service=self.file_service,
            client_address=client_address,
        )
        handler.handle_client()
