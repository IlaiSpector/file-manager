"""Reusable validation helpers for server-side inputs.

These functions cover the basic input checks already needed by the current
authentication flow. filename and path-safety validation would be implemented here.
"""

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}
INVALID_FILENAME_CHARACTERS = set('<>:"/\\|?*')


def require_non_empty_text(value: str, field_name: str) -> str:
    """Return a stripped text value or raise when it is empty."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")
    return normalized


def is_valid_email(email: str) -> bool:
    """Perform a simple email-shape validation."""
    if not isinstance(email, str):
        return False

    candidate = email.strip()
    if candidate.count("@") != 1:
        return False

    local_part, domain_part = candidate.split("@", 1)
    if not local_part or not domain_part:
        return False

    if "." not in domain_part:
        return False

    if domain_part.startswith(".") or domain_part.endswith("."):
        return False

    return True


def validate_windows_filename(filename: str) -> str:
    """Return a safe filename or raise when it violates Windows filename rules. throws TypeError/ValueError"""
    if not isinstance(filename, str):
        raise TypeError("filename must be a string.")
    if not filename:
        raise ValueError("filename cannot be empty.")
    if filename in {".", ".."}:
        raise ValueError("filename is invalid.")
    if filename.endswith((" ", ".")):
        raise ValueError("filename cannot end with a space or dot.")
    if any(character in INVALID_FILENAME_CHARACTERS for character in filename):
        raise ValueError("filename contains invalid characters. can't contain <>:\"/\\|?*")
    if any(ord(character) < 32 for character in filename):
        raise ValueError("filename contains invalid characters.")

    reserved_candidate = filename.split(".", 1)[0].upper()
    if reserved_candidate in WINDOWS_RESERVED_NAMES:
        raise ValueError("filename uses a reserved Windows name.")

    return filename
