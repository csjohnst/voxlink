"""Qt signals for Mumble protocol events."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class MumbleEvents(QObject):
    """Thread-safe Qt signals bridged from pymumble callbacks.

    All signals are emitted from pymumble's callback thread and
    delivered to the Qt main thread via the signal/slot mechanism.
    """

    connected = Signal()
    disconnected = Signal()
    error = Signal(str)
    user_joined = Signal(dict)
    user_left = Signal(dict)
    user_state_changed = Signal(dict)
    channel_updated = Signal(dict)
    audio_received = Signal(bytes)
