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
    """Require a non-empty string for a protocol field."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty.")
    return value


def _normalize_data(data: dict | None) -> dict:
    """Return a safe dictionary payload for the message ``data`` field."""
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise TypeError("data must be a dictionary.")
    return dict(data)


def build_request(action: str, request_id: str, data: dict | None = None) -> dict:
    """Create a standard client request message.

    The request shape matches the agreed protocol contract:
    ``action`` + ``request_id`` + ``data``
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
    """Create a standard server response message.

    Responses extend the request identity with ``status`` and a human-readable
    ``message`` so the future GUI can show useful feedback to the user.
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
    """Create a response whose status is ``success``."""
    return build_response(action, request_id, STATUS_SUCCESS, message, data)


def build_error_response(
    action: str,
    request_id: str,
    message: str,
    data: dict | None = None,
) -> dict:
    """Create a response whose status is ``error``."""
    return build_response(action, request_id, STATUS_ERROR, message, data)


def build_ready_response(
    action: str,
    request_id: str,
    message: str,
    data: dict | None = None,
) -> dict:
    """Create a response whose status is ``ready``.

    ``ready`` is used for staged operations such as file upload/download
    handshakes before raw bytes are transferred.
    """
    return build_response(action, request_id, STATUS_READY, message, data)


# Future helper builders can be added here if the protocol grows enough that
# per-action payload construction becomes repetitive.
