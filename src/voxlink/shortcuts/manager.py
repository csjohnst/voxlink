"""Shortcut method auto-detection and unified PTT interface."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from voxlink.config import PTTConfig

logger = logging.getLogger(__name__)


class ShortcutManager(QObject):
    """Manages PTT shortcut detection with automatic fallback.

    Detection order:
    1. xdg-desktop-portal GlobalShortcuts (preferred)
    2. evdev direct input (requires input group)
    3. Qt key events (window-focused only, last resort)

    Signals:
        ptt_pressed: Emitted when PTT key is pressed.
        ptt_released: Emitted when PTT key is released.
        method_changed: Emitted with the name of the active method.
    """

    ptt_pressed = Signal()
    ptt_released = Signal()
    method_changed = Signal(str)

    def __init__(self, config: PTTConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._active_method: str = "none"
        self._backend: QObject | None = None

    @property
    def active_method(self) -> str:
        """Name of the currently active shortcut method."""
        return self._active_method

    def start(self) -> None:
        """Detect and start the best available shortcut method."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop the active shortcut listener."""
        raise NotImplementedError


def test_ptt_cli() -> int:
    """CLI command to test PTT shortcut detection and exit."""
    raise NotImplementedError
