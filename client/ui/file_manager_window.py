"""Main file manager window for the PyQt6 client application."""

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from client.network.client_socket import ClientSocket, Result


class FileManagerWindow(QWidget):
    """Allow an authenticated user to manage their server-side files."""

    def __init__(
        self,
        client_socket: ClientSocket,
        on_logout: Callable[[], None],
    ) -> None:
        """Create the main file manager window.

        :param client_socket: Authenticated client socket used for file actions.
        :param on_logout: Callback used after a successful logout.
        """
        super().__init__()
        self.client_socket = client_socket
        self.on_logout = on_logout

        self.status_label = QLabel("Ready")
        self.file_table = QTableWidget(0, 3)
        self.refresh_button = QPushButton("Refresh")
        self.upload_button = QPushButton("Upload")
        self.download_button = QPushButton("Download")
        self.delete_button = QPushButton("Delete")
        self.logout_button = QPushButton("Logout")

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """Build the file manager widgets and layout."""
        self.setWindowTitle("Secure File Manager")
        self.resize(900, 620)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(28, 28, 28, 28)
        page_layout.setSpacing(18)

        header = QFrame()
        header.setObjectName("card")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 22, 24, 22)

        title_group = QVBoxLayout()
        title_label = QLabel("My Files")
        title_label.setObjectName("titleLabel")
        subtitle_label = QLabel("Upload, download, refresh, or delete files from your private area.")
        subtitle_label.setObjectName("subtitleLabel")
        title_group.addWidget(title_label)
        title_group.addWidget(subtitle_label)

        self.logout_button.setObjectName("secondaryButton")

        header_layout.addLayout(title_group)
        header_layout.addStretch()
        header_layout.addWidget(self.logout_button)

        toolbar = QHBoxLayout()
        self.refresh_button.setObjectName("secondaryButton")
        self.upload_button.setObjectName("primaryButton")
        self.download_button.setObjectName("secondaryButton")
        self.delete_button.setObjectName("dangerButton")
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.upload_button)
        toolbar.addWidget(self.download_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addStretch()

        self.file_table.setHorizontalHeaderLabels(["Filename", "Size", "Extension"])
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_table.setShowGrid(False)
        self.file_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        self.file_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.file_table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        self.status_label.setObjectName("statusLabel")

        page_layout.addWidget(header)
        page_layout.addLayout(toolbar)
        page_layout.addWidget(self.file_table)
        page_layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        """Connect file manager buttons to their handlers."""
        self.refresh_button.clicked.connect(self.refresh_files)
        self.upload_button.clicked.connect(self._handle_upload)
        self.download_button.clicked.connect(self._handle_download)
        self.delete_button.clicked.connect(self._handle_delete)
        self.logout_button.clicked.connect(self._handle_logout)

    def refresh_files(self) -> None:
        """Reload the authenticated user's file list from the server."""
        self._set_busy(True, "Refreshing files...")
        try:
            result, files = self.client_socket.list_files()
        except (ConnectionError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Refresh failed", str(exc))
            self.status_label.setText("Refresh failed.")
            return
        finally:
            self._set_busy(False)

        if not result.success:
            QMessageBox.warning(self, "Refresh failed", result.message)
            self.status_label.setText(result.message)
            return

        if files is None:
            QMessageBox.warning(self, "Refresh failed", "Server did not return a file list.")
            self.status_label.setText("Refresh failed.")
            return

        self._populate_files(files)
        self.status_label.setText(f"{len(files)} file(s) loaded.")

    def _handle_upload(self) -> None:
        """Open a native file picker and upload the chosen file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose file to upload",
            str(Path.home()),
            "All Files (*)",
        ) # opens the windows file dialog
        if not file_path:
            return

        result = self._run_file_action(
            "Upload failed",
            lambda: self.client_socket.upload_file(file_path),
        )
        if result is None:
            return

        if result.success:
            QMessageBox.information(self, "Upload complete", result.message)
            self.refresh_files()
            return

        QMessageBox.warning(self, "Upload failed", result.message)

    def _handle_download(self) -> None:
        """Download the selected server-side file to the Downloads folder."""
        filename = self._selected_filename()
        if filename is None:
            QMessageBox.information(self, "Choose a file", "Please select a file to download.")
            return

        result = self._run_file_action(
            "Download failed",
            lambda: self.client_socket.download_file(filename),
        )
        if result is None:
            return

        if result.success:
            QMessageBox.information(
                self,
                "Download complete",
                f"{result.message}\nSaved to your Downloads folder.",
            )
            return

        QMessageBox.warning(self, "Download failed", result.message)

    def _handle_delete(self) -> None:
        """Ask for confirmation and delete the selected server-side file."""
        filename = self._selected_filename()
        if filename is None:
            QMessageBox.information(self, "Choose a file", "Please select a file to delete.")
            return

        choice = QMessageBox.question(
            self,
            "Delete file?",
            f"Are you sure you want to delete '{filename}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        result = self._run_file_action(
            "Delete failed",
            lambda: self.client_socket.delete_file(filename),
        )
        if result is None:
            return

        if result.success:
            QMessageBox.information(self, "Delete complete", result.message)
            self.refresh_files()
            return

        QMessageBox.warning(self, "Delete failed", result.message)

    def _handle_logout(self) -> None:
        """Log out from the current connection and return to login."""
        self._set_busy(True, "Logging out...")
        try:
            result = self.client_socket.logout()
        except (ConnectionError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Logout failed", str(exc))
            return
        finally:
            self._set_busy(False)

        if result.success:
            self.on_logout()
            return

        QMessageBox.warning(self, "Logout failed", result.message)

    def _run_file_action(
        self,
        error_title: str,
        action: Callable[[], Result],
    ) -> Result | None:
        """Run one blocking file action and convert expected failures to popups.

        :param error_title: Message box title used when the action raises.
        :param action: Callable that performs the client socket request.
        :returns: Action result, or ``None`` when an exception was already shown.
        """
        self._set_busy(True, "Working...")
        try:
            return action()
        except (ConnectionError, FileNotFoundError, IsADirectoryError, OSError, ValueError) as exc:
            QMessageBox.critical(self, error_title, str(exc))
            self.status_label.setText(error_title)
            return None
        finally:
            self._set_busy(False)

    def _populate_files(self, files: list[dict[str, int | str]]) -> None:
        """Fill the table with server-provided file metadata.

        :param files: File metadata dictionaries returned by the server.
        """
        self.file_table.setRowCount(0) # removes all current file rows

        for row_index, file_info in enumerate(files):
            filename = str(file_info.get("filename", ""))
            size = file_info.get("size", 0)
            extension = str(file_info.get("extension", ""))

            self.file_table.insertRow(row_index)
            self.file_table.setItem(row_index, 0, self._readonly_item(filename))
            self.file_table.setItem(row_index, 1, self._readonly_item(self._format_file_size(size)))
            self.file_table.setItem(row_index, 2, self._readonly_item(extension or "(none)"))

    def _selected_filename(self) -> str | None:
        """Return the filename from the currently selected table row.

        :returns: Selected filename, or ``None`` when no row is selected.
        """
        selected_rows = self.file_table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        filename_item = self.file_table.item(selected_rows[0].row(), 0)
        if filename_item is None:
            return None
        return filename_item.text()

    def _readonly_item(self, text: str) -> QTableWidgetItem:
        """Create a non-editable table item.

        :param text: Text shown in the table cell.
        :returns: Configured table item.
        """
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _format_file_size(self, size: int | str) -> str:
        """Format a byte count for display.

        :param size: Raw size value returned by the server.
        :returns: Human-readable file size string.
        """
        try:
            byte_count = int(size)
        except (TypeError, ValueError):
            return str(size)

        if byte_count < 1024:
            return f"{byte_count} B"

        size_value = float(byte_count)
        for unit in ("KB", "MB", "GB", "TB"):
            size_value /= 1024
            if size_value < 1024:
                return f"{size_value:.1f} {unit}"

        return f"{size_value:.1f} PB"

    def _set_busy(self, is_busy: bool, message: str | None = None) -> None:
        """Toggle the file manager busy state during blocking network calls.

        :param is_busy: Whether the form should be disabled.
        :param message: Optional status text to show while busy.
        """
        for button in (
            self.refresh_button,
            self.upload_button,
            self.download_button,
            self.delete_button,
            self.logout_button,
        ):
            button.setEnabled(not is_busy)

        if message is not None:
            self.status_label.setText(message)

        if is_busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor) # changes the mouse to loading cursors
        else:
            QApplication.restoreOverrideCursor()
        QApplication.processEvents() # immediatly update the GUI
