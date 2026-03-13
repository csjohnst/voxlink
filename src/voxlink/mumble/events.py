"""Qt signals for Mumble protocol events.

All signals are emitted from pymumble's callback thread and delivered
to the Qt main thread via Qt's signal/slot mechanism, which is inherently
thread-safe for cross-thread signal emission.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class MumbleEvents(QObject):
    """Thread-safe Qt signals bridged from pymumble callbacks.

    pymumble runs its own thread for the network loop. Callbacks registered
    with pymumble execute in that thread.  By emitting Qt signals from those
    callbacks, connected slots in the main (GUI) thread are invoked safely
    via Qt's event loop.
    """

    # Connection lifecycle
    connected = Signal()
    disconnected = Signal()
    error = Signal(str)

    # User events
    user_joined = Signal(dict)       # {"session": int, "name": str, "channel_id": int, ...}
    user_left = Signal(dict)         # {"session": int, "name": str, ...}
    user_state_changed = Signal(dict)  # {"session": int, "name": str, <changed fields>}

    # Channel events
    channel_created = Signal(dict)   # {"channel_id": int, "name": str, "parent": int, ...}
    channel_updated = Signal(dict)   # {"channel_id": int, "name": str, ...}
    channel_removed = Signal(dict)   # {"channel_id": int}

    # Audio
    audio_received = Signal(bytes)   # Raw PCM: 48kHz, 16-bit signed, mono

    def emit_connected(self) -> None:
        """Emit the connected signal (thread-safe)."""
        logger.debug("Emitting connected signal")
        self.connected.emit()

    def emit_disconnected(self) -> None:
        """Emit the disconnected signal (thread-safe)."""
        logger.debug("Emitting disconnected signal")
        self.disconnected.emit()

    def emit_error(self, message: str) -> None:
        """Emit the error signal with a description (thread-safe)."""
        logger.debug("Emitting error signal: %s", message)
        self.error.emit(message)

    def emit_user_joined(self, user_info: dict) -> None:
        """Emit user_joined with user data dict (thread-safe)."""
        logger.debug("Emitting user_joined: %s", user_info.get("name", "?"))
        self.user_joined.emit(user_info)

    def emit_user_left(self, user_info: dict) -> None:
        """Emit user_left with user data dict (thread-safe)."""
        logger.debug("Emitting user_left: %s", user_info.get("name", "?"))
        self.user_left.emit(user_info)

    def emit_user_state_changed(self, user_info: dict) -> None:
        """Emit user_state_changed with user data dict (thread-safe)."""
        logger.debug("Emitting user_state_changed: %s", user_info.get("name", "?"))
        self.user_state_changed.emit(user_info)

    def emit_channel_created(self, channel_info: dict) -> None:
        """Emit channel_created with channel data dict (thread-safe)."""
        logger.debug("Emitting channel_created: %s", channel_info.get("name", "?"))
        self.channel_created.emit(channel_info)

    def emit_channel_updated(self, channel_info: dict) -> None:
        """Emit channel_updated with channel data dict (thread-safe)."""
        logger.debug("Emitting channel_updated: %s", channel_info.get("name", "?"))
        self.channel_updated.emit(channel_info)

    def emit_channel_removed(self, channel_info: dict) -> None:
        """Emit channel_removed with channel data dict (thread-safe)."""
        logger.debug("Emitting channel_removed: %s", channel_info.get("channel_id", "?"))
        self.channel_removed.emit(channel_info)

    def emit_audio_received(self, pcm_data: bytes) -> None:
        """Emit audio_received with raw PCM bytes (thread-safe)."""
        self.audio_received.emit(pcm_data)
