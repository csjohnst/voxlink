"""xdg-desktop-portal GlobalShortcuts interface via D-Bus."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class PortalShortcuts(QObject):
    """Binds global shortcuts via the xdg-desktop-portal GlobalShortcuts API.

    Uses dbus-next to communicate with the portal. Runs the asyncio
    event loop in a dedicated thread.

    Signals:
        activated: Emitted when the bound shortcut key is pressed.
        deactivated: Emitted when the bound shortcut key is released.
        available_changed: Emitted when portal availability changes.
    """

    activated = Signal()
    deactivated = Signal()
    available_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._session = None
        self._running = False

    @staticmethod
    def is_available() -> bool:
        """Check if the GlobalShortcuts portal is available."""
        raise NotImplementedError

    def start(self) -> None:
        """Create a session and bind shortcuts."""
        raise NotImplementedError

    def stop(self) -> None:
        """Close the session and clean up."""
        raise NotImplementedError
