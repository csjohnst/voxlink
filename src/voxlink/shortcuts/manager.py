"""Shortcut method auto-detection and unified PTT interface."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, Signal

from voxlink.config import PTTConfig

logger = logging.getLogger(__name__)


# Map evdev key names to Qt key codes for the Qt fallback
_EVDEV_TO_QT: dict[str, int] = {
    "KEY_F1": Qt.Key.Key_F1, "KEY_F2": Qt.Key.Key_F2,
    "KEY_F3": Qt.Key.Key_F3, "KEY_F4": Qt.Key.Key_F4,
    "KEY_F5": Qt.Key.Key_F5, "KEY_F6": Qt.Key.Key_F6,
    "KEY_F7": Qt.Key.Key_F7, "KEY_F8": Qt.Key.Key_F8,
    "KEY_F9": Qt.Key.Key_F9, "KEY_F10": Qt.Key.Key_F10,
    "KEY_F11": Qt.Key.Key_F11, "KEY_F12": Qt.Key.Key_F12,
    "KEY_F13": Qt.Key.Key_F13, "KEY_F14": Qt.Key.Key_F14,
    "KEY_F15": Qt.Key.Key_F15, "KEY_F16": Qt.Key.Key_F16,
    "KEY_SPACE": Qt.Key.Key_Space,
    "KEY_CAPSLOCK": Qt.Key.Key_CapsLock,
    "KEY_TAB": Qt.Key.Key_Tab,
    "KEY_PAUSE": Qt.Key.Key_Pause,
    "KEY_SCROLLLOCK": Qt.Key.Key_ScrollLock,
    "KEY_INSERT": Qt.Key.Key_Insert,
    "KEY_HOME": Qt.Key.Key_Home,
    "KEY_END": Qt.Key.Key_End,
    "KEY_PAGEUP": Qt.Key.Key_PageUp,
    "KEY_PAGEDOWN": Qt.Key.Key_PageDown,
    "KEY_NUMLOCK": Qt.Key.Key_NumLock,
    "KEY_LEFTCTRL": Qt.Key.Key_Control,
    "KEY_LEFTALT": Qt.Key.Key_Alt,
    "KEY_LEFTSHIFT": Qt.Key.Key_Shift,
    "KEY_LEFTMETA": Qt.Key.Key_Meta,
}

# Add letter and digit keys
for _c in range(ord("A"), ord("Z") + 1):
    _EVDEV_TO_QT[f"KEY_{chr(_c)}"] = getattr(Qt.Key, f"Key_{chr(_c)}")
for _d in range(10):
    _EVDEV_TO_QT[f"KEY_{_d}"] = getattr(Qt.Key, f"Key_{_d}")


class _QtKeyFilter(QObject):
    """Application-level event filter that watches for a specific key."""

    pressed = Signal()
    released = Signal()

    def __init__(self, qt_key: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._qt_key = qt_key
        self._is_pressed = False

    def stop(self) -> None:
        app = QCoreApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
            if event.key() == self._qt_key and not self._is_pressed:
                self._is_pressed = True
                self.pressed.emit()
        elif event.type() == QEvent.Type.KeyRelease and not event.isAutoRepeat():
            if event.key() == self._qt_key and self._is_pressed:
                self._is_pressed = False
                self.released.emit()
        return False


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
            # Disconnect signals — different backends use different signal names
            for sig_name in ("activated", "pressed"):
                sig = getattr(self._backend, sig_name, None)
                if sig is not None:
                    try:
                        sig.disconnect(self.ptt_pressed)
                    except (RuntimeError, TypeError):
                        pass
            for sig_name in ("deactivated", "released"):
                sig = getattr(self._backend, sig_name, None)
                if sig is not None:
                    try:
                        sig.disconnect(self.ptt_released)
                    except (RuntimeError, TypeError):
                        pass
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
        """Install an application-wide event filter for PTT key events.

        Only works when the application window is focused.
        """
        qt_key = _EVDEV_TO_QT.get(self._config.evdev_key)
        if qt_key is None:
            logger.warning(
                "Cannot map PTT key '%s' to Qt key code", self._config.evdev_key
            )
            self._active_method = "qt"
            self.method_changed.emit("qt")
            return

        self._qt_filter = _QtKeyFilter(qt_key, self)
        self._qt_filter.pressed.connect(self.ptt_pressed)
        self._qt_filter.released.connect(self.ptt_released)

        app = QCoreApplication.instance()
        if app is not None:
            app.installEventFilter(self._qt_filter)

        self._backend = self._qt_filter
        self._active_method = "qt"
        self.method_changed.emit("qt")
        logger.info(
            "Using Qt key events for PTT (key=%s, window-focused only)",
            self._config.evdev_key,
        )

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
