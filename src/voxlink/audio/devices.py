"""PipeWire/PulseAudio device enumeration via pulsectl."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import pulsectl

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
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # Separate Pulse instance for event monitoring (blocking call)
        self._event_pulse: pulsectl.Pulse | None = None

    def refresh(self) -> None:
        """Re-enumerate all audio devices."""
        try:
            with pulsectl.Pulse("voxlink-enumerate") as pulse:
                sources = pulse.source_list()
                sinks = pulse.sink_list()

            self._sources = [
                AudioDevice(
                    name=s.name,
                    description=s.description,
                    is_monitor=s.monitor_of_sink != 0xFFFFFFFF
                    and s.monitor_of_sink is not None,
                )
                for s in sources
            ]
            self._sinks = [
                AudioDevice(
                    name=s.name,
                    description=s.description,
                    is_monitor=False,
                )
                for s in sinks
            ]
            logger.debug(
                "Enumerated %d sources, %d sinks",
                len(self._sources),
                len(self._sinks),
            )
        except pulsectl.PulseError:
            logger.exception("Failed to enumerate audio devices")
            self._sources = []
            self._sinks = []

    def get_sources(self) -> list[AudioDevice]:
        """Return available input devices (microphones)."""
        return list(self._sources)

    def get_sinks(self) -> list[AudioDevice]:
        """Return available output devices (speakers)."""
        return list(self._sinks)

    def start_monitoring(self) -> None:
        """Begin monitoring for device add/remove events."""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            logger.warning("Device monitoring already running")
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="device-monitor"
        )
        self._monitor_thread.start()
        logger.info("Device monitoring started")

    def stop_monitoring(self) -> None:
        """Stop monitoring for device events."""
        self._stop_event.set()
        # Interrupt the blocking event_listen call
        if self._event_pulse is not None:
            try:
                self._event_pulse.event_listen_stop()
            except Exception:
                pass
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None
        logger.info("Device monitoring stopped")

    def _monitor_loop(self) -> None:
        """Background thread: subscribe to PulseAudio events."""
        try:
            self._event_pulse = pulsectl.Pulse("voxlink-monitor")
            self._event_pulse.event_mask_set(
                pulsectl.PulseEventMaskEnum.source,
                pulsectl.PulseEventMaskEnum.sink,
            )
            self._event_pulse.event_callback_set(self._on_pulse_event)

            while not self._stop_event.is_set():
                try:
                    self._event_pulse.event_listen()
                except pulsectl.PulseDisconnected:
                    logger.warning("PulseAudio disconnected during event listen")
                    break
                # After event_listen returns (stopped by callback raising
                # PulseLoopStop), refresh and emit signal, then listen again.
                if not self._stop_event.is_set():
                    self.refresh()
                    self.devices_changed.emit()

        except Exception:
            logger.exception("Device monitor thread crashed")
        finally:
            if self._event_pulse is not None:
                try:
                    self._event_pulse.close()
                except Exception:
                    pass
                self._event_pulse = None

    def _on_pulse_event(self, event: pulsectl.PulseEventInfo) -> None:
        """Callback for PulseAudio events; stops the listen loop so we can refresh."""
        if event.facility in (
            pulsectl.PulseEventFacilityEnum.source,
            pulsectl.PulseEventFacilityEnum.sink,
        ) and event.t in (
            pulsectl.PulseEventTypeEnum.new,
            pulsectl.PulseEventTypeEnum.remove,
        ):
            logger.debug("Device event: %s %s", event.facility, event.t)
            raise pulsectl.PulseLoopStop


def list_devices_cli() -> int:
    """CLI command to list audio devices and exit."""
    dm = DeviceManager()
    dm.refresh()

    sources = dm.get_sources()
    sinks = dm.get_sinks()

    print("=== Input Devices (Sources) ===")
    if not sources:
        print("  (none found)")
    for dev in sources:
        monitor_tag = " [monitor]" if dev.is_monitor else ""
        print(f"  {dev.description}{monitor_tag}")
        print(f"    name: {dev.name}")

    print()
    print("=== Output Devices (Sinks) ===")
    if not sinks:
        print("  (none found)")
    for dev in sinks:
        print(f"  {dev.description}")
        print(f"    name: {dev.name}")

    return 0
