"""Settings page using Fluent Design widgets."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets import (
    ScrollArea,
    ExpandLayout,
    SubtitleLabel,
    BodyLabel,
    ComboBox,
    Slider,
    LineEdit,
    PasswordLineEdit,
    SwitchButton,
    SimpleCardWidget,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    setTheme,
    Theme,
    isDarkTheme,
    InfoBar,
    InfoBarPosition,
)

from voxlink.config import VoxLinkConfig

if TYPE_CHECKING:
    from voxlink.audio.devices import DeviceManager

logger = logging.getLogger(__name__)


def _qt_key_to_evdev_name(qt_key: int) -> str | None:
    """Map a Qt key code to an evdev KEY_* name."""
    from PySide6.QtCore import Qt as _Qt

    # Common mappings
    _MAP = {
        _Qt.Key.Key_F1: "KEY_F1", _Qt.Key.Key_F2: "KEY_F2",
        _Qt.Key.Key_F3: "KEY_F3", _Qt.Key.Key_F4: "KEY_F4",
        _Qt.Key.Key_F5: "KEY_F5", _Qt.Key.Key_F6: "KEY_F6",
        _Qt.Key.Key_F7: "KEY_F7", _Qt.Key.Key_F8: "KEY_F8",
        _Qt.Key.Key_F9: "KEY_F9", _Qt.Key.Key_F10: "KEY_F10",
        _Qt.Key.Key_F11: "KEY_F11", _Qt.Key.Key_F12: "KEY_F12",
        _Qt.Key.Key_F13: "KEY_F13", _Qt.Key.Key_F14: "KEY_F14",
        _Qt.Key.Key_F15: "KEY_F15", _Qt.Key.Key_F16: "KEY_F16",
        _Qt.Key.Key_Space: "KEY_SPACE",
        _Qt.Key.Key_CapsLock: "KEY_CAPSLOCK",
        _Qt.Key.Key_Tab: "KEY_TAB",
        _Qt.Key.Key_Pause: "KEY_PAUSE",
        _Qt.Key.Key_ScrollLock: "KEY_SCROLLLOCK",
        _Qt.Key.Key_Insert: "KEY_INSERT",
        _Qt.Key.Key_Home: "KEY_HOME",
        _Qt.Key.Key_End: "KEY_END",
        _Qt.Key.Key_PageUp: "KEY_PAGEUP",
        _Qt.Key.Key_PageDown: "KEY_PAGEDOWN",
        _Qt.Key.Key_NumLock: "KEY_NUMLOCK",
        _Qt.Key.Key_Control: "KEY_LEFTCTRL",
        _Qt.Key.Key_Alt: "KEY_LEFTALT",
        _Qt.Key.Key_Shift: "KEY_LEFTSHIFT",
        _Qt.Key.Key_Meta: "KEY_LEFTMETA",
    }

    name = _MAP.get(qt_key)
    if name:
        return name

    # Try letter/number keys
    if _Qt.Key.Key_A <= qt_key <= _Qt.Key.Key_Z:
        letter = chr(qt_key)
        return f"KEY_{letter}"
    if _Qt.Key.Key_0 <= qt_key <= _Qt.Key.Key_9:
        digit = chr(qt_key)
        return f"KEY_{digit}"

    # Fallback: use the Qt key name
    return None


class SettingsPage(ScrollArea):
    """Settings page with fluent card-based layout."""

    settings_saved = Signal()

    def __init__(
        self,
        config: VoxLinkConfig,
        device_manager: DeviceManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self.setWidgetResizable(True)

        # Scroll content
        self._content = QWidget()
        self._content.setObjectName("settingsContent")
        self._layout = ExpandLayout(self._content)
        self._layout.setContentsMargins(28, 28, 28, 28)
        self._layout.setSpacing(16)

        self._config = config
        self._device_manager = device_manager

        self._create_audio_group()
        self._create_voice_group()
        self._create_connection_group()
        self._create_general_group()
        self._create_actions()

        self.setWidget(self._content)
        self._load_values()

    # ---- Audio Group ----

    def _create_audio_group(self) -> None:
        self._audio_label = SubtitleLabel("Audio")
        self._layout.addWidget(self._audio_label)

        # Input device
        self._input_card = SimpleCardWidget()
        input_layout = QHBoxLayout(self._input_card)
        input_layout.setContentsMargins(16, 8, 16, 8)
        input_layout.addWidget(BodyLabel("Input Device"))
        input_layout.addStretch()
        self._input_combo = ComboBox()
        self._input_combo.setMinimumWidth(200)
        input_layout.addWidget(self._input_combo)
        self._layout.addWidget(self._input_card)

        # Output device
        self._output_card = SimpleCardWidget()
        output_layout = QHBoxLayout(self._output_card)
        output_layout.setContentsMargins(16, 8, 16, 8)
        output_layout.addWidget(BodyLabel("Output Device"))
        output_layout.addStretch()
        self._output_combo = ComboBox()
        self._output_combo.setMinimumWidth(200)
        output_layout.addWidget(self._output_combo)
        self._layout.addWidget(self._output_card)

        # Input volume
        self._input_vol_card = SimpleCardWidget()
        iv_layout = QHBoxLayout(self._input_vol_card)
        iv_layout.setContentsMargins(16, 8, 16, 8)
        iv_layout.addWidget(BodyLabel("Input Volume"))
        iv_layout.addStretch()
        self._input_volume_label = BodyLabel("80%")
        self._input_volume_label.setMinimumWidth(40)
        self._input_volume_slider = Slider(Qt.Orientation.Horizontal)
        self._input_volume_slider.setRange(0, 100)
        self._input_volume_slider.setMinimumWidth(200)
        self._input_volume_slider.valueChanged.connect(
            lambda v: self._input_volume_label.setText(f"{v}%")
        )
        iv_layout.addWidget(self._input_volume_slider)
        iv_layout.addWidget(self._input_volume_label)
        self._layout.addWidget(self._input_vol_card)

        # Output volume
        self._output_vol_card = SimpleCardWidget()
        ov_layout = QHBoxLayout(self._output_vol_card)
        ov_layout.setContentsMargins(16, 8, 16, 8)
        ov_layout.addWidget(BodyLabel("Output Volume"))
        ov_layout.addStretch()
        self._output_volume_label = BodyLabel("100%")
        self._output_volume_label.setMinimumWidth(40)
        self._output_volume_slider = Slider(Qt.Orientation.Horizontal)
        self._output_volume_slider.setRange(0, 100)
        self._output_volume_slider.setMinimumWidth(200)
        self._output_volume_slider.valueChanged.connect(
            lambda v: self._output_volume_label.setText(f"{v}%")
        )
        ov_layout.addWidget(self._output_volume_slider)
        ov_layout.addWidget(self._output_volume_label)
        self._layout.addWidget(self._output_vol_card)

        # Test audio
        self._test_card = SimpleCardWidget()
        test_layout = QHBoxLayout(self._test_card)
        test_layout.setContentsMargins(16, 8, 16, 8)
        test_layout.addWidget(BodyLabel("Test Audio"))
        test_layout.addStretch()
        self._test_btn = PushButton("Test")
        self._test_btn.setMinimumWidth(100)
        self._test_btn.clicked.connect(self._on_test_audio)
        test_layout.addWidget(self._test_btn)
        self._layout.addWidget(self._test_card)

        # Populate devices
        self._populate_devices()

    def _populate_devices(self) -> None:
        """Fill device combo boxes from DeviceManager."""
        self._input_combo.clear()
        self._output_combo.clear()

        self._input_combo.addItem("(Default)")
        self._output_combo.addItem("(Default)")

        # Store user data mapping: display text -> device name
        self._input_device_data: dict[str, str] = {"(Default)": ""}
        self._output_device_data: dict[str, str] = {"(Default)": ""}

        if self._device_manager is not None:
            self._device_manager.refresh()
            for dev in self._device_manager.get_sources():
                if not dev.is_monitor:
                    self._input_combo.addItem(dev.description)
                    self._input_device_data[dev.description] = dev.name
            for dev in self._device_manager.get_sinks():
                self._output_combo.addItem(dev.description)
                self._output_device_data[dev.description] = dev.name

    # ---- Voice Group ----

    def _create_voice_group(self) -> None:
        self._voice_label = SubtitleLabel("Voice")
        self._layout.addWidget(self._voice_label)

        # Voice mode
        self._mode_card = SimpleCardWidget()
        mode_layout = QHBoxLayout(self._mode_card)
        mode_layout.setContentsMargins(16, 8, 16, 8)
        mode_layout.addWidget(BodyLabel("Voice Mode"))
        mode_layout.addStretch()
        self._voice_mode_combo = ComboBox()
        self._voice_mode_combo.addItems(["Push-to-Talk", "Voice Activity", "Continuous"])
        self._voice_mode_combo.setMinimumWidth(200)
        mode_layout.addWidget(self._voice_mode_combo)
        self._layout.addWidget(self._mode_card)

        # Mode display text -> config value mapping
        self._voice_mode_map = {
            "Push-to-Talk": "ptt",
            "Voice Activity": "vad",
            "Continuous": "continuous",
        }
        self._voice_mode_reverse = {v: k for k, v in self._voice_mode_map.items()}

        # PTT key binding
        self._ptt_card = SimpleCardWidget()
        ptt_layout = QHBoxLayout(self._ptt_card)
        ptt_layout.setContentsMargins(16, 8, 16, 8)
        ptt_layout.addWidget(BodyLabel("PTT Key"))
        ptt_layout.addStretch()
        self._ptt_key_btn = PrimaryPushButton("Click to bind...")
        self._ptt_key_btn.setMinimumWidth(200)
        self._ptt_key_btn.clicked.connect(self._on_bind_ptt_key)
        ptt_layout.addWidget(self._ptt_key_btn)
        self._layout.addWidget(self._ptt_card)

        # VAD sensitivity
        self._vad_card = SimpleCardWidget()
        vad_layout = QHBoxLayout(self._vad_card)
        vad_layout.setContentsMargins(16, 8, 16, 8)
        vad_layout.addWidget(BodyLabel("VAD Sensitivity"))
        vad_layout.addStretch()
        self._vad_sensitivity_label = BodyLabel("2%")
        self._vad_sensitivity_label.setMinimumWidth(40)
        self._vad_sensitivity_slider = Slider(Qt.Orientation.Horizontal)
        self._vad_sensitivity_slider.setRange(0, 100)
        self._vad_sensitivity_slider.setMinimumWidth(200)
        self._vad_sensitivity_slider.valueChanged.connect(
            lambda v: self._vad_sensitivity_label.setText(f"{v}%")
        )
        vad_layout.addWidget(self._vad_sensitivity_slider)
        vad_layout.addWidget(self._vad_sensitivity_label)
        self._layout.addWidget(self._vad_card)

    # ---- Connection Group ----

    def _create_connection_group(self) -> None:
        self._conn_label = SubtitleLabel("Connection")
        self._layout.addWidget(self._conn_label)

        # Username
        self._user_card = SimpleCardWidget()
        user_layout = QHBoxLayout(self._user_card)
        user_layout.setContentsMargins(16, 8, 16, 8)
        user_layout.addWidget(BodyLabel("Username"))
        user_layout.addStretch()
        self._username_edit = LineEdit()
        self._username_edit.setMinimumWidth(200)
        user_layout.addWidget(self._username_edit)
        self._layout.addWidget(self._user_card)

        # Password
        self._pass_card = SimpleCardWidget()
        pass_layout = QHBoxLayout(self._pass_card)
        pass_layout.setContentsMargins(16, 8, 16, 8)
        pass_layout.addWidget(BodyLabel("Password"))
        pass_layout.addStretch()
        self._password_edit = PasswordLineEdit()
        self._password_edit.setMinimumWidth(200)
        self._password_edit.setPlaceholderText("(stored in keyring)")
        pass_layout.addWidget(self._password_edit)
        self._layout.addWidget(self._pass_card)

        # Server host
        self._host_card = SimpleCardWidget()
        host_layout = QHBoxLayout(self._host_card)
        host_layout.setContentsMargins(16, 8, 16, 8)
        host_layout.addWidget(BodyLabel("Server Host"))
        host_layout.addStretch()
        self._host_edit = LineEdit()
        self._host_edit.setMinimumWidth(200)
        host_layout.addWidget(self._host_edit)
        self._layout.addWidget(self._host_card)

        # Server port
        self._port_card = SimpleCardWidget()
        port_layout = QHBoxLayout(self._port_card)
        port_layout.setContentsMargins(16, 8, 16, 8)
        port_layout.addWidget(BodyLabel("Server Port"))
        port_layout.addStretch()
        self._port_spin = SpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setMinimumWidth(200)
        port_layout.addWidget(self._port_spin)
        self._layout.addWidget(self._port_card)

    # ---- General Group ----

    def _create_general_group(self) -> None:
        self._general_label = SubtitleLabel("General")
        self._layout.addWidget(self._general_label)

        # Dark mode
        self._dark_card = SimpleCardWidget()
        dark_layout = QHBoxLayout(self._dark_card)
        dark_layout.setContentsMargins(16, 8, 16, 8)
        dark_layout.addWidget(BodyLabel("Dark Mode"))
        dark_layout.addStretch()
        self._dark_switch = SwitchButton()
        self._dark_switch.checkedChanged.connect(self._on_dark_mode_toggled)
        dark_layout.addWidget(self._dark_switch)
        self._layout.addWidget(self._dark_card)

        # Start minimized
        self._minimized_card = SimpleCardWidget()
        min_layout = QHBoxLayout(self._minimized_card)
        min_layout.setContentsMargins(16, 8, 16, 8)
        min_layout.addWidget(BodyLabel("Start Minimized"))
        min_layout.addStretch()
        self._start_minimized_switch = SwitchButton()
        min_layout.addWidget(self._start_minimized_switch)
        self._layout.addWidget(self._minimized_card)

        # Show tray icon
        self._tray_card = SimpleCardWidget()
        tray_layout = QHBoxLayout(self._tray_card)
        tray_layout.setContentsMargins(16, 8, 16, 8)
        tray_layout.addWidget(BodyLabel("Show Tray Icon"))
        tray_layout.addStretch()
        self._show_tray_switch = SwitchButton()
        tray_layout.addWidget(self._show_tray_switch)
        self._layout.addWidget(self._tray_card)

        # Compact mode
        self._compact_card = SimpleCardWidget()
        compact_layout = QHBoxLayout(self._compact_card)
        compact_layout.setContentsMargins(16, 8, 16, 8)
        compact_layout.addWidget(BodyLabel("Compact Mode"))
        compact_layout.addStretch()
        self._compact_switch = SwitchButton()
        compact_layout.addWidget(self._compact_switch)
        self._layout.addWidget(self._compact_card)

    # ---- Actions ----

    def _create_actions(self) -> None:
        self._save_btn = PrimaryPushButton("Save Settings")
        self._save_btn.setMinimumWidth(140)
        self._save_btn.clicked.connect(self._apply_settings)
        self._layout.addWidget(self._save_btn)

    # ---- Load / Apply ----

    def _load_values(self) -> None:
        """Populate widgets from current config."""
        cfg = self._config

        # Audio
        self._input_volume_slider.setValue(cfg.audio.input_volume)
        self._output_volume_slider.setValue(cfg.audio.output_volume)

        # Select current input device
        for text, name in self._input_device_data.items():
            if name == cfg.audio.input_device:
                idx = self._input_combo.findText(text)
                if idx >= 0:
                    self._input_combo.setCurrentIndex(idx)
                break

        # Select current output device
        for text, name in self._output_device_data.items():
            if name == cfg.audio.output_device:
                idx = self._output_combo.findText(text)
                if idx >= 0:
                    self._output_combo.setCurrentIndex(idx)
                break

        # Voice
        mode_text = self._voice_mode_reverse.get(cfg.ptt.mode, "Push-to-Talk")
        mode_idx = self._voice_mode_combo.findText(mode_text)
        if mode_idx >= 0:
            self._voice_mode_combo.setCurrentIndex(mode_idx)
        self._ptt_key_btn.setText(cfg.ptt.evdev_key or "Click to bind...")
        vad_pct = int(cfg.ptt.vad_threshold * 100)
        self._vad_sensitivity_slider.setValue(vad_pct)

        # Connection
        self._username_edit.setText(cfg.server.username)
        self._host_edit.setText(cfg.server.host)
        self._port_spin.setValue(cfg.server.port)

        # General
        self._dark_switch.setChecked(isDarkTheme())
        self._start_minimized_switch.setChecked(cfg.ui.start_minimized)
        self._show_tray_switch.setChecked(cfg.ui.show_tray_icon)
        self._compact_switch.setChecked(cfg.ui.compact_mode)

    def _apply_settings(self) -> None:
        """Write widget values back to config."""
        cfg = self._config

        # Audio
        input_text = self._input_combo.currentText()
        cfg.audio.input_device = self._input_device_data.get(input_text, "")
        output_text = self._output_combo.currentText()
        cfg.audio.output_device = self._output_device_data.get(output_text, "")
        cfg.audio.input_volume = self._input_volume_slider.value()
        cfg.audio.output_volume = self._output_volume_slider.value()

        # Voice
        mode_text = self._voice_mode_combo.currentText()
        cfg.ptt.mode = self._voice_mode_map.get(mode_text, "ptt")
        cfg.ptt.vad_threshold = self._vad_sensitivity_slider.value() / 100.0

        # Connection
        cfg.server.username = self._username_edit.text() or cfg.server.username
        cfg.server.host = self._host_edit.text() or cfg.server.host
        port_val = self._port_spin.value()
        if port_val > 0:
            cfg.server.port = port_val

        # General
        cfg.ui.start_minimized = self._start_minimized_switch.isChecked()
        cfg.ui.show_tray_icon = self._show_tray_switch.isChecked()
        cfg.ui.compact_mode = self._compact_switch.isChecked()

        try:
            cfg.save()
        except Exception:
            logger.exception("Failed to save settings")

        self.settings_saved.emit()

    # ---- Event Handlers ----

    def _on_dark_mode_toggled(self, checked: bool) -> None:
        """Toggle between dark and light theme."""
        setTheme(Theme.DARK if checked else Theme.LIGHT)

    def _on_bind_ptt_key(self) -> None:
        """Start PTT key binding process."""
        method = self._config.ptt.shortcut_method

        if method == "portal" or method == "auto":
            # Portal handles its own key binding UI
            # We just need to trigger a re-bind
            self._ptt_key_btn.setText("Waiting for portal...")
            try:
                from voxlink.shortcuts.portal import PortalShortcuts
                if PortalShortcuts.is_available():
                    # The portal will show its own dialog
                    # We need to restart the shortcut manager to trigger BindShortcuts
                    self._ptt_key_btn.setText("Portal binding active")
                    InfoBar.info(
                        "PTT Binding",
                        "The desktop portal will show a key binding dialog. "
                        "Press the key you want to use for Push-to-Talk.",
                        parent=self.window(),
                        duration=5000,
                    )
                    return
            except Exception:
                pass

        # For evdev or fallback: capture next key press
        self._ptt_key_btn.setText("Press any key...")
        self._ptt_key_btn.setFocus()
        self._waiting_for_key = True
        # Install event filter to capture the next key press
        self._ptt_key_btn.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        """Capture key press for PTT binding."""
        from PySide6.QtCore import QEvent
        if hasattr(self, '_waiting_for_key') and self._waiting_for_key:
            if event.type() == QEvent.Type.KeyPress:
                from PySide6.QtCore import Qt as _Qt
                key = event.key()
                if key in (_Qt.Key.Key_Escape,):
                    # Cancel binding
                    self._ptt_key_btn.setText(self._config.ptt.evdev_key or "Click to bind...")
                    self._waiting_for_key = False
                    self._ptt_key_btn.removeEventFilter(self)
                    return True

                # Map Qt key to evdev key name
                key_name = _qt_key_to_evdev_name(key)
                if key_name:
                    self._config.ptt.evdev_key = key_name
                    self._ptt_key_btn.setText(key_name)
                    self._waiting_for_key = False
                    self._ptt_key_btn.removeEventFilter(self)
                    logger.info("PTT key bound to: %s", key_name)
                    return True
        return super().eventFilter(obj, event)

    def _on_test_audio(self) -> None:
        """Record 2 seconds from input and play back through output."""
        import threading
        from voxlink.audio.capture import FRAME_BYTES, RATE

        self._test_btn.setEnabled(False)
        self._test_btn.setText("Recording...")

        input_dev = self._input_device_data.get(self._input_combo.currentText(), "")
        output_dev = self._output_device_data.get(self._output_combo.currentText(), "")

        def _run_test() -> None:
            try:
                from pasimple import (
                    PaSimple,
                    PA_STREAM_RECORD,
                    PA_STREAM_PLAYBACK,
                    PA_SAMPLE_S16LE,
                )

                # Record 2 seconds
                record_stream = PaSimple(
                    direction=PA_STREAM_RECORD,
                    format=PA_SAMPLE_S16LE,
                    channels=1,
                    rate=RATE,
                    app_name="voxlink-test",
                    stream_name="test-capture",
                    device_name=input_dev or None,
                    fragsize=FRAME_BYTES,
                )

                frames: list[bytes] = []
                num_frames = int(RATE * 2 / 960)  # 2 seconds worth
                for _ in range(num_frames):
                    data = record_stream.read(FRAME_BYTES)
                    frames.append(data)
                record_stream.close()

                self._test_btn.setText("Playing...")

                # Play back
                play_stream = PaSimple(
                    direction=PA_STREAM_PLAYBACK,
                    format=PA_SAMPLE_S16LE,
                    channels=1,
                    rate=RATE,
                    app_name="voxlink-test",
                    stream_name="test-playback",
                    device_name=output_dev or None,
                )
                for frame in frames:
                    play_stream.write(frame)
                play_stream.drain()
                play_stream.close()

            except Exception:
                logger.exception("Audio test failed")
            finally:
                self._test_btn.setText("Test")
                self._test_btn.setEnabled(True)

        thread = threading.Thread(target=_run_test, daemon=True)
        thread.start()
