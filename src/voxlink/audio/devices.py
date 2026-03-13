"""PipeWire/PulseAudio device enumeration via pulsectl."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


@dataclass
class AudioDevice:
    """Represents an audio input or output device."""

    name: str
    description: str
    is_monitor: bool = False


class DeviceManager(QObject):
    """Enumerates and monitors PipeWire audio devices.

    Signals:
        devices_changed: Emitted when devices are added or removed.
    """

    devices_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sources: list[AudioDevice] = []
        self._sinks: list[AudioDevice] = []

    def refresh(self) -> None:
        """Re-enumerate all audio devices."""
        raise NotImplementedError

    def get_sources(self) -> list[AudioDevice]:
        """Return available input devices (microphones)."""
        return list(self._sources)

    def get_sinks(self) -> list[AudioDevice]:
        """Return available output devices (speakers)."""
        return list(self._sinks)

    def start_monitoring(self) -> None:
        """Begin monitoring for device add/remove events."""
        raise NotImplementedError

    def stop_monitoring(self) -> None:
        """Stop monitoring for device events."""
        raise NotImplementedError


def list_devices_cli() -> int:
    """CLI command to list audio devices and exit."""
    raise NotImplementedError
