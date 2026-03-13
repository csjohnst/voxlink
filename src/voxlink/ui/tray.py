"""System tray icon with status and context menu."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QSystemTrayIcon, QMainWindow

from voxlink.config import UIConfig

logger = logging.getLogger(__name__)


class TrayIcon(QSystemTrayIcon):
    """System tray icon with context menu and status indication.

    Context menu: Show/Hide, Mute, Deafen, Disconnect, Quit.
    Icon changes based on connection and voice state.
    """

    def __init__(self, main_window: QMainWindow, config: UIConfig) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self._config = config
