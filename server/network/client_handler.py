"""Per-client request handling for the server."""


import json
import socket
from typing import Callable

from server.config import MAX_UPLOAD_SIZE_BYTES
from server.database.models import User
from server.services.auth_service import AuthService
from server.services.file_service import FileService
from server.utils.validators import validate_windows_filename
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
    FIELD_REQUEST_ID,
)
from shared.message_helpers import (
    build_error_response,
    build_ready_response,
    build_success_response,
)
from shared.protocol import (
    decode_message,
    encode_message,
    recv_exact,
    recv_message_bytes_or_none,
    send_all,
)

ActionHandler = Callable[[str, dict], None]


class ClientHandler:
    """Own the lifecycle and protocol flow for one client socket."""

    def __init__(
        self,
        client_socket: socket.socket,
        auth_service: AuthService,
        file_service: FileService,
        client_address: tuple[str, int] | None = None,
    ) -> None:
        self.client_socket = client_socket
        self.auth_service = auth_service
        self.file_service = file_service
        self.client_address = client_address
        self.current_user: User | None = None
        self._action_handlers: dict[str, ActionHandler] = {
            ACTION_SIGNUP: self.handle_signup,
            ACTION_LOGIN: self.handle_login,
            ACTION_LIST_FILES: self.handle_list_files,
            ACTION_UPLOAD_FILE: self.handle_upload_file,
            ACTION_DOWNLOAD_FILE: self.handle_download_file,
            ACTION_DELETE_FILE: self.handle_delete_file,
            ACTION_LOGOUT: self.handle_logout,
        }

    def handle_client(self) -> None:
        """Process requests for this client connection until it ends.

        A clean disconnect before the next message starts ends the loop
        quietly. Malformed or truncated transfers eventually surface as
        :class:`ConnectionError`, which stops only this handler and still
        triggers socket cleanup in ``finally``.
        """

        try:
            while True:
                message_bytes = recv_message_bytes_or_none(self.client_socket)
                if message_bytes is None:
                    break

                try:
                    message = decode_message(message_bytes)
                except (ValueError, json.JSONDecodeError):
                    break

                self._dispatch_message(message)
        except ConnectionError:
            return
        except TimeoutError:
            print(f"timed out client {self.client_address}")
            return
        finally:
            self.close()

    def close(self) -> None:
        """Close the client socket without raising shutdown noise.

        The method tries to shut down both read and write directions first, but
        ignores shutdown errors so calling close() during cleanup won’t fail if the socket was already closed
        """
        try:
            #shuts down communication, both reading and writing with the socket. SHUT_RDWR: RD means reading, WR meaning writing
            self.client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        finally:
            print(f"closed client {self.client_address}")
            self.client_socket.close()

    def _dispatch_message(self, message: dict) -> None:
        """Validate a decoded request and route it to the matching handler.

        :param message: Decoded request dictionary received from the client.
        :raises ConnectionError: If the request cannot be safely answered
            because it lacks a usable identity.
        """
        action, request_id = self._extract_request_identity(message)
        is_valid, error_message = self._validate_request_envelope(message)
        if not is_valid:
            if action is not None and request_id is not None:
                self._send_json_message(build_error_response(action, request_id, error_message))
                return
            raise ConnectionError(error_message)


        # asserts are used to make the IDE realize that action, request_id and data must be str, str and dict
        assert action is not None
        assert request_id is not None
        data = message[FIELD_DATA]
        assert isinstance(data, dict)

        handler = self._action_handlers.get(action)
        if handler is None:
            self._send_json_message(build_error_response(action, request_id, "Unsupported action"))
            return

        is_allowed, denial_message = self._validate_action_allowed(action)
        if not is_allowed:
            self._send_json_message(build_error_response(action, request_id, denial_message))
            return

        handler(request_id, data)

    def _extract_request_identity(self, message: dict) -> tuple[str | None, str | None]:
        """Extract the request identity used for error responses.

        :param message: Decoded request dictionary.
        :returns: Two-item tuple ``(action, request_id)`` when both values are
            usable non-empty strings; otherwise ``(None, None)``.
        """
        action = message.get(FIELD_ACTION)
        request_id = message.get(FIELD_REQUEST_ID)

        if not isinstance(action, str) or not action.strip():
            return None, None
        if not isinstance(request_id, str) or not request_id.strip():
            return None, None
        return action, request_id

    def _validate_request_envelope(self, message: dict) -> tuple[bool, str]:
        """Validate the request fields shared by every protocol action.

        :param message: Decoded request dictionary.
        :returns: Two-item tuple ``(is_valid, message)`` describing whether the
            request can be routed safely.
        """
        if FIELD_ACTION not in message:
            return False, "Request is missing the action field."
        if FIELD_REQUEST_ID not in message:
            return False, "Request is missing the request_id field."
        if FIELD_DATA not in message:
            return False, "Request is missing the data field."
        if not isinstance(message[FIELD_ACTION], str) or not message[FIELD_ACTION].strip():
            return False, "Request action must be a non-empty string."
        if not isinstance(message[FIELD_REQUEST_ID], str) or not message[FIELD_REQUEST_ID].strip():
            return False, "Request request_id must be a non-empty string."
        if not isinstance(message[FIELD_DATA], dict):
            return False, "Request data must be a dictionary."
        return True, ""

    def _validate_action_allowed(self, action: str) -> tuple[bool, str]:
        """Enforce the connection-based authentication rules.

        :param action: Action that the client requested.
        :returns: Two-item tuple ``(is_allowed, message)`` describing whether
            the current connection state may perform that action.
        """
        if self.current_user is None and action not in {ACTION_SIGNUP, ACTION_LOGIN}:
            return False, "User is not authenticated"
        if self.current_user is not None and action in {ACTION_SIGNUP, ACTION_LOGIN}:
            return False, "User is already authenticated"
        return True, ""

    def handle_signup(self, request_id: str, data: dict) -> None:
        """Handle a ``SIGNUP`` request for the current connection.

        On success the connection immediately becomes authenticated as the new
        user.

        :param request_id: Request identifier echoed back to the client.
        :param data: Signup payload already validated as a dictionary.
        """
        is_valid, error_message = self._validate_signup(data)
        if not is_valid:
            self._send_json_message(build_error_response(ACTION_SIGNUP, request_id, error_message))
            return

        result = self.auth_service.try_signup(
            username=data["username"],
            email=data["email"],
            password=data["password"],
        )
        if result.success:
            self.current_user = result.user
            self._send_json_message(
                build_success_response(ACTION_SIGNUP, request_id, result.message),
            )
            return

        self._send_json_message(build_error_response(ACTION_SIGNUP, request_id, result.message))

    def _validate_signup(self, data: dict) -> tuple[bool, str]:
        """Validate the action-specific fields for ``SIGNUP``.

        :param data: Signup payload dictionary.
        :returns: Two-item tuple ``(is_valid, message)`` describing whether the
            required signup fields are present.
        """
        return self._require_fields(data, "username", "email", "password")

    def handle_login(self, request_id: str, data: dict) -> None:
        """Handle a ``LOGIN`` request for the current connection.

        On success the connection becomes authenticated as the matching user.

        :param request_id: Request identifier echoed back to the client.
        :param data: Login payload already validated as a dictionary.
        """
        is_valid, error_message = self._validate_login(data)
        if not is_valid:
            self._send_json_message(build_error_response(ACTION_LOGIN, request_id, error_message))
            return

        result = self.auth_service.try_login(
            email=data["email"],
            password=data["password"],
        )
        if result.success:
            self.current_user = result.user
            self._send_json_message(
                build_success_response(ACTION_LOGIN, request_id, result.message),
            )
            return

        self._send_json_message(build_error_response(ACTION_LOGIN, request_id, result.message))

    def _validate_login(self, data: dict) -> tuple[bool, str]:
        """Validate the action-specific fields for ``LOGIN``.

        :param data: Login payload dictionary.
        :returns: Two-item tuple ``(is_valid, message)`` describing whether the
            required login fields are present.
        """
        return self._require_fields(data, "email", "password")

    def handle_list_files(self, request_id: str, data: dict) -> None:
        """Handle a ``LIST_FILES`` request for the authenticated user.

        :param request_id: Request identifier echoed back to the client.
        :param data: Action payload dictionary. The envelope has already
            validated that it is a dictionary, and this action has no
            additional fields.
        """

        assert self.current_user is not None
        is_successful, message, files = self.file_service.list_files(self.current_user.id)
        if is_successful:
            self._send_json_message(
                build_success_response(
                    ACTION_LIST_FILES,
                    request_id,
                    message,
                    {"files": files},
                )
            )
            return

        self._send_json_message(build_error_response(ACTION_LIST_FILES, request_id, message))


    def handle_upload_file(self, request_id: str, data: dict) -> None:
        """Handle the staged ``UPLOAD_FILE`` protocol flow.

        The method validates the upload metadata, asks the file service for the
        final filename, sends the ``ready`` response, receives exactly the
        announced number of raw bytes, and then persists the upload.

        :param request_id: Request identifier echoed back to the client.
        :param data: Upload payload already validated as a dictionary.
        :raises ConnectionError: If the client disconnects during the raw-byte
            receive or while a response is being sent.
        """
        is_valid, error_message = self._validate_upload_file(data)
        if not is_valid:
            self._send_json_message(build_error_response(ACTION_UPLOAD_FILE, request_id, error_message))
            return

        assert self.current_user is not None
        filename = data["filename"]
        filesize = data["filesize"]
        is_successful, message, final_filename = self.file_service.prepare_upload(
            self.current_user.id,
            filename,
        )
        if not is_successful or final_filename is None:
            self._send_json_message(build_error_response(ACTION_UPLOAD_FILE, request_id, message))
            return

        self._send_json_message(
            build_ready_response(
                ACTION_UPLOAD_FILE,
                request_id,
                message,
                {"final_filename": final_filename},
            )
        )
        file_bytes = recv_exact(self.client_socket, filesize)

        is_successful, message = self.file_service.save_file_bytes(
            self.current_user.id,
            final_filename,
            file_bytes,
        )
        if is_successful:
            self._send_json_message(
                build_success_response(
                    ACTION_UPLOAD_COMPLETE,
                    request_id,
                    message,
                    {"filename": final_filename},
                )
            )
            return

        self._send_json_message(
            build_error_response(ACTION_UPLOAD_COMPLETE, request_id, message)
        )

    def _validate_upload_file(self, data: dict) -> tuple[bool, str]:
        """Validate the action-specific fields for ``UPLOAD_FILE``.

        :param data: Upload payload dictionary.
        :returns: Two-item tuple ``(is_valid, message)`` describing whether the
            upload metadata is acceptable before raw bytes are received.
        """
        is_valid, error_message = self._require_fields(data, "filename", "filesize")
        if not is_valid:
            return False, error_message

        try:
            validate_windows_filename(data["filename"])
        except (TypeError, ValueError) as exc:
            return False, str(exc)

        filesize = data["filesize"]
        if isinstance(filesize, bool) or not isinstance(filesize, int):
            return False, "filesize must be an integer."
        if filesize < 0:
            return False, "filesize cannot be negative."
        if filesize > MAX_UPLOAD_SIZE_BYTES:
            return False, f"File exceeds maximum size of {MAX_UPLOAD_SIZE_BYTES} bytes."
        return True, ""

    def handle_download_file(self, request_id: str, data: dict) -> None:
        """Handle the staged ``DOWNLOAD_FILE`` protocol flow.

        The method validates the request, loads the file bytes from the file
        service, sends the ``ready`` response with the final size, and then
        streams the raw payload.

        :param request_id: Request identifier echoed back to the client.
        :param data: Download payload already validated as a dictionary.
        :raises ConnectionError: If the client disconnects while the response
            or raw bytes are being sent.
        """
        is_valid, error_message = self._validate_download_file(data)
        if not is_valid:
            self._send_json_message(
                build_error_response(ACTION_DOWNLOAD_FILE, request_id, error_message)
            )
            return

        assert self.current_user is not None
        filename = data["filename"]
        is_successful, message, file_bytes = self.file_service.get_file_bytes(
            self.current_user.id,
            filename,
        )
        if not is_successful or file_bytes is None:
            self._send_json_message(build_error_response(ACTION_DOWNLOAD_FILE, request_id, message))
            return

        self._send_json_message(
            build_ready_response(
                ACTION_DOWNLOAD_FILE,
                request_id,
                message,
                {"filename": filename, "filesize": len(file_bytes)},
            )
        )
        self._send_raw_bytes(file_bytes)

    def _validate_download_file(self, data: dict) -> tuple[bool, str]:
        """Validate the action-specific fields for ``DOWNLOAD_FILE``.

        :param data: Download payload dictionary.
        :returns: Two-item tuple ``(is_valid, message)`` describing whether the
            required filename field is present.
        """
        return self._require_fields(data, "filename")

    def handle_delete_file(self, request_id: str, data: dict) -> None:
        """Handle a ``DELETE_FILE`` request for the authenticated user.

        :param request_id: Request identifier echoed back to the client.
        :param data: Delete payload already validated as a dictionary.
        """
        is_valid, error_message = self._validate_delete_file(data)
        if not is_valid:
            self._send_json_message(build_error_response(ACTION_DELETE_FILE, request_id, error_message))
            return

        assert self.current_user is not None
        is_successful, message = self.file_service.delete_file(
            self.current_user.id,
            data["filename"],
        )
        if is_successful:
            self._send_json_message(
                build_success_response(ACTION_DELETE_FILE, request_id, message),
            )
            return

        self._send_json_message(build_error_response(ACTION_DELETE_FILE, request_id, message))

    def _validate_delete_file(self, data: dict) -> tuple[bool, str]:
        """Validate the action-specific fields for ``DELETE_FILE``.

        :param data: Delete payload dictionary.
        :returns: Two-item tuple ``(is_valid, message)`` describing whether the
            required filename field is present.
        """
        return self._require_fields(data, "filename")

    def handle_logout(self, request_id: str, data: dict) -> None:
        """Handle a ``LOGOUT`` request for the current connection.

        The socket remains open, but the connection returns to the unauthenticated
        state.

        :param request_id: Request identifier echoed back to the client.
        :param data: Action payload dictionary. This action has no additional
            fields beyond the validated envelope.
        """
        self.current_user = None
        self._send_json_message(
            build_success_response(ACTION_LOGOUT, request_id, "Logged out successfully"),
        )

    def _require_fields(self, data: dict, *field_names: str) -> tuple[bool, str]:
        """Ensure an already-validated payload contains required keys.

        The caller is expected to pass a payload that has already been checked
        as a dictionary by the request envelope validation step.

        :param data: Action payload dictionary.
        :param field_names: Required keys that must exist in ``data``.
        :returns: Two-item tuple ``(is_valid, message)`` describing whether all
            required fields are present.
        """
        for field_name in field_names:
            if field_name not in data:
                return False, f"Request data is missing the {field_name} field."
        return True, ""

    def _send_json_message(self, message: dict) -> None:
        """Send one length-prefixed JSON response to the client.

        :param message: Response dictionary to encode and send.
        :raises ConnectionError: If the underlying socket send fails.
        """
        try:
            send_all(self.client_socket, encode_message(message))
        except OSError as exc:
            raise ConnectionError("Failed to send response to the client.") from exc

    def _send_raw_bytes(self, payload: bytes) -> None:
        """Send one raw binary payload to the client.

        :param payload: Raw bytes to send after a successful ``ready``
            handshake.
        :raises ConnectionError: If the underlying socket send fails.
        """
        try:
            send_all(self.client_socket, payload)
        except OSError as exc:
            raise ConnectionError("Failed to send raw bytes to the client.") from exc
