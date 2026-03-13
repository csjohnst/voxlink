"""Main application window."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QLineEdit,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from voxlink.ui.channel_tree import ChannelTree
from voxlink.ui.status_bar import StatusBar

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent
    from voxlink.audio.capture import CaptureManager
    from voxlink.audio.devices import DeviceManager
    from voxlink.audio.playback import PlaybackManager
    from voxlink.config import VoxLinkConfig
    from voxlink.mumble.client import MumbleClient
    from voxlink.shortcuts.manager import ShortcutManager

logger = logging.getLogger(__name__)


class ConnectDialog(QDialog):
    """Simple dialog asking for host, port, and username."""

    def __init__(self, host: str = "localhost", port: int = 64738, username: str = "VoxLinkUser", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Server")
        layout = QFormLayout(self)

        self.host_edit = QLineEdit(host)
        layout.addRow("Host:", self.host_edit)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(port)
        layout.addRow("Port:", self.port_spin)

        self.username_edit = QLineEdit(username)
        layout.addRow("Username:", self.username_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class MainWindow(QMainWindow):
    """VoxLink main application window.

    Layout:
    - Left: Channel tree (QTreeWidget)
    - Right: Status/info area
    - Bottom: Status bar with PTT indicator, audio levels, mute/deafen
    """

    def __init__(
        self,
        config: VoxLinkConfig,
        device_manager: DeviceManager,
        capture_manager: CaptureManager,
        playback_manager: PlaybackManager,
        mumble_client: MumbleClient,
        shortcut_manager: ShortcutManager,
    ) -> None:
        super().__init__()
        self._config = config
        self._device_manager = device_manager
        self._capture_manager = capture_manager
        self._playback_manager = playback_manager
        self._mumble_client = mumble_client
        self._shortcut_manager = shortcut_manager
        self._tray_icon = None  # set externally by app.py
        self._is_muted = False
        self._is_deafened = False
        self._setup_ui()
        self._setup_menu()
        self._setup_shortcuts()
        self._restore_geometry()

    def set_tray_icon(self, tray_icon) -> None:
        """Store reference to tray icon for minimize-to-tray behavior."""
        self._tray_icon = tray_icon

    def _setup_ui(self) -> None:
        """Initialize the window layout and widgets."""
        self.setWindowTitle("VoxLink \u2014 Disconnected")
        self.setMinimumSize(600, 400)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Splitter: channel tree (left) + info area (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._channel_tree = ChannelTree()
        self._channel_tree.channel_join_requested.connect(self._on_join_channel)
        splitter.addWidget(self._channel_tree)

        self._info_area = QTextEdit()
        self._info_area.setReadOnly(True)
        self._info_area.setPlaceholderText("Server information and events will appear here.")
        splitter.addWidget(self._info_area)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter, 1)

        # Status bar at bottom
        self._status_bar = StatusBar()
        self._status_bar.mute_toggled.connect(self._on_mute_toggled)
        self._status_bar.deafen_toggled.connect(self._on_deafen_toggled)
        main_layout.addWidget(self._status_bar)

    def _setup_menu(self) -> None:
        """Build the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        connect_action = QAction("&Connect...", self)
        connect_action.setToolTip("Connect to a Mumble server")
        connect_action.triggered.connect(self._show_connect_dialog)
        file_menu.addAction(connect_action)

        disconnect_action = QAction("&Disconnect", self)
        disconnect_action.setToolTip("Disconnect from the current server")
        disconnect_action.triggered.connect(self._disconnect)
        file_menu.addAction(disconnect_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self._quit)
        file_menu.addAction(quit_action)

        # Settings menu
        settings_menu = menubar.addMenu("&Settings")
        prefs_action = QAction("&Preferences...", self)
        prefs_action.setToolTip("Open settings dialog")
        prefs_action.triggered.connect(self._show_settings)
        settings_menu.addAction(prefs_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About VoxLink", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_shortcuts(self) -> None:
        """Register keyboard shortcuts."""
        # Ctrl+M = toggle mute
        mute_shortcut = QAction("Toggle Mute", self)
        mute_shortcut.setShortcut(QKeySequence("Ctrl+M"))
        mute_shortcut.triggered.connect(self._toggle_mute)
        self.addAction(mute_shortcut)

        # Ctrl+D = toggle deafen
        deafen_shortcut = QAction("Toggle Deafen", self)
        deafen_shortcut.setShortcut(QKeySequence("Ctrl+D"))
        deafen_shortcut.triggered.connect(self._toggle_deafen)
        self.addAction(deafen_shortcut)

    def _restore_geometry(self) -> None:
        settings = QSettings("VoxLink", "VoxLink")
        geometry = settings.value("main_window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def _save_geometry(self) -> None:
        settings = QSettings("VoxLink", "VoxLink")
        settings.setValue("main_window/geometry", self.saveGeometry())

    # ---- Properties ----

    @property
    def channel_tree(self) -> ChannelTree:
        return self._channel_tree

    @property
    def status_bar_widget(self) -> StatusBar:
        return self._status_bar

    # ---- Slots: connection events ----

    def on_connected(self) -> None:
        """Handle successful server connection."""
        self.setWindowTitle("VoxLink \u2014 Connected")
        self._status_bar.set_connection_status("Connected")
        self._info_area.append("Connected to server.")

        # Populate channel tree
        channels = self._mumble_client.get_channels()
        users = self._mumble_client.get_users()
        self._channel_tree.update_channels(channels, users)

    def on_disconnected(self) -> None:
        """Handle server disconnection."""
        self.setWindowTitle("VoxLink \u2014 Disconnected")
        self._status_bar.set_connection_status("Disconnected")
        self._channel_tree.clear()
        self._channel_tree.setHeaderLabel("Channels")
        self._info_area.append("Disconnected from server.")

    def on_error(self, message: str) -> None:
        """Handle connection error."""
        logger.error("Connection error: %s", message)
        self._status_bar.set_connection_status(f"Error: {message}")
        self._info_area.append(f"Error: {message}")

    def on_channel_updated(self, channel_data: dict) -> None:
        """Handle channel tree update."""
        channels = self._mumble_client.get_channels()
        users = self._mumble_client.get_users()
        self._channel_tree.update_channels(channels, users)

    def on_user_joined(self, user_data: dict) -> None:
        """Handle user joining."""
        name = user_data.get("name", "Unknown")
        self._info_area.append(f"User joined: {name}")
        self._channel_tree.add_user(user_data)

    def on_user_left(self, user_data: dict) -> None:
        """Handle user leaving."""
        name = user_data.get("name", "Unknown")
        self._info_area.append(f"User left: {name}")
        self._channel_tree.remove_user(user_data)

    # ---- Actions ----

    def _show_connect_dialog(self) -> None:
        dlg = ConnectDialog(
            host=self._config.server.host,
            port=self._config.server.port,
            username=self._config.server.username,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            host = dlg.host_edit.text().strip()
            port = dlg.port_spin.value()
            username = dlg.username_edit.text().strip()
            if host and username:
                self._info_area.append(f"Connecting to {host}:{port} as {username}...")
                self._status_bar.set_connection_status("Connecting...")
                self._mumble_client.connect_to_server(host, port, username)

    def _disconnect(self) -> None:
        self._mumble_client.disconnect()

    def _quit(self) -> None:
        self._save_geometry()
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()  # type: ignore[union-attr]

    def _show_settings(self) -> None:
        from voxlink.ui.settings import SettingsDialog
        dlg = SettingsDialog(self._config, self._device_manager, parent=self)
        dlg.exec()

    def _show_about(self) -> None:
        from voxlink import __version__

        QMessageBox.about(
            self,
            "About VoxLink",
            f"VoxLink v{__version__}\n\n"
            "Wayland-native Mumble voice chat client\n"
            "Built with PySide6 and pymumble.",
        )

    def _on_join_channel(self, channel_id: int) -> None:
        self._mumble_client.join_channel(channel_id)

    def _toggle_mute(self) -> None:
        self._is_muted = not self._is_muted
        self._status_bar.set_muted(self._is_muted)

    def _toggle_deafen(self) -> None:
        self._is_deafened = not self._is_deafened
        self._status_bar.set_deafened(self._is_deafened)

    def _on_mute_toggled(self, muted: bool) -> None:
        self._is_muted = muted
        logger.info("Mute toggled: %s", muted)

    def _on_deafen_toggled(self, deafened: bool) -> None:
        self._is_deafened = deafened
        logger.info("Deafen toggled: %s", deafened)

    # ---- Window events ----

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Minimize to tray on close if tray is enabled, otherwise quit."""
        self._save_geometry()
        if self._tray_icon is not None and self._tray_icon.should_minimize_to_tray():
            event.ignore()
            self.hide()
        else:
            event.accept()
