"""Blocking client networking for the file manager application."""

from dataclasses import dataclass
from pathlib import Path
import socket
import ssl
import uuid
from typing import Any

from client.config import (
    SERVER_HOST,
    SERVER_PORT,
    SOCKET_TIMEOUT_SECONDS,
    TLS_MINIMUM_VERSION,
    get_default_downloads_path,
)
from shared.constants import (
    ACTION_DELETE_FILE,
    ACTION_DOWNLOAD_FILE,
    ACTION_LIST_FILES,
    ACTION_LOGIN,
    ACTION_LOGOUT,
    ACTION_SIGNUP,
    ACTION_UPLOAD_COMPLETE,
    ACTION_UPLOAD_FILE,
    FIELD_ACTION,
    FIELD_DATA,
    FIELD_MESSAGE,
    FIELD_REQUEST_ID,
    FIELD_STATUS,
    STATUS_ERROR,
    STATUS_READY,
    STATUS_SUCCESS,
)
from shared.message_helpers import build_request
from shared.protocol import (
    decode_message,
    encode_message,
    recv_exact,
    recv_message_bytes,
    send_all,
)


@dataclass
class Result:
    """Simple result returned by client network operations.

    :param success: Whether the operation succeeded.
    :param message: Human-readable message for the caller.
    """

    success: bool
    message: str


