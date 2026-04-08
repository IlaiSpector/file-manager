"""Client GUI entrypoint for the file manager application."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from client.network.client_socket import ClientSocket
from client.ui.file_manager_window import FileManagerWindow
from client.ui.login_window import LoginWindow
from client.ui.signup_window import SignupWindow


APP_STYLESHEET = """
QWidget {
    background-color: #f4f7fb;
    color: #1f2937;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
}

QFrame#card {
    background-color: #ffffff;
    border: 1px solid #dbe3ef;
    border-radius: 18px;
}

QLabel#titleLabel {
    color: #111827;
    font-size: 28px;
    font-weight: 700;
}

QLabel#subtitleLabel {
    color: #64748b;
    font-size: 14px;
}

QLabel#sectionLabel {
    color: #111827;
    font-size: 20px;
    font-weight: 700;
}

QLabel#statusLabel {
    color: #64748b;
}

QLineEdit {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 10px 12px;
}

QLineEdit:focus {
    border: 1px solid #2563eb;
}

QPushButton {
    border: none;
    border-radius: 10px;
    font-weight: 600;
    padding: 10px 16px;
}

QPushButton#primaryButton {
    background-color: #2563eb;
    color: #ffffff;
}

QPushButton#primaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#secondaryButton {
    background-color: #e2e8f0;
    color: #1f2937;
}

QPushButton#secondaryButton:hover {
    background-color: #cbd5e1;
}

QPushButton#dangerButton {
    background-color: #dc2626;
    color: #ffffff;
}

QPushButton#dangerButton:hover {
    background-color: #b91c1c;
}

QPushButton:disabled {
    background-color: #cbd5e1;
    color: #64748b;
}

QTableWidget {
    background-color: #ffffff;
    border: 1px solid #dbe3ef;
    border-radius: 14px;
    gridline-color: #e2e8f0;
    selection-background-color: #dbeafe;
    selection-color: #111827;
}

QHeaderView::section {
    background-color: #eff6ff;
    color: #1e3a8a;
    border: none;
    border-bottom: 1px solid #dbe3ef;
    font-weight: 700;
    padding: 9px;
}
"""


class ClientGuiController:
    """Coordinate the client GUI windows and shared socket connection."""

    def __init__(self, client_socket: ClientSocket) -> None:
        """Store the socket wrapper used by all client windows.

        :param client_socket: Connected blocking client socket wrapper.
        """
        self.client_socket = client_socket
        self.current_window: QWidget | None = None

    def show_login(self) -> None:
        """Display the login screen."""
        self._show_window(
            LoginWindow(
                client_socket=self.client_socket,
                on_signup_requested=self.show_signup,
                on_authenticated=self.show_file_manager,
            )
        )

    def show_signup(self) -> None:
        """Display the signup screen."""
        self._show_window(
            SignupWindow(
                client_socket=self.client_socket,
                on_login_requested=self.show_login,
                on_authenticated=self.show_file_manager,
            )
        )

    def show_file_manager(self) -> None:
        """Display the authenticated file manager screen."""
        file_manager_window = FileManagerWindow(
            client_socket=self.client_socket,
            on_logout=self.show_login,
        )
        self._show_window(file_manager_window)
        file_manager_window.refresh_files()

    def _show_window(self, window: QWidget) -> None:
        """Replace the visible top-level window.

        :param window: Window that should become visible.
        """
        previous_window = self.current_window
        self.current_window = window
        window.show()

        if previous_window is not None:
            previous_window.close()
            previous_window.deleteLater()


def main() -> int:
    """Start the PyQt6 client application.

    :returns: Process exit code returned by Qt.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Secure File Manager")
    app.setStyleSheet(APP_STYLESHEET)

    client_socket = ClientSocket()
    try:
        client_socket.connect()
    except ConnectionError as exc:
        QMessageBox.critical(
            None,
            "Connection failed",
            (
                "Could not connect to the file manager server.\n\n"
                f"Server: {client_socket.host}:{client_socket.port}\n"
                f"Error: {exc}"
            ),
        )
        return 1

    controller = ClientGuiController(client_socket)
    controller.show_login()

    try:
        return app.exec()
    finally:
        client_socket.close()


if __name__ == "__main__":
    raise SystemExit(main())
