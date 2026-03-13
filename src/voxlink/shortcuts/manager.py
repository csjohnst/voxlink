"""Shortcut method auto-detection and unified PTT interface."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, Signal

from voxlink.config import PTTConfig

logger = logging.getLogger(__name__)


class ShortcutManager(QObject):
    """Manages PTT shortcut detection with automatic fallback.

    Detection order:
    1. xdg-desktop-portal GlobalShortcuts (preferred)
    2. evdev direct input (requires input group)
    3. Qt key events (window-focused only, last resort)

    Signals:
        ptt_pressed: Emitted when PTT key is pressed.
        ptt_released: Emitted when PTT key is released.
        method_changed: Emitted with the name of the active method.
    """

    ptt_pressed = Signal()
    ptt_released = Signal()
    method_changed = Signal(str)

    def __init__(self, config: PTTConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._active_method: str = "none"
        self._backend: QObject | None = None

    @property
    def active_method(self) -> str:
        """Name of the currently active shortcut method."""
        return self._active_method

    def start(self) -> None:
        """Detect and start the best available shortcut method."""
        if self._backend is not None:
            self.stop()

        method = self._config.shortcut_method

        # If method is "auto" or "portal", try portal first
        if method in ("auto", "portal"):
            if self._try_portal():
                return

        # If method is "auto" or "evdev", try evdev next
        if method in ("auto", "evdev"):
            if self._try_evdev():
                return

        # Last resort: Qt-based (window-focused only)
        if method in ("auto", "qt"):
            self._start_qt_fallback()
            return

        # If a specific method was requested and it failed
        if method not in ("auto",):
            logger.warning(
                "Requested shortcut method '%s' is not available; "
                "falling back to auto-detection",
                method,
            )
            # Re-run with auto logic
            if self._try_portal():
                return
            if self._try_evdev():
                return
            self._start_qt_fallback()

    def stop(self) -> None:
        """Stop the active shortcut listener."""
        if self._backend is None:
            return

        try:
            # Disconnect signals
            self._backend.activated.disconnect(self.ptt_pressed)  # type: ignore[attr-defined]
            self._backend.deactivated.disconnect(self.ptt_released)  # type: ignore[attr-defined]
        except (RuntimeError, TypeError):
            pass

        if hasattr(self._backend, "stop"):
            self._backend.stop()  # type: ignore[attr-defined]

        self._backend = None
        self._active_method = "none"

    def _try_portal(self) -> bool:
        """Attempt to start the portal shortcuts backend."""
        from voxlink.shortcuts.portal import PortalShortcuts

        try:
            if not PortalShortcuts.is_available():
                logger.info("Portal shortcuts not available")
                return False
        except Exception:
            logger.debug("Portal availability check raised", exc_info=True)
            return False

        backend = PortalShortcuts(parent=self)
        backend.activated.connect(self.ptt_pressed)
        backend.deactivated.connect(self.ptt_released)
        backend.available_changed.connect(self._on_portal_availability_changed)

        try:
            backend.start()
        except Exception:
            logger.error("Failed to start portal shortcuts", exc_info=True)
            return False

        self._backend = backend
        self._active_method = "portal"
        self.method_changed.emit("portal")
        logger.info("Using portal shortcuts")
        return True

    def _try_evdev(self) -> bool:
        """Attempt to start the evdev shortcuts backend."""
        from voxlink.shortcuts.evdev import EvdevShortcuts

        try:
            if not EvdevShortcuts.is_available():
                logger.info("evdev shortcuts not available")
                return False
        except Exception:
            logger.debug("evdev availability check raised", exc_info=True)
            return False

        backend = EvdevShortcuts(
            key_name=self._config.evdev_key, parent=self
        )
        backend.activated.connect(self.ptt_pressed)
        backend.deactivated.connect(self.ptt_released)

        try:
            backend.start()
        except Exception:
            logger.error("Failed to start evdev shortcuts", exc_info=True)
            return False

        self._backend = backend
        self._active_method = "evdev"
        self.method_changed.emit("evdev")
        logger.info("Using evdev shortcuts (key=%s)", self._config.evdev_key)
        return True

    def _start_qt_fallback(self) -> None:
        """Use a minimal Qt-based fallback (window-focused only)."""
        self._active_method = "qt"
        self.method_changed.emit("qt")
        logger.info(
            "Using Qt key events (window-focused only) - "
            "global shortcuts unavailable"
        )
        # Qt key event handling is done at the widget level;
        # the manager just records that this is the active method.
        # The UI layer should install an event filter when method is "qt".

    def _on_portal_availability_changed(self, available: bool) -> None:
        """Handle portal session being revoked."""
        if not available and self._active_method == "portal":
            logger.warning("Portal session lost; switching to fallback")
            self.stop()
            # Try evdev, then Qt
            if not self._try_evdev():
                self._start_qt_fallback()


def test_ptt_cli() -> int:
    """CLI command to test PTT shortcut detection and exit.

    Detects the best available method, registers a test shortcut,
    and prints PRESSED / RELEASED until Ctrl+C.
    """
    from PySide6.QtCore import QCoreApplication

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = QCoreApplication.instance()
    owns_app = False
    if app is None:
        app = QCoreApplication(sys.argv)
        owns_app = True

    config = PTTConfig()
    manager = ShortcutManager(config)

    def on_pressed() -> None:
        print("PRESSED")

    def on_released() -> None:
        print("RELEASED")

    manager.ptt_pressed.connect(on_pressed)
    manager.ptt_released.connect(on_released)
    manager.method_changed.connect(
        lambda m: print(f"Active shortcut method: {m}")
    )

    print("Detecting shortcut method...")
    manager.start()
    print(f"Method: {manager.active_method}")
    print("Press PTT key to test (Ctrl+C to exit)...")

    if owns_app:
        try:
            return app.exec()
        except KeyboardInterrupt:
            print("\nStopping...")
            manager.stop()
            return 0
    return 0
