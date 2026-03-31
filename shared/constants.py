"""Shared protocol constants

The project uses a small custom JSON protocol over TCP. Keeping repeated field
names, action names, and status values here makes the future client and server
implementations less error-prone.
"""

# Top-level message fields used by every JSON request/response pair.
FIELD_ACTION = "action"
FIELD_REQUEST_ID = "request_id"
FIELD_DATA = "data"
FIELD_STATUS = "status"
FIELD_MESSAGE = "message"

# response statuses
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_READY = "ready"

# action names
ACTION_SIGNUP = "SIGNUP"
ACTION_LOGIN = "LOGIN"
ACTION_LIST_FILES = "LIST_FILES"
ACTION_UPLOAD_FILE = "UPLOAD_FILE"
ACTION_UPLOAD_COMPLETE = "UPLOAD_COMPLETE"
ACTION_DOWNLOAD_FILE = "DOWNLOAD_FILE"
ACTION_DELETE_FILE = "DELETE_FILE"
ACTION_LOGOUT = "LOGOUT"

REQUEST_FIELDS = (
    FIELD_ACTION,
    FIELD_REQUEST_ID,
    FIELD_DATA,
)

RESPONSE_FIELDS = (
    FIELD_ACTION,
    FIELD_REQUEST_ID,
    FIELD_STATUS,
    FIELD_MESSAGE,
    FIELD_DATA,
)
