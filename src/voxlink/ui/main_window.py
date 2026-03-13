"""Main application window using Fluent Design."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter,
)
from qfluentwidgets import (
    FluentWindow, FluentIcon, NavigationItemPosition,
    TextEdit, LineEdit, SpinBox,
    SubtitleLabel, BodyLabel,
    MessageBox,
    InfoBar, InfoBarPosition,
    SimpleCardWidget,
)
from qfluentwidgets.components.dialog_box.message_box_base import MessageBoxBase

from voxlink.ui.channel_tree import ChannelTree
from voxlink.ui.compact_overlay import CompactOverlay
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


class ServerPage(QWidget):
    """Main server interaction page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("serverPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        # Splitter with channel tree and info area
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.channel_tree = ChannelTree()
        splitter.addWidget(self.channel_tree)

        # Info area in a card
        info_card = SimpleCardWidget()
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(12, 12, 12, 12)
        header = SubtitleLabel("Server")
        info_layout.addWidget(header)
        self.info_area = TextEdit()
        self.info_area.setReadOnly(True)
        self.info_area.setPlaceholderText("Server information and events will appear here.")
        info_layout.addWidget(self.info_area)
        splitter.addWidget(info_card)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        # Status bar at bottom
        self.status_bar = StatusBar()
        layout.addWidget(self.status_bar)


class ConnectDialog(MessageBoxBase):
    """Fluent-styled connect dialog."""

    def __init__(self, host="localhost", port=64738, username="VoxLinkUser", parent=None):
        super().__init__(parent)

        self.viewLayout.addWidget(SubtitleLabel("Connect to Server"))

        self.host_edit = LineEdit()
        self.host_edit.setPlaceholderText("Server address")
        self.host_edit.setText(host)
        self.host_edit.setClearButtonEnabled(True)

        self.port_spin = SpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(port)

        self.username_edit = LineEdit()
        self.username_edit.setPlaceholderText("Username")
        self.username_edit.setText(username)
        self.username_edit.setClearButtonEnabled(True)

        self.viewLayout.addWidget(BodyLabel("Host"))
        self.viewLayout.addWidget(self.host_edit)
        self.viewLayout.addWidget(BodyLabel("Port"))
        self.viewLayout.addWidget(self.port_spin)
        self.viewLayout.addWidget(BodyLabel("Username"))
        self.viewLayout.addWidget(self.username_edit)

        self.yesButton.setText("Connect")
        self.cancelButton.setText("Cancel")

        self.widget.setMinimumWidth(360)


class _SettingsPagePlaceholder(QWidget):
    """Placeholder settings page until the real one is written."""

    def __init__(self, config, device_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        layout = QVBoxLayout(self)
        layout.addWidget(SubtitleLabel("Settings"))
        layout.addWidget(BodyLabel("Settings page will be available in a future update."))
        layout.addStretch()


class MainWindow(FluentWindow):
    """VoxLink main application window using Fluent Design with sidebar navigation."""

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
        self._tray_icon = None
        self._is_muted = False
        self._is_deafened = False
        self._compact_overlay = CompactOverlay()
        self._compact_overlay.restore_requested.connect(self._restore_from_compact)

        # Setup
        self.setWindowTitle("VoxLink")
        self.setMinimumSize(700, 500)

        # Create pages
        self._server_page = ServerPage()
        self._server_page.channel_tree.channel_join_requested.connect(self._on_join_channel)
        self._server_page.status_bar.mute_toggled.connect(self._on_mute_toggled)
        self._server_page.status_bar.deafen_toggled.connect(self._on_deafen_toggled)

        # Settings page - try to import the real one, fall back to placeholder
        try:
            from voxlink.ui.settings import SettingsPage
            self._settings_page = SettingsPage(config, device_manager)
        except ImportError:
            self._settings_page = _SettingsPagePlaceholder(config, device_manager)

        # Add navigation items
        self.addSubInterface(self._server_page, FluentIcon.MICROPHONE, "Server")

        # Add connect/disconnect to nav
        self.navigationInterface.addItem(
            routeKey="connect",
            icon=FluentIcon.LINK,
            text="Connect",
            onClick=self._show_connect_dialog,
            selectable=False,
            position=NavigationItemPosition.TOP,
        )
        self.navigationInterface.addItem(
            routeKey="disconnect",
            icon=FluentIcon.CLOSE,
            text="Disconnect",
            onClick=self._disconnect,
            selectable=False,
            position=NavigationItemPosition.TOP,
        )

        self.addSubInterface(
            self._settings_page, FluentIcon.SETTING, "Settings",
            position=NavigationItemPosition.BOTTOM,
        )

        # Compact mode toggle in nav
        self.navigationInterface.addItem(
            routeKey="compact",
            icon=FluentIcon.MINIMIZE,
            text="Compact",
            onClick=self._enter_compact_mode,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        # About in bottom nav
        self.navigationInterface.addItem(
            routeKey="about",
            icon=FluentIcon.INFO,
            text="About",
            onClick=self._show_about,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        self._restore_geometry()

    # ---- Properties for external wiring ----

    @property
    def channel_tree(self) -> ChannelTree:
        return self._server_page.channel_tree

    @property
    def status_bar_widget(self) -> StatusBar:
        return self._server_page.status_bar

    @property
    def compact_overlay(self) -> CompactOverlay:
        return self._compact_overlay

    def set_tray_icon(self, tray_icon) -> None:
        """Store reference to tray icon for minimize-to-tray behavior."""
        self._tray_icon = tray_icon

    # ---- Slots: connection events ----

    def on_connected(self) -> None:
        """Handle successful server connection."""
        self.setWindowTitle("VoxLink — Connected")
        self._server_page.status_bar.set_connection_status("Connected")
        self._server_page.info_area.append("Connected to server.")
        InfoBar.success(
            "Connected", "Successfully connected to server",
            parent=self, duration=3000, position=InfoBarPosition.TOP,
        )
        self._refresh_tree()
        # Refresh again after a short delay to pick up late-arriving user data
        QTimer.singleShot(1000, self._refresh_tree)

    def _refresh_tree(self) -> None:
        """Rebuild the channel tree from the current server state."""
        channels = self._mumble_client.get_channels()
        users = self._mumble_client.get_users()
        logger.info("Refreshing tree: %d channels, %d users", len(channels), len(users))
        logger.debug("Channels: %s", channels)
        logger.debug("Users: %s", users)
        self._server_page.channel_tree.update_channels(channels, users)

    def on_disconnected(self) -> None:
        """Handle server disconnection."""
        self.setWindowTitle("VoxLink — Disconnected")
        self._server_page.status_bar.set_connection_status("Disconnected")
        self._server_page.channel_tree.clear()
        self._server_page.channel_tree.setHeaderLabel("Channels")
        self._server_page.info_area.append("Disconnected from server.")
        self._compact_overlay.clear_users()

    def on_error(self, message: str) -> None:
        """Handle connection error."""
        logger.error("Connection error: %s", message)
        self._server_page.status_bar.set_connection_status(f"Error: {message}")
        self._server_page.info_area.append(f"Error: {message}")
        InfoBar.error(
            "Error", message,
            parent=self, duration=5000, position=InfoBarPosition.TOP,
        )

    def on_channel_updated(self, channel_data: dict) -> None:
        """Handle channel tree update."""
        self._refresh_tree()

    def on_user_joined(self, user_data: dict) -> None:
        """Handle user joining."""
        name = user_data.get("name", "Unknown")
        session = user_data.get("session")
        self._server_page.info_area.append(f"User joined: {name}")
        self._refresh_tree()
        if session is not None:
            self._compact_overlay.add_user(session, name)

    def on_user_left(self, user_data: dict) -> None:
        """Handle user leaving."""
        name = user_data.get("name", "Unknown")
        session = user_data.get("session")
        self._server_page.info_area.append(f"User left: {name}")
        self._server_page.channel_tree.remove_user(user_data)
        if session is not None:
            self._compact_overlay.remove_user(session)

    # ---- Actions ----

    def _show_connect_dialog(self) -> None:
        dlg = ConnectDialog(
            host=self._config.server.host,
            port=self._config.server.port,
            username=self._config.server.username,
            parent=self,
        )
        if dlg.exec():
            host = dlg.host_edit.text().strip()
            port = dlg.port_spin.value()
            username = dlg.username_edit.text().strip()
            if host and username:
                self._server_page.info_area.append(f"Connecting to {host}:{port} as {username}...")
                self._server_page.status_bar.set_connection_status("Connecting...")
                self._mumble_client.connect_to_server(host, port, username)

    def _disconnect(self) -> None:
        self._mumble_client.disconnect()

    def _show_about(self) -> None:
        from voxlink import __version__
        MessageBox(
            "About VoxLink",
            f"VoxLink v{__version__}\n\nWayland-native Mumble voice chat client.\n"
            "Built with PySide6, pymumble, and Fluent Design.",
            self,
        ).exec()

    def _on_join_channel(self, channel_id: int) -> None:
        self._mumble_client.join_channel(channel_id)

    def _toggle_mute(self) -> None:
        self._is_muted = not self._is_muted
        self._server_page.status_bar.set_muted(self._is_muted)

    def _toggle_deafen(self) -> None:
        self._is_deafened = not self._is_deafened
        self._server_page.status_bar.set_deafened(self._is_deafened)

    def _enter_compact_mode(self) -> None:
        """Switch to compact floating overlay."""
        self._save_geometry()
        self.hide()
        # Sync current users to overlay
        users = self._mumble_client.get_users()
        self._compact_overlay.set_users(users)
        self._compact_overlay.show()

    def _restore_from_compact(self) -> None:
        """Restore from compact overlay to full window."""
        self._compact_overlay.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_mute_toggled(self, muted: bool) -> None:
        self._is_muted = muted
        if muted:
            self._capture_manager.stop()
        # Don't auto-start capture on unmute - PTT controls that
        logger.info("Mute %s", "enabled" if muted else "disabled")

    def _on_deafen_toggled(self, deafened: bool) -> None:
        self._is_deafened = deafened
        # Store the deafen state; the app.py audio_received handler checks it
        logger.info("Deafen %s", "enabled" if deafened else "disabled")

    def _restore_geometry(self) -> None:
        settings = QSettings("VoxLink", "VoxLink")
        geometry = settings.value("main_window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def _save_geometry(self) -> None:
        settings = QSettings("VoxLink", "VoxLink")
        settings.setValue("main_window/geometry", self.saveGeometry())

    # ---- Window events ----

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Minimize to tray on close if tray is enabled, otherwise quit."""
        self._save_geometry()
        if self._tray_icon is not None and self._tray_icon.should_minimize_to_tray():
            event.ignore()
            self.hide()
        else:
            event.accept()
