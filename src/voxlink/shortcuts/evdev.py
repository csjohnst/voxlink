"""Fallback evdev-based global shortcut listener."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

# Try to import evdev; it may not be installed
try:
    import evdev
    import evdev.ecodes as ecodes

    _HAS_EVDEV = True
except ImportError:
    _HAS_EVDEV = False
    evdev = None  # type: ignore[assignment]
    ecodes = None  # type: ignore[assignment]


class EvdevShortcuts(QObject):
    """Listens for key events via evdev as a fallback shortcut method.

    Requires the user to be in the 'input' group.

    Signals:
        activated: Emitted when the configured key is pressed.
        deactivated: Emitted when the configured key is released.
    """

    activated = Signal()
    deactivated = Signal()

    def __init__(
        self, key_name: str = "KEY_F13", parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._key_name = key_name
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @staticmethod
    def is_available() -> bool:
        """Check if evdev input devices are accessible.

        Returns True if evdev is importable and at least one
        /dev/input/event* device can be opened for reading.
        """
        if not _HAS_EVDEV:
            logger.debug("evdev module not available")
            return False

        input_dir = Path("/dev/input")
        if not input_dir.exists():
            return False

        for entry in input_dir.iterdir():
            if entry.name.startswith("event"):
                if os.access(str(entry), os.R_OK):
                    return True

        logger.debug("No readable /dev/input/event* devices found")
        return False

    def start(self) -> None:
        """Begin listening for key events in a background thread."""
        if self._running:
            return

        if not _HAS_EVDEV:
            logger.error("Cannot start evdev shortcuts: evdev not installed")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._listen_loop,
            name="evdev-shortcuts",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the listener thread."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _get_key_code(self) -> int | None:
        """Resolve the configured key name to an evdev key code."""
        if ecodes is None:
            return None
        code = getattr(ecodes, self._key_name, None)
        if code is None:
            logger.error("Unknown evdev key name: %s", self._key_name)
        return code

    def _find_keyboard_devices(self) -> list[Any]:
        """Find all evdev devices that have EV_KEY capability."""
        assert evdev is not None
        devices = []
        input_dir = Path("/dev/input")
        for entry in sorted(input_dir.iterdir()):
            if not entry.name.startswith("event"):
                continue
            try:
                dev = evdev.InputDevice(str(entry))
                capabilities = dev.capabilities()
                # EV_KEY = 1
                if 1 in capabilities:
                    devices.append(dev)
                else:
                    dev.close()
            except (PermissionError, OSError):
                continue
        return devices

    def _listen_loop(self) -> None:
        """Main loop running in the background thread, reading key events."""
        import select

        assert evdev is not None

        key_code = self._get_key_code()
        if key_code is None:
            self._running = False
            return

        devices = self._find_keyboard_devices()
        if not devices:
            logger.error("No keyboard devices found for evdev shortcuts")
            self._running = False
            return

        logger.info(
            "evdev listening on %d device(s) for %s (code %d)",
            len(devices),
            self._key_name,
            key_code,
        )

        device_map = {dev.fd: dev for dev in devices}

        try:
            while not self._stop_event.is_set():
                # Use select with a timeout so we can check _stop_event
                r, _, _ = select.select(
                    list(device_map.keys()), [], [], 0.5
                )
                for fd in r:
                    dev = device_map.get(fd)
                    if dev is None:
                        continue
                    try:
                        for event in dev.read():
                            # EV_KEY = 1
                            if event.type != 1:
                                continue
                            if event.code != key_code:
                                continue
                            # value: 0=release, 1=press, 2=repeat
                            if event.value == 1:
                                logger.debug("evdev key pressed: %s", self._key_name)
                                self.activated.emit()
                            elif event.value == 0:
                                logger.debug("evdev key released: %s", self._key_name)
                                self.deactivated.emit()
                    except OSError:
                        logger.warning(
                            "Lost evdev device %s", dev.path, exc_info=True
                        )
                        try:
                            dev.close()
                        except Exception:
                            pass
                        del device_map[fd]
                        if not device_map:
                            logger.error("All evdev devices lost")
                            break
        finally:
            for dev in device_map.values():
                try:
                    dev.close()
                except Exception:
                    pass
            self._running = False
