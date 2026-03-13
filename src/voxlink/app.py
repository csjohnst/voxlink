"""QApplication setup and main window orchestration."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from voxlink.config import VoxLinkConfig

logger = logging.getLogger(__name__)


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

    # Wire PTT signals to audio capture
    shortcut_manager.ptt_pressed.connect(capture_manager.start)
    shortcut_manager.ptt_released.connect(capture_manager.stop)

    # Wire audio pipeline
    capture_manager.audio_captured.connect(mumble_client.send_audio)
    mumble_client.audio_received.connect(playback_manager.play)

    # Wire mumble events to UI
    mumble_client.events.connected.connect(main_window.on_connected)
    mumble_client.events.disconnected.connect(main_window.on_disconnected)
    mumble_client.events.error.connect(main_window.on_error)
    mumble_client.events.channel_updated.connect(main_window.on_channel_updated)
    mumble_client.events.user_joined.connect(main_window.on_user_joined)
    mumble_client.events.user_left.connect(main_window.on_user_left)

    if not config.ui.start_minimized:
        main_window.show()

    if config.ui.show_tray_icon:
        tray_icon.show()

    return app.exec()
