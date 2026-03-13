"""Main application window."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMainWindow

if TYPE_CHECKING:
    from voxlink.audio.capture import CaptureManager
    from voxlink.audio.devices import DeviceManager
    from voxlink.audio.playback import PlaybackManager
    from voxlink.config import VoxLinkConfig
    from voxlink.mumble.client import MumbleClient
    from voxlink.shortcuts.manager import ShortcutManager

logger = logging.getLogger(__name__)


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
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize the window layout and widgets."""
        self.setWindowTitle("VoxLink — Disconnected")
        self.setMinimumSize(600, 400)

    def on_connected(self) -> None:
        """Handle successful server connection."""
        self.setWindowTitle("VoxLink — Connected")

    def on_disconnected(self) -> None:
        """Handle server disconnection."""
        self.setWindowTitle("VoxLink — Disconnected")

    def on_error(self, message: str) -> None:
        """Handle connection error."""
        logger.error("Connection error: %s", message)

    def on_channel_updated(self, channel_data: dict) -> None:
        """Handle channel tree update."""
        pass

    def on_user_joined(self, user_data: dict) -> None:
        """Handle user joining."""
        pass

    def on_user_left(self, user_data: dict) -> None:
        """Handle user leaving."""
        pass
