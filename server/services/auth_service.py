"""Authentication service backed by the server database."""

from pathlib import Path
import uuid

import bcrypt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.database.db_manager import DatabaseManager
from server.database.models import User
from server.utils.path_utils import get_user_storage_path
from server.utils.validators import is_valid_email, require_non_empty_text


class AuthResult:
    """result for signup/login attempts.    """

    def __init__(self, success: bool, message: str, user: User | None) -> None:
        self.success = success
        self.message = message
        self.user = user

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"success={self.success!r}, "
            f"message={self.message!r}, "
            f"user={self.user!r})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare two authentication results by value.

        :param other: Object being compared with this result.
        :returns: ``True`` when both objects hold the same success flag,
            message, and user reference.
        """
        if not isinstance(other, AuthResult):
            return NotImplemented
        return (
            self.success == other.success
            and self.message == other.message
            and self.user == other.user
        )


class AuthService:
    """Business logic for signup and login."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        storage_root: Path,
    ) -> None:
        self.db_manager = db_manager
        self.storage_root = storage_root

    def try_signup(self, username: str, email: str, password: str) -> AuthResult:
        """Attempt to create a new user account.

        Expected validation or uniqueness failures are returned as
        :class:`AuthResult` objects with ``success=False``. Unexpected database
        or filesystem errors are allowed to propagate unless they happen because
        the username or email is not unique.

        :param username: Requested unique username.
        :param email: Email used for login and uniqueness checks.
        :param password: Plain-text password supplied by the client.
        :returns: Authentication result describing the signup outcome and, on
            success, the newly created user.
        """
        try:
            normalized_username = require_non_empty_text(username, "username")
            normalized_email = self._normalize_email(email)
            normalized_password = self._require_password(password)
        except (TypeError, ValueError) as exc:
            return AuthResult(False, str(exc), None)

        if not is_valid_email(normalized_email):
            return AuthResult(False, "Email address is invalid.", None)

        password_hash = self._hash_password(normalized_password)
        user = User(
            id=self._generate_user_id(),
            username=normalized_username,
            email=normalized_email,
            password_hash=password_hash,
        )

        try:
            with self.db_manager.session_scope() as session:
                if self._username_exists(session, normalized_username) or self._email_exists(
                    session, normalized_email
                ):
                    return AuthResult(False, "Email or username already exists", None)

                session.add(user)
                # after ``flush``, the changes are still revertable in case of a problem with the creation of the user
                session.flush()
                self._create_user_storage_folder(user.id)
                return AuthResult(True, "User created successfully", user)
        except IntegrityError:
            # if there is a problem with the creation in the database, the user can't be created. 
            return AuthResult(False, "Email or username already exists", None)

    def try_login(self, email: str, password: str) -> AuthResult:
        """Authenticate a user by email and password.

        :param email: Email used to locate the account.
        :param password: Plain-text password supplied by the client.
        :returns: Authentication result describing whether the login succeeded.
        """
        try:
            normalized_email = self._normalize_email(email)
            normalized_password = self._require_password(password)
        except (TypeError, ValueError):
            return AuthResult(False, "Invalid email or password", None)

        with self.db_manager.session_scope() as session:
            user = self._get_user_by_email(session, normalized_email)
            if user is None:
                return AuthResult(False, "Invalid email or password", None)

            if not self._verify_password(normalized_password, user.password_hash):
                return AuthResult(False, "Invalid email or password", None)

            return AuthResult(True, "Login successful", user)

    def _generate_user_id(self) -> str:
        """Create the UUID string stored as the user identifier.

        :returns: Newly generated UUID string.
        """
        return str(uuid.uuid4())

    def _normalize_email(self, email: str) -> str:
        """Normalize an email for storage and lookup.

        :param email: Raw email value from the caller.
        :returns: Lowercased, trimmed email string.
        :raises TypeError: If ``email`` is not a string.
        :raises ValueError: If the normalized email is empty.
        """
        normalized_email = require_non_empty_text(email, "email").lower()
        return normalized_email

    def _require_password(self, password: str) -> str:
        """Validate that a password was supplied.

        The password itself is returned unchanged so leading or trailing spaces
        remain valid when they are part of the user's intended password.

        :param password: Candidate plain-text password.
        :returns: The original password string.
        :raises TypeError: If ``password`` is not a string.
        :raises ValueError: If the password is empty or whitespace-only.
        """
        if not isinstance(password, str):
            raise TypeError("password must be a string.")
        if not password.strip():
            raise ValueError("password cannot be empty.")
        return password

    def _hash_password(self, password: str) -> str:
        """Hash a plain-text password for database storage.

        :param password: Plain-text password
        :returns: Bcrypt hash string suitable for persistent storage.
        """
        password_bytes = password.encode("utf-8")
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify a plain-text password against a stored bcrypt hash.

        :param password: Plain-text password supplied by the client.
        :param stored_hash: Hash read from persistent storage.
        :returns: ``True`` when the password matches the stored hash.
        """
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))

    def _get_user_by_email(self, session: Session, email: str) -> User | None:
        """Fetch one user by email address.

        :param session: Active SQLAlchemy session used for the query.
        :param email: Normalized email to search for.
        :returns: Matching user object or ``None`` when no account exists.
        """
        statement = select(User).where(User.email == email)
        return session.scalar(statement)

    def _email_exists(self, session: Session, email: str) -> bool:
        """Check whether an email address is already registered.

        :param session: Active SQLAlchemy session used for the query.
        :param email: Normalized email to search for.
        :returns: ``True`` when a matching user already exists.
        """
        return self._get_user_by_email(session, email) is not None

    def _username_exists(self, session: Session, username: str) -> bool:
        """Check whether a username is already registered.

        :param session: Active SQLAlchemy session used for the query.
        :param username: Username to search for.
        :returns: ``True`` when a matching user already exists.
        """
        statement = select(User).where(User.username == username)
        return session.scalar(statement) is not None

    def _create_user_storage_folder(self, user_id: str) -> None:
        """Create the storage directory for one newly created user.

        The root storage directory is created first when needed. The user
        directory itself is expected not to exist yet; an existing directory is
        treated as an error because it likely signals inconsistent signup
        state.

        :param user_id: Identifier of the user whose folder should be created.
        :raises FileExistsError: If the target user directory already exists.
        :raises OSError: If the filesystem operation fails.
        """

        # exists_ok=True means if the folder exists, don't raise an error and leave it as it is.
        self.storage_root.mkdir(parents=True, exist_ok=True)
        user_storage_path = get_user_storage_path(self.storage_root, user_id)
        # exists_ok=False means if the folder exists, raise an error. useful to show bugs in folder creation
        user_storage_path.mkdir(parents=True, exist_ok=False)
