"""System tray icon with Fluent-styled context menu."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap, QPainter, QBrush
from PySide6.QtWidgets import QMainWindow, QSystemTrayIcon

from qfluentwidgets import SystemTrayMenu, Action, FluentIcon, isDarkTheme

from voxlink.config import UIConfig

logger = logging.getLogger(__name__)


def _make_tray_icon(color: QColor, size: int = 22) -> QIcon:
    """Generate a simple colored circle icon for the tray."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    """System tray icon with context menu and status indication.

    Context menu: Show/Hide, Mute, Deafen, Disconnect, Quit.
    Icon changes based on connection and voice state.
    """

    def __init__(self, main_window: QMainWindow, config: UIConfig) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self._config = config

        # State icons
        self._icon_disconnected = _make_tray_icon(QColor(158, 158, 158))
        self._icon_connected = _make_tray_icon(QColor(76, 175, 80))
        self._icon_talking = _make_tray_icon(QColor(0, 230, 64))
        self._icon_muted = _make_tray_icon(QColor(244, 67, 54))

        self.setIcon(self._icon_disconnected)
        self.setToolTip("VoxLink - Disconnected")

        self._setup_menu()
        self.activated.connect(self._on_activated)

    def _setup_menu(self) -> None:
        menu = SystemTrayMenu(parent=self._main_window)

        self._show_action = Action(FluentIcon.FULL_SCREEN, "Show", parent=menu)
        self._show_action.triggered.connect(self._toggle_window)
        menu.addAction(self._show_action)

        menu.addSeparator()

        self._mute_action = Action(FluentIcon.MUTE, "Mute", parent=menu)
        self._mute_action.setCheckable(True)
        menu.addAction(self._mute_action)

        self._deafen_action = Action(FluentIcon.HEADPHONE, "Deafen", parent=menu)
        self._deafen_action.setCheckable(True)
        menu.addAction(self._deafen_action)

        menu.addSeparator()

        self._disconnect_action = Action(FluentIcon.CLOSE, "Disconnect", parent=menu)
        menu.addAction(self._disconnect_action)

        self._quit_action = Action(FluentIcon.POWER_BUTTON, "Quit", parent=menu)
        menu.addAction(self._quit_action)

        self.setContextMenu(menu)

    # ---- Public accessors for wiring signals ----

    @property
    def mute_action(self) -> Action:
        return self._mute_action

    @property
    def deafen_action(self) -> Action:
        return self._deafen_action

    @property
    def disconnect_action(self) -> Action:
        return self._disconnect_action

    @property
    def quit_action(self) -> Action:
        return self._quit_action

    # ---- Icon state changes ----

    def set_connected(self) -> None:
        self.setIcon(self._icon_connected)
        self.setToolTip("VoxLink - Connected")

    def set_disconnected(self) -> None:
        self.setIcon(self._icon_disconnected)
        self.setToolTip("VoxLink - Disconnected")

    def set_talking(self, talking: bool) -> None:
        if talking:
            self.setIcon(self._icon_talking)
        else:
            self.setIcon(self._icon_connected)

    def set_muted(self) -> None:
        self.setIcon(self._icon_muted)
        self.setToolTip("VoxLink - Muted")

    # ---- Interaction ----

    def _toggle_window(self) -> None:
        if self._main_window.isVisible():
            self._main_window.hide()
            self._show_action.setText("Show")
        else:
            self._main_window.show()
            self._main_window.raise_()
            self._main_window.activateWindow()
            self._show_action.setText("Hide")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def should_minimize_to_tray(self) -> bool:
        """Return True if the window should minimize to tray instead of closing."""
        return self._config.show_tray_icon
