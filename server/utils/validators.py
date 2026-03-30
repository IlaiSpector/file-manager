"""Reusable validation helpers for server-side inputs."""


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
