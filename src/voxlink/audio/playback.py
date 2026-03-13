"""Speaker audio playback via PulseAudio Simple API."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from voxlink.config import AudioConfig

logger = logging.getLogger(__name__)


class PlaybackManager(QObject):
    """Plays audio through speakers in a dedicated thread.

    Signals:
        level_changed: Emitted with current output RMS level (0.0 - 1.0).
    """

    level_changed = Signal(float)

    def __init__(self, config: AudioConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config

    def play(self, pcm_data: bytes) -> None:
        """Queue PCM audio data for playback."""
        raise NotImplementedError

    def set_device(self, device_name: str) -> None:
        """Switch to a different output device."""
        raise NotImplementedError

    def start(self) -> None:
        """Initialize the playback stream."""
        raise NotImplementedError

    def stop(self) -> None:
        """Close the playback stream."""
        raise NotImplementedError
