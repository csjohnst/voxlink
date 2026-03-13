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

    # Set Fluent theme from config before creating any widgets
    _THEME_MAP = {"dark": Theme.DARK, "light": Theme.LIGHT, "auto": Theme.AUTO}
    setTheme(_THEME_MAP.get(config.ui.theme, Theme.AUTO))
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

    # Show which PTT method is active
    _METHOD_LABELS = {"portal": "PTT (Portal)", "evdev": "PTT (evdev)", "qt": "PTT (Qt, focused only)", "none": "PTT (none)"}
    shortcut_manager.method_changed.connect(
        lambda m: main_window._server_page.info_area.append(f"Shortcut method: {_METHOD_LABELS.get(m, m)}")
    )

    # Wire capture level to status bar input meter
    capture_manager.level_changed.connect(main_window.status_bar_widget.set_input_level)

    # Wire audio pipeline through filter functions that respect mute/deafen
    _send_count = [0]
    _recv_count = [0]

    def _send_audio_if_not_muted(pcm_data: bytes) -> None:
        _send_count[0] += 1
        if _send_count[0] % 50 == 1:
            logger.info("_send_audio_if_not_muted called (#%d), muted=%s, %d bytes",
                        _send_count[0], main_window._is_muted, len(pcm_data))
        if not main_window._is_muted:
            mumble_client.send_audio(pcm_data)

    def _play_audio_filtered(session_id: int, pcm_data: bytes) -> None:
        _recv_count[0] += 1
        if _recv_count[0] % 50 == 1:
            logger.info("_play_audio_filtered called (#%d), session=%d, deafened=%s, %d bytes",
                        _recv_count[0], session_id, main_window._is_deafened, len(pcm_data))
        if main_window._is_deafened:
            return
        if main_window.channel_tree.is_user_muted(session_id):
            return
        vol = main_window.channel_tree.get_user_volume(session_id)
        if vol != 1.0:
            import struct
            n_samples = len(pcm_data) // 2
            samples = struct.unpack(f"<{n_samples}h", pcm_data)
            scaled = [max(-32768, min(32767, int(s * vol))) for s in samples]
            pcm_data = struct.pack(f"<{n_samples}h", *scaled)
        playback_manager.play(pcm_data)

    # Use DirectConnection so audio callbacks run immediately on the
    # emitting thread instead of being queued to the main-thread event loop.
    # This avoids latency and potential signal-delivery issues when emitting
    # from plain threading.Thread (capture) or pymumble's network thread.
    from PySide6.QtCore import Qt
    capture_manager.audio_captured.connect(
        _send_audio_if_not_muted, Qt.ConnectionType.DirectConnection)
    mumble_client.audio_received_from_user.connect(
        _play_audio_filtered, Qt.ConnectionType.DirectConnection)

    # Wire talking indicator (queued to main thread for UI safety)
    def _on_user_audio(session_id: int, pcm_data: bytes) -> None:
        main_window.channel_tree.set_user_talking(session_id)
        main_window.compact_overlay.set_user_talking(session_id)
    mumble_client.audio_received_from_user.connect(_on_user_audio)

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

    # Connect settings saved signal to update managers
    def _on_settings_saved() -> None:
        # Update audio devices if changed
        capture_manager.set_device(config.audio.input_device)
        playback_manager.set_device(config.audio.output_device)
        # Refresh tray icon visibility
        if config.ui.show_tray_icon:
            tray_icon.show()
        else:
            tray_icon.hide()

    main_window._settings_page.settings_saved.connect(_on_settings_saved)

    # Start playback manager so it's ready to receive audio
    playback_manager.start()

    # Start device monitoring
    device_manager.refresh()
    device_manager.start_monitoring()

    # Start shortcut detection
    shortcut_manager.start()

    if not config.ui.start_minimized:
        main_window.show()

    if config.ui.show_tray_icon:
        tray_icon.show()

    # Auto-connect if configured
    if config.server.auto_connect and config.server.host:
        logger.info("Auto-connecting to %s:%d as %s",
                     config.server.host, config.server.port, config.server.username)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, lambda: mumble_client.connect_to_server())

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
