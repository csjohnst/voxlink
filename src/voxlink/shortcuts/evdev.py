"""Fallback evdev-based global shortcut listener."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class EvdevShortcuts(QObject):
    """Listens for key events via evdev as a fallback shortcut method.

    Requires the user to be in the 'input' group.

    Signals:
        activated: Emitted when the configured key is pressed.
        deactivated: Emitted when the configured key is released.
    """

    activated = Signal()
    deactivated = Signal()

    def __init__(self, key_name: str = "KEY_F13", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._key_name = key_name
        self._running = False

    @staticmethod
    def is_available() -> bool:
        """Check if evdev input devices are accessible."""
        raise NotImplementedError

    def start(self) -> None:
        """Begin listening for key events in a background thread."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop the listener thread."""
        raise NotImplementedError
