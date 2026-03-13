"""QApplication setup and main window orchestration."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme, setThemeColor

from voxlink.config import VoxLinkConfig

logger = logging.getLogger(__name__)

# Path to the app icon
_ICON_PATH = Path(__file__).resolve().parent.parent.parent / "resources" / "icons" / "voxlink.svg"


def run_app(config_path: str | None = None) -> int:
    """Launch the VoxLink GUI application.

    Args:
        config_path: Optional path to config file.

    Returns:
        Application exit code.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "wayland")

    config = VoxLinkConfig.load(Path(config_path) if config_path else None)

    app = QApplication(sys.argv)
    app.setApplicationName("VoxLink")
    app.setApplicationDisplayName("VoxLink")
    app.setDesktopFileName("voxlink")

    # Set application icon
    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))

    # Set Fluent theme before creating any widgets
    setTheme(Theme.AUTO)
    setThemeColor(QColor("#4ade80"))

    # Import here to avoid circular imports and ensure QApplication exists
    from voxlink.audio.devices import DeviceManager
    from voxlink.audio.capture import CaptureManager
    from voxlink.audio.playback import PlaybackManager
    from voxlink.mumble.client import MumbleClient
    from voxlink.shortcuts.manager import ShortcutManager
    from voxlink.ui.main_window import MainWindow
    from voxlink.ui.tray import TrayIcon

    # Instantiate managers
    device_manager = DeviceManager()
    capture_manager = CaptureManager(config.audio)
    playback_manager = PlaybackManager(config.audio)
    mumble_client = MumbleClient(config.server)
    shortcut_manager = ShortcutManager(config.ptt)

    # Create UI
    main_window = MainWindow(
        config=config,
        device_manager=device_manager,
        capture_manager=capture_manager,
        playback_manager=playback_manager,
        mumble_client=mumble_client,
        shortcut_manager=shortcut_manager,
    )

    tray_icon = TrayIcon(main_window, config.ui)
    main_window.set_tray_icon(tray_icon)

    # Wire PTT signals to audio capture
    shortcut_manager.ptt_pressed.connect(capture_manager.start)
    shortcut_manager.ptt_released.connect(capture_manager.stop)

    # Wire PTT indicator on status bar
    shortcut_manager.ptt_pressed.connect(lambda: main_window.status_bar_widget.set_ptt_active(True))
    shortcut_manager.ptt_released.connect(lambda: main_window.status_bar_widget.set_ptt_active(False))

    # Wire capture level to status bar input meter
    capture_manager.level_changed.connect(main_window.status_bar_widget.set_input_level)

    # Wire audio pipeline
    capture_manager.audio_captured.connect(mumble_client.send_audio)
    mumble_client.audio_received.connect(playback_manager.play)

    # Wire mumble events to UI
    mumble_client.events.connected.connect(main_window.on_connected)
    mumble_client.events.disconnected.connect(main_window.on_disconnected)
    mumble_client.events.error.connect(main_window.on_error)
    mumble_client.events.channel_updated.connect(main_window.on_channel_updated)
    mumble_client.events.channel_created.connect(main_window.on_channel_updated)
    mumble_client.events.channel_removed.connect(main_window.on_channel_updated)
    mumble_client.events.user_joined.connect(main_window.on_user_joined)
    mumble_client.events.user_left.connect(main_window.on_user_left)
    mumble_client.events.user_state_changed.connect(
        lambda data: main_window.channel_tree.update_user(data)
    )

    # Wire tray icon state to connection events
    mumble_client.events.connected.connect(tray_icon.set_connected)
    mumble_client.events.disconnected.connect(tray_icon.set_disconnected)

    # Wire tray menu actions
    tray_icon.mute_action.toggled.connect(main_window.status_bar_widget.set_muted)
    tray_icon.deafen_action.toggled.connect(main_window.status_bar_widget.set_deafened)
    tray_icon.disconnect_action.triggered.connect(mumble_client.disconnect)
    tray_icon.quit_action.triggered.connect(app.quit)

    # Start device monitoring
    device_manager.refresh()
    device_manager.start_monitoring()

    # Start shortcut detection
    shortcut_manager.start()

    if not config.ui.start_minimized:
        main_window.show()

    if config.ui.show_tray_icon:
        tray_icon.show()

    # Graceful shutdown
    def _shutdown() -> None:
        logger.info("Shutting down...")
        shortcut_manager.stop()
        capture_manager.stop()
        playback_manager.stop()
        device_manager.stop_monitoring()
        mumble_client.disconnect()

    app.aboutToQuit.connect(_shutdown)

    return app.exec()
