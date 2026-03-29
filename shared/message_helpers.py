"""Helpers for constructing standard protocol message dictionaries."""

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
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty.")
    return value


def _normalize_data(data: dict | None) -> dict:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise TypeError("data must be a dictionary.")
    return dict(data)


def build_request(action: str, request_id: str, data: dict | None = None) -> dict:
    """Create a standard client request message."""
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
    """Create a standard server response message."""
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
    return build_response(action, request_id, STATUS_SUCCESS, message, data)


def build_error_response(
    action: str,
    request_id: str,
    message: str,
    data: dict | None = None,
) -> dict:
    return build_response(action, request_id, STATUS_ERROR, message, data)


def build_ready_response(
    action: str,
    request_id: str,
    message: str,
    data: dict | None = None,
) -> dict:
    return build_response(action, request_id, STATUS_READY, message, data)


#TODO create build_field_data_<name of type_message> for each type message that I will futreally create