class ClientSocket:
    """Own one blocking socket connection to the file manager server."""

    def __init__(
        self,
        host: str = SERVER_HOST,
        port: int = SERVER_PORT,
        socket_timeout: float | None = SOCKET_TIMEOUT_SECONDS,
        downloads_path: Path | str | None = None,
    ) -> None:
        """Initialize a disconnected client socket wrapper.

        :param host: Server host or IP address.
        :param port: Server TCP port.
        :param socket_timeout: Timeout used after the connection is open.
        :param downloads_path: Optional downloads directory override.
        """
        self.host = host
        self.port = port
        self.socket_timeout = socket_timeout
        self.downloads_path = (
            Path(downloads_path)
            if downloads_path is not None
            else get_default_downloads_path()
        )
        self._socket: socket.socket | None = None

    def connect(self) -> None:
        """Open the TCP connection to the configured server.

        :raises ConnectionError: If a socket is already connected or if the
            connection attempt fails.
        """
        if self.is_connected():
            raise ConnectionError("Client is already connected.")

        raw_socket: socket.socket | None = None
        try:
            raw_socket = socket.create_connection(
                (self.host, self.port),
                timeout=self.socket_timeout,
            )
            raw_socket.settimeout(self.socket_timeout)
            client_socket = self._create_tls_context().wrap_socket(
                raw_socket,
                server_hostname=self.host,
            )
            client_socket.settimeout(self.socket_timeout)
        except ssl.SSLError as exc:
            if raw_socket is not None:
                raw_socket.close()
            raise ConnectionError("Failed to establish a TLS connection to the server.") from exc
        except OSError as exc:
            if raw_socket is not None:
                raw_socket.close()
            raise ConnectionError("Failed to connect to the server.") from exc

        self._socket = client_socket

    def close(self) -> None:
        """Close the current socket connection if one is open."""
        if self._socket is None:
            return

        self._socket.close()
        self._socket = None

    def is_connected(self) -> bool:
        """Return whether this wrapper currently owns an open socket.

        :returns: ``True`` when a socket object is present and not locally
            closed, otherwise ``False``.
        """
        # if fileno == -1 socket has been closed.
        return self._socket is not None and self._socket.fileno() != -1

    def send_json_message(self, message: dict[str, Any]) -> None:
        """Send one length-prefixed JSON message to the server.

        :param message: Protocol message dictionary to send.
        :raises ConnectionError: If the client is disconnected or sending
            fails.
        """
        try:
            send_all(self._socket, encode_message(message))
        except OSError as exc:
            raise ConnectionError("Failed to send message to the server.") from exc

    def receive_json_message(self) -> dict[str, Any]:
        """Receive one length-prefixed JSON message from the server.

        :returns: Decoded protocol response dictionary.
        :raises ConnectionError: If the client is disconnected or the receive
            fails because of a broken connection.
        :raises ValueError: If the received payload is not a valid protocol
            JSON object.
        """
        try:
            return decode_message(recv_message_bytes(self._socket))
        except ConnectionError:
            raise
        except OSError as exc:
            raise ConnectionError("Failed to receive message from the server.") from exc
        except ValueError as exc:
            raise ValueError("Received malformed JSON response from the server.") from exc

    def send_raw_bytes(self, payload: bytes) -> None:
        """Send a raw binary payload to the server.

        :param payload: Bytes to send after an upload ``ready`` response.
        :raises ConnectionError: If the client is disconnected or sending
            fails.
        """
        try:
            send_all(self._socket, payload)
        except OSError as exc:
            raise ConnectionError("Failed to send file bytes to the server.") from exc

    def receive_raw_bytes(self, size: int) -> bytes:
        """Receive exactly ``size`` raw bytes from the server.

        :param size: Number of raw bytes expected.
        :returns: Raw bytes received from the server.
        :raises ConnectionError: If the client is disconnected or the raw
            transfer is interrupted.
        """
        try:
            return recv_exact(self._socket, size)
        except ConnectionError:
            raise
        except OSError as exc:
            raise ConnectionError("Failed to receive file bytes from the server.") from exc

    def signup(self, username: str, email: str, password: str) -> Result:
        """Send a signup request.

        Successful signup also authenticates the current server connection.

        :param username: Requested unique username.
        :param email: Requested unique email address.
        :param password: Plain-text password entered by the user.
        :returns: Operation result using the server's message.
        """
        return self._send_simple_action(
            ACTION_SIGNUP,
            {"username": username, "email": email, "password": password},
        )

    def login(self, email: str, password: str) -> Result:
        """Send a login request.

        :param email: Email address used for login.
        :param password: Plain-text password entered by the user.
        :returns: Operation result using the server's message.
        """
        return self._send_simple_action(
            ACTION_LOGIN,
            {"email": email, "password": password},
        )

    def logout(self) -> Result:
        """Send a logout request while keeping the socket open.

        :returns: Operation result using the server's message.
        """
        return self._send_simple_action(ACTION_LOGOUT, {})

    def list_files(self) -> tuple[Result, list[dict[str, int | str]] | None]:
        """Request the authenticated user's file list.

        :returns: Tuple containing the operation result and the server file
            list on success, otherwise ``None``.
        """
        request_id = self._send_request(ACTION_LIST_FILES, {})
        response = self._receive_expected_response(
            ACTION_LIST_FILES,
            request_id,
        )
        result = self._result_from_response(response)
        if not result.success:
            return result, None

        files = response[FIELD_DATA].get("files")
        if not isinstance(files, list):
            raise ValueError("LIST_FILES response is missing the files list.")
        return result, files

    def upload_file(self, source_path: Path | str) -> Result:
        """Upload one local file to the authenticated user's server storage.

        The whole local file is read into memory and sent as one raw byte
        payload after the server's ``ready`` response.

        :param source_path: Local file path to upload.
        :returns: Operation result using the server's final upload message.
        :raises FileNotFoundError: If ``source_path`` does not exist.
        :raises IsADirectoryError: If ``source_path`` is not a file.
        """
        source = Path(source_path)
        self._require_upload_source(source)
        file_bytes = source.read_bytes()

        request_id = self._send_request(
            ACTION_UPLOAD_FILE,
            {"filename": source.name, "filesize": len(file_bytes)},
        )
        ready_response = self._receive_expected_response(
            ACTION_UPLOAD_FILE,
            request_id,
        )
        ready_result = self._result_from_response(ready_response)
        if not ready_result.success:
            return ready_result

        self.send_raw_bytes(file_bytes)
        complete_response = self._receive_expected_response(
            ACTION_UPLOAD_COMPLETE,
            request_id,
        )
        return self._result_from_response(complete_response)

    def download_file(self, filename: str) -> Result:
        """Download one server-side file into the configured Downloads folder.

        The whole file is received into memory and then written directly to the
        final duplicate-safe destination path. No temporary ``.part`` file is
        used.

        :param filename: Server-side filename to download.
        :returns: Operation result using a client success message or the
            server's error message.
        :raises FileNotFoundError: If the Downloads folder does not exist.
        :raises NotADirectoryError: If the Downloads path is not a directory.
        :raises OSError: If writing the local file fails.
        """
        self._require_downloads_directory()
        request_id = self._send_request(ACTION_DOWNLOAD_FILE, {"filename": filename})
        ready_response = self._receive_expected_response(
            ACTION_DOWNLOAD_FILE,
            request_id,
        )
        ready_result = self._result_from_response(ready_response)
        if not ready_result.success:
            return ready_result

        response_data = ready_response[FIELD_DATA]
        response_filename = response_data["filename"]
        filesize = response_data["filesize"]

        target_path = self._choose_available_download_path(response_filename)
        file_bytes = self.receive_raw_bytes(filesize)
        try:
            target_path.write_bytes(file_bytes)
        except OSError:
            if target_path.exists():
                target_path.unlink()
            raise

        return Result(True, "File downloaded successfully")

    def delete_file(self, filename: str) -> Result:
        """Send a delete request for one server-side file.

        :param filename: Server-side filename to delete.
        :returns: Operation result using the server's message.
        """
        return self._send_simple_action(ACTION_DELETE_FILE, {"filename": filename})

    def _send_simple_action(self, action: str, data: dict[str, Any]) -> Result:
        """Send one JSON request and receive one success/error response.

        :param action: Protocol action name to send.
        :param data: Request payload dictionary.
        :returns: Operation result using the server's message.
        """
        request_id = self._send_request(action, data)
        response = self._receive_expected_response(
            action,
            request_id,
        )
        return self._result_from_response(response)

    def _send_request(self, action: str, data: dict[str, Any]) -> str:
        """Build and send one protocol request.

        :param action: Protocol action name to send.
        :param data: Request payload dictionary.
        :returns: Generated request identifier.
        """
        request_id = self._generate_request_id()
        self.send_json_message(build_request(action, request_id, data))
        return request_id

    def _receive_expected_response(
        self,
        expected_action: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Receive and validate one response envelope.

        :param expected_action: Action expected in the response.
        :param request_id: Request identifier expected in the response.
        :returns: Validated response dictionary.
        :raises ValueError: If the response identity is invalid.
        """
        response = self.receive_json_message()

        if response[FIELD_ACTION] != expected_action:
            raise ValueError("Response action does not match the request.")
        if response[FIELD_REQUEST_ID] != request_id:
            raise ValueError("Response request_id does not match the request.")
        return response

    def _result_from_response(self, response: dict[str, Any]) -> Result:
        """Convert a server response into the generic client result.

        :param response: Validated server response dictionary.
        :returns: Generic client result.
        """
        return Result(
            response[FIELD_STATUS] in {STATUS_SUCCESS, STATUS_READY},
            response[FIELD_MESSAGE],
        )

    def _require_upload_source(self, source_path: Path) -> None:
        """Validate the local file selected for upload.

        :param source_path: Local path that should point to a regular file.
        :raises FileNotFoundError: If the path does not exist.
        :raises IsADirectoryError: If the path is not a file.
        """
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        if not source_path.is_file():
            raise IsADirectoryError(source_path)

    def _require_downloads_directory(self) -> None:
        """Validate the configured Downloads directory without creating it.

        :raises FileNotFoundError: If the path does not exist.
        :raises NotADirectoryError: If the path is not a directory.
        """
        if not self.downloads_path.exists():
            raise FileNotFoundError(self.downloads_path)
        if not self.downloads_path.is_dir():
            raise NotADirectoryError(self.downloads_path)

    def _choose_available_download_path(self, filename: str) -> Path:
        """Choose a duplicate-safe path inside the Downloads directory.

        :param filename: Filename returned by the server.
        :returns: First available local destination path.
        """
        requested_path = self.downloads_path / filename
        if not requested_path.exists():
            return requested_path

        original_path = Path(filename)
        stem = original_path.stem
        suffix = original_path.suffix
        duplicate_index = 2
        while True:
            candidate_path = self.downloads_path / f"{stem}({duplicate_index}){suffix}"
            if not candidate_path.exists():
                return candidate_path
            duplicate_index += 1

    def _generate_request_id(self) -> str:
        """Generate a unique client-side request identifier.

        :returns: Hexadecimal UUID string used as ``request_id``.
        """
        return uuid.uuid4().hex

    def _create_tls_context(self) -> ssl.SSLContext:
        """Create the fixed client TLS context used for every connection."""
        tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        tls_context.minimum_version = TLS_MINIMUM_VERSION
        tls_context.check_hostname = False
        tls_context.verify_mode = ssl.CERT_NONE
        return tls_context
