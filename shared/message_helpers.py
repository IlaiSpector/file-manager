"""Helpers for constructing protocol message dictionaries.

The project summary fixes a common request/response shape for all actions.
These helpers centralize that shape so future client and server code can build
messages consistently and tests can assert against one canonical format.
"""

from shared.constants import (
    FIELD_ACTION,
    FIELD_DATA,
    FIELD_MESSAGE,
    FIELD_REQUEST_ID,
    FIELD_STATUS,
    STATUS_ERROR,
    STATUS_READY,
    STATUS_SUCCESS,
)


def _validate_text(value: str, field_name: str) -> str:
    """Validate a text field used in protocol messages.

    :param value: Candidate value for the protocol field.
    :param field_name: Human-readable field name used in error messages.
    :returns: The original value when it is a non-empty string.
    :raises TypeError: If ``value`` is not a string.
    :raises ValueError: If ``value`` is empty or contains only whitespace.
    """
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty.")
    return value


def _normalize_data(data: dict | None) -> dict:
    """Normalize the protocol ``data`` payload to a standalone dictionary.

    :param data: Optional payload supplied by the caller.
    :returns: An empty dictionary when ``data`` is ``None``, otherwise a copy
        of the provided mapping.
    :raises TypeError: If ``data`` is not ``None`` and is not a dictionary.
    """
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise TypeError("data must be a dictionary.")
    return dict(data)


def build_request(action: str, request_id: str, data: dict | None = None) -> dict:
    """Build a request dictionary that follows the shared protocol shape.

    :param action: Protocol action name such as ``LOGIN`` or ``UPLOAD_FILE``.
    :param request_id: Client-generated identifier echoed by the server.
    :param data: Optional action-specific payload.
    :returns: A dictionary containing the standard request fields.
    :raises TypeError: If any validated field has the wrong type.
    :raises ValueError: If ``action`` or ``request_id`` is empty.
    """
    return {
        FIELD_ACTION: _validate_text(action, "action"),
        FIELD_REQUEST_ID: _validate_text(request_id, "request_id"),
        FIELD_DATA: _normalize_data(data),
    }


def build_response(
    action: str,
    request_id: str,
    status: str,
    message: str,
    data: dict | None = None,
) -> dict:
    """Build a response dictionary that follows the shared protocol shape.

    :param action: Action name the response belongs to.
    :param request_id: Request identifier being answered.
    :param status: Response status such as ``success``, ``error``, or
        ``ready``.
    :param message: Human-readable message intended for the client.
    :param data: Optional action-specific response payload.
    :returns: A dictionary containing the standard response fields.
    :raises TypeError: If any validated field has the wrong type.
    :raises ValueError: If any required text field is empty.
    """
    return {
        FIELD_ACTION: _validate_text(action, "action"),
        FIELD_REQUEST_ID: _validate_text(request_id, "request_id"),
        FIELD_STATUS: _validate_text(status, "status"),
        FIELD_MESSAGE: _validate_text(message, "message"),
        FIELD_DATA: _normalize_data(data),
    }


def build_success_response(
    action: str,
    request_id: str,
    message: str,
    data: dict | None = None,
) -> dict:
    """Build a standard response whose status is ``success``.

    :returns: Response dictionary ready for protocol encoding.
    """
    return build_response(action, request_id, STATUS_SUCCESS, message, data)


def build_error_response(
    action: str,
    request_id: str,
    message: str,
    data: dict | None = None,
) -> dict:
    """Build a standard response whose status is ``error``.

    :returns: Response dictionary ready for protocol encoding.
    """
    return build_response(action, request_id, STATUS_ERROR, message, data)


def build_ready_response(
    action: str,
    request_id: str,
    message: str,
    data: dict | None = None,
) -> dict:
    """Build a standard response whose status is ``ready``.

    ``ready`` is used for staged operations such as upload and download
    handshakes before raw bytes are transferred.

    :returns: Response dictionary ready for protocol encoding.
    """
    return build_response(action, request_id, STATUS_READY, message, data)
