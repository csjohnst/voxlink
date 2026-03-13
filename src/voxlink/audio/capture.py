"""Microphone audio capture via PulseAudio Simple API."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from voxlink.config import AudioConfig

logger = logging.getLogger(__name__)


class CaptureManager(QObject):
    """Captures audio from a microphone in a dedicated thread.

    Signals:
        audio_captured: Emitted with raw PCM bytes (48kHz, 16-bit, mono).
        level_changed: Emitted with current RMS audio level (0.0 - 1.0).
    """

    audio_captured = Signal(bytes)
    level_changed = Signal(float)

    def __init__(self, config: AudioConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._running = False

    def start(self) -> None:
        """Start capturing audio from the configured input device."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop audio capture."""
        raise NotImplementedError

    def set_device(self, device_name: str) -> None:
        """Switch to a different input device."""
        raise NotImplementedError

    @property
    def is_capturing(self) -> bool:
        """Whether capture is currently active."""
        return self._running
