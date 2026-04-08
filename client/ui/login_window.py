"""Login window for the PyQt6 client application."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from client.network.client_socket import ClientSocket


class LoginWindow(QWidget):
    """Allow an existing user to log in through the GUI."""

    def __init__(
        self,
        client_socket: ClientSocket,
        on_signup_requested: Callable[[], None],
        on_authenticated: Callable[[], None],
    ) -> None:
        """Create the login window.

        :param client_socket: Connected client socket used for login requests.
        :param on_signup_requested: Callback used to switch to the signup form.
        :param on_authenticated: Callback used after successful authentication.
        """
        super().__init__()
        self.client_socket = client_socket
        self.on_signup_requested = on_signup_requested
        self.on_authenticated = on_authenticated

        self.email_input = QLineEdit()
        self.password_input = QLineEdit()
        self.login_button = QPushButton("Log In")
        self.signup_button = QPushButton("Create Account")

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """Build the login form widgets and layout."""
        self.setWindowTitle("Secure File Manager - Login")
        self.resize(520, 460)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(32, 32, 32, 32)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setMinimumWidth(430)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 34, 34, 34)
        card_layout.setSpacing(18)

        title_label = QLabel("Welcome back")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle_label = QLabel("Log in to manage your private server files.")
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.email_input.setPlaceholderText("you@example.com")
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setVerticalSpacing(14)
        form_layout.addRow("Email", self.email_input)
        form_layout.addRow("Password", self.password_input)

        self.login_button.setObjectName("primaryButton")
        self.signup_button.setObjectName("secondaryButton")

        switch_layout = QHBoxLayout()
        switch_label = QLabel("New here?")
        switch_label.setObjectName("subtitleLabel")
        switch_layout.addWidget(switch_label)
        switch_layout.addWidget(self.signup_button)

        card_layout.addWidget(title_label)
        card_layout.addWidget(subtitle_label)
        card_layout.addLayout(form_layout)
        card_layout.addWidget(self.login_button)
        card_layout.addLayout(switch_layout)

        page_layout.addWidget(card)

    def _connect_signals(self) -> None:
        """Connect button clicks and keyboard shortcuts."""
        self.login_button.clicked.connect(self._handle_login)
        self.signup_button.clicked.connect(self.on_signup_requested)
        self.password_input.returnPressed.connect(self._handle_login) # if enter is pressed on password input field, handle_sigunp will happen.

    def _handle_login(self) -> None:
        """Validate the form, send the login request, and handle the result."""
        email = self.email_input.text().strip()
        password = self.password_input.text()
        validation_error = self._validate_form(email, password)
        if validation_error:
            QMessageBox.warning(self, "Login details needed", validation_error)
            return

        self._set_busy(True)
        try:
            result = self.client_socket.login(email=email, password=password)
        except (ConnectionError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Login failed", str(exc))
            return
        finally:
            self._set_busy(False)

        if result.success:
            self.on_authenticated()
            return

        QMessageBox.warning(self, "Login failed", result.message)

    def _validate_form(self, email: str, password: str) -> str | None:
        """Validate login form fields before contacting the server.

        :param email: Email address typed by the user.
        :param password: Password typed by the user.
        :returns: Error message when validation fails, otherwise ``None``.
        """
        if not email:
            return "Please enter your email address."
        if not self._looks_like_email(email):
            return "Please enter a valid email address."
        if not password.strip():
            return "Please enter your password."
        return None

    def _looks_like_email(self, email: str) -> bool:
        """Perform the same simple email-shape check used by the project.

        :param email: Email candidate to validate.
        :returns: ``True`` when the value looks like an email address.
        """
        if email.count("@") != 1:
            return False
        local_part, domain_part = email.split("@", 1)
        if not local_part or not domain_part:
            return False
        if "." not in domain_part:
            return False
        return not domain_part.startswith(".") and not domain_part.endswith(".")

    def _set_busy(self, is_busy: bool) -> None:
        """Toggle the form busy state during blocking network calls.

        :param is_busy: Whether the form should be disabled.
        """
        self.email_input.setEnabled(not is_busy)
        self.password_input.setEnabled(not is_busy)
        self.login_button.setEnabled(not is_busy)
        self.signup_button.setEnabled(not is_busy)

        if is_busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor) # changes the mouse to loading cursors
        else:
            QApplication.restoreOverrideCursor()
        QApplication.processEvents()  # immediatly update the GUI
