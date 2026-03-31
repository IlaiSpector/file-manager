"""Authentication service backed by the server database."""

import uuid

import bcrypt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.database.db_manager import DatabaseManager
from server.database.models import User
from server.services.user_storage_service import UserStorageService
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
        """Support direct equality checks"""
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
        user_storage_service: UserStorageService,
    ) -> None:
        self.db_manager = db_manager
        self.user_storage_service = user_storage_service

    def try_signup(self, username: str, email: str, password: str) -> AuthResult:
        """Create a new user account when the provided data is valid.

        Expected validation failures are returned as ``AuthResult`` instances.
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
                self.user_storage_service.create_user_storage_folder(user.id)
                return AuthResult(True, "User created successfully", user)
        except IntegrityError:
            # if there is a problem with the creation in the database, the user can't be created. 
            return AuthResult(False, "Email or username already exists", None)

    def try_login(self, email: str, password: str) -> AuthResult:
        """Authenticate a user by email and password."""
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
        """Create the UUID string used as user id"""
        return str(uuid.uuid4())

    def _normalize_email(self, email: str) -> str:
        """Normalize email input for uniqueness checks and login lookup."""
        normalized_email = require_non_empty_text(email, "email").lower()
        return normalized_email

    def _require_password(self, password: str) -> str:
        """Require a non-empty password string.

        The password is not stripped because spaces may be part
        of the user's intended password
        """
        if not isinstance(password, str):
            raise TypeError("password must be a string.")
        if not password.strip():
            raise ValueError("password cannot be empty.")
        return password

    def _hash_password(self, password: str) -> str:
        """Return a bcrypt hash string for database storage."""
        password_bytes = password.encode("utf-8")
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Check a password against the stored bcrypt hash."""
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))

    def _get_user_by_email(self, session: Session, email: str) -> User | None:
        """Look up a user by email address."""
        statement = select(User).where(User.email == email)
        return session.scalar(statement)

    def _email_exists(self, session: Session, email: str) -> bool:
        """Return whether a user with a specific email is already registeed."""
        return self._get_user_by_email(session, email) is not None

    def _username_exists(self, session: Session, username: str) -> bool:
        """Return whether a username is already registered."""
        statement = select(User).where(User.username == username)
        return session.scalar(statement) is not None
