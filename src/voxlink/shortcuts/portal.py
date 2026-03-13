"""xdg-desktop-portal GlobalShortcuts interface via D-Bus."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

# Portal constants
_BUS_NAME = "org.freedesktop.portal.Desktop"
_OBJECT_PATH = "/org/freedesktop/portal/desktop"
_IFACE_SHORTCUTS = "org.freedesktop.portal.GlobalShortcuts"
_IFACE_REQUEST = "org.freedesktop.portal.Request"

# Shortcut identifier used for PTT
_PTT_SHORTCUT_ID = "voxlink-ptt"


class PortalShortcuts(QObject):
    """Binds global shortcuts via the xdg-desktop-portal GlobalShortcuts API.

    Uses dbus-next to communicate with the portal. Runs the asyncio
    event loop in a dedicated thread.

    Signals:
        activated: Emitted when the bound shortcut key is pressed.
        deactivated: Emitted when the bound shortcut key is released.
        available_changed: Emitted when portal availability changes.
    """

    activated = Signal()
    deactivated = Signal()
    available_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._session = None
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._bus = None
        self._session_handle: str | None = None

    @staticmethod
    def is_available() -> bool:
        """Check if the GlobalShortcuts portal is available via D-Bus."""
        try:
            from dbus_next.aio import MessageBus
            from dbus_next import BusType
        except ImportError:
            logger.debug("dbus-next not available")
            return False

        # Run a quick synchronous check using a temporary event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_check_portal_available())
        except Exception:
            logger.debug("Portal availability check failed", exc_info=True)
            return False
        finally:
            loop.close()

    def start(self) -> None:
        """Create a session and bind shortcuts."""
        if self._running:
            return

        self._running = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="portal-shortcuts",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Close the session and clean up."""
        if not self._running:
            return

        self._running = False

        if self._loop is not None and not self._loop.is_closed():
            # Schedule cleanup on the asyncio loop
            asyncio.run_coroutine_threadsafe(self._async_stop(), self._loop)
            # Then stop the loop
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

        if self._loop is not None and not self._loop.is_closed():
            self._loop.close()
        self._loop = None

    def _run_loop(self) -> None:
        """Entry point for the dedicated asyncio thread."""
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_start())
            # Keep the loop running to receive signals
            self._loop.run_forever()
        except Exception:
            logger.error("Portal shortcuts event loop error", exc_info=True)
        finally:
            # Clean up any remaining tasks
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass

    async def _async_start(self) -> None:
        """Async setup: connect to D-Bus, create session, bind shortcuts."""
        from dbus_next.aio import MessageBus
        from dbus_next import BusType, Variant

        try:
            self._bus = await MessageBus(bus_type=BusType.SESSION).connect()
        except Exception:
            logger.error("Failed to connect to session bus", exc_info=True)
            self.available_changed.emit(False)
            return

        try:
            introspection = await self._bus.introspect(_BUS_NAME, _OBJECT_PATH)
            proxy = self._bus.get_proxy_object(
                _BUS_NAME, _OBJECT_PATH, introspection
            )
            shortcuts_iface = proxy.get_interface(_IFACE_SHORTCUTS)
        except Exception:
            logger.error(
                "Failed to get GlobalShortcuts interface", exc_info=True
            )
            self.available_changed.emit(False)
            return

        # Step 1: CreateSession
        try:
            session_handle = await self._create_session(shortcuts_iface)
            if session_handle is None:
                logger.error("CreateSession returned no session handle")
                self.available_changed.emit(False)
                return
            self._session_handle = session_handle
            logger.info("Portal session created: %s", session_handle)
        except Exception:
            logger.error("CreateSession failed", exc_info=True)
            self.available_changed.emit(False)
            return

        # Step 2: ListShortcuts (informational)
        try:
            await shortcuts_iface.call_list_shortcuts(  # type: ignore[attr-defined]
                self._session_handle,
                {},
            )
        except Exception:
            logger.debug("ListShortcuts call failed (non-critical)", exc_info=True)

        # Step 3: BindShortcuts - portal shows its own UI for key selection
        try:
            shortcuts = [
                (
                    _PTT_SHORTCUT_ID,
                    {
                        "description": Variant("s", "Push to Talk"),
                    },
                )
            ]
            await shortcuts_iface.call_bind_shortcuts(  # type: ignore[attr-defined]
                self._session_handle,
                shortcuts,
                "",  # parent_window
                {},
            )
            logger.info("BindShortcuts requested (portal will show UI)")
        except Exception:
            logger.error("BindShortcuts failed", exc_info=True)

        # Step 4: Listen for Activated / Deactivated signals
        try:
            shortcuts_iface.on_activated(self._on_activated)  # type: ignore[attr-defined]
            shortcuts_iface.on_deactivated(self._on_deactivated)  # type: ignore[attr-defined]
            logger.info("Listening for portal shortcut signals")
            self.available_changed.emit(True)
        except Exception:
            logger.error("Failed to connect portal signals", exc_info=True)
            self.available_changed.emit(False)

    async def _create_session(self, shortcuts_iface: Any) -> str | None:
        """Call CreateSession and return the session object path."""
        from dbus_next import Variant

        sender = self._bus.unique_name.replace(".", "_").lstrip(":")
        token = "voxlink_session"
        request_path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"

        # Set up a future to wait for the Response signal on the Request object
        response_future: asyncio.Future[Any] = self._loop.create_future()  # type: ignore[union-attr]

        try:
            req_introspection = await self._bus.introspect(
                _BUS_NAME, request_path
            )
        except Exception:
            # The request object may not exist yet; we'll create it after
            # calling CreateSession. For dbus-next, we listen on the bus
            # message handler instead.
            pass

        options = {
            "handle_token": Variant("s", token),
            "session_handle_token": Variant("s", "voxlink_ptt"),
        }

        result = await shortcuts_iface.call_create_session(options)  # type: ignore[attr-defined]

        # result is the request object path; the actual session handle
        # comes from the portal session_handle_token
        session_path = (
            f"/org/freedesktop/portal/desktop/session/{sender}/voxlink_ptt"
        )
        return session_path

    def _on_activated(
        self,
        session_handle: str,
        shortcut_id: str,
        timestamp: int,
        options: dict[str, Any],
    ) -> None:
        """Handle the Activated signal from the portal."""
        logger.debug(
            "Portal shortcut activated: %s (ts=%d)", shortcut_id, timestamp
        )
        if shortcut_id == _PTT_SHORTCUT_ID:
            self.activated.emit()

    def _on_deactivated(
        self,
        session_handle: str,
        shortcut_id: str,
        timestamp: int,
        options: dict[str, Any],
    ) -> None:
        """Handle the Deactivated signal from the portal."""
        logger.debug(
            "Portal shortcut deactivated: %s (ts=%d)", shortcut_id, timestamp
        )
        if shortcut_id == _PTT_SHORTCUT_ID:
            self.deactivated.emit()

    async def _async_stop(self) -> None:
        """Async cleanup: close session and disconnect from bus."""
        if self._bus is not None:
            try:
                self._bus.disconnect()
            except Exception:
                pass
            self._bus = None
        self._session_handle = None


async def _check_portal_available() -> bool:
    """Check if the GlobalShortcuts portal interface exists on the bus."""
    from dbus_next.aio import MessageBus
    from dbus_next import BusType

    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    try:
        introspection = await bus.introspect(_BUS_NAME, _OBJECT_PATH)
        proxy = bus.get_proxy_object(_BUS_NAME, _OBJECT_PATH, introspection)
        # This will raise if the interface isn't available
        proxy.get_interface(_IFACE_SHORTCUTS)
        return True
    except Exception:
        return False
    finally:
        bus.disconnect()
