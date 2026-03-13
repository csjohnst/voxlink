"""Settings dialog with tabbed configuration."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QDialog

from voxlink.config import VoxLinkConfig

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Settings dialog with tabs for Audio, Voice, Connection, and General.

    Tabs:
    - Audio: Input/output device selection, volume sliders, test button
    - Voice: PTT/VAD/Continuous mode, key binding, VAD sensitivity
    - Connection: Server list management, username, password
    - General: Start minimized, tray icon, compact mode
    """

    def __init__(self, config: VoxLinkConfig, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("VoxLink Settings")
