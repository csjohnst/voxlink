"""Mumble server client wrapping pymumble."""

from __future__ import annotations

import enum
import logging

from PySide6.QtCore import QObject, Signal

from voxlink.config import ServerConfig
from voxlink.mumble.events import MumbleEvents

logger = logging.getLogger(__name__)


class ConnectionState(enum.Enum):
    """Mumble connection state machine."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class MumbleClient(QObject):
    """Manages the lifecycle of a Mumble server connection.

    Wraps pymumble 2.0 (sourcehut fork) and bridges its callbacks
    to Qt signals for thread-safe UI updates.

    Signals:
        state_changed: Emitted when connection state changes.
        audio_received: Emitted with PCM bytes from other users.
    """

    state_changed = Signal(ConnectionState)
    audio_received = Signal(bytes)

    def __init__(
        self, config: ServerConfig, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._state = ConnectionState.DISCONNECTED
        self._mumble = None
        self.events = MumbleEvents()

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    def connect_to_server(
        self, host: str | None = None, port: int | None = None, username: str | None = None
    ) -> None:
        """Initiate connection to a Mumble server."""
        raise NotImplementedError

    def disconnect(self) -> None:
        """Disconnect from the current server."""
        raise NotImplementedError

    def send_audio(self, pcm_data: bytes) -> None:
        """Send PCM audio data to the server."""
        raise NotImplementedError

    def join_channel(self, channel_id: int) -> None:
        """Join a channel by ID."""
        raise NotImplementedError

    def get_channels(self) -> dict:
        """Return the current channel tree."""
        raise NotImplementedError

    def get_users(self) -> dict:
        """Return connected users."""
        raise NotImplementedError


def test_connection_cli(host: str, port: int, username: str) -> int:
    """CLI command to test server connection and exit."""
    raise NotImplementedError
