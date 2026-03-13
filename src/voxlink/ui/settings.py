"""Settings dialog with tabbed configuration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from voxlink.config import VoxLinkConfig

if TYPE_CHECKING:
    from voxlink.audio.devices import DeviceManager

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Settings dialog with tabs for Audio, Voice, Connection, and General.

    Tabs:
    - Audio: Input/output device selection, volume sliders, test button
    - Voice: PTT/VAD/Continuous mode, key binding, VAD sensitivity
    - Connection: Server list management, username, password
    - General: Start minimized, tray icon, compact mode
    """

    def __init__(
        self,
        config: VoxLinkConfig,
        device_manager: DeviceManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._device_manager = device_manager
        self.setWindowTitle("VoxLink Settings")
        self.setMinimumSize(480, 400)
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tabs.addTab(self._create_audio_tab(), "Audio")
        self._tabs.addTab(self._create_voice_tab(), "Voice")
        self._tabs.addTab(self._create_connection_tab(), "Connection")
        self._tabs.addTab(self._create_general_tab(), "General")

        # Button box
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        self._button_box.accepted.connect(self._on_ok)
        self._button_box.rejected.connect(self.reject)
        apply_btn = self._button_box.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn:
            apply_btn.clicked.connect(self._apply_settings)
        layout.addWidget(self._button_box)

    # ---- Audio Tab ----

    def _create_audio_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)

        self._input_device_combo = QComboBox()
        layout.addRow("Input device:", self._input_device_combo)

        self._output_device_combo = QComboBox()
        layout.addRow("Output device:", self._output_device_combo)

        self._input_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._input_volume_slider.setRange(0, 100)
        self._input_volume_label = QLabel("80%")
        self._input_volume_slider.valueChanged.connect(
            lambda v: self._input_volume_label.setText(f"{v}%")
        )
        input_vol_layout = QHBoxLayout()
        input_vol_layout.addWidget(self._input_volume_slider)
        input_vol_layout.addWidget(self._input_volume_label)
        input_vol_widget = QWidget()
        input_vol_widget.setLayout(input_vol_layout)
        layout.addRow("Input volume:", input_vol_widget)

        self._output_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._output_volume_slider.setRange(0, 100)
        self._output_volume_label = QLabel("100%")
        self._output_volume_slider.valueChanged.connect(
            lambda v: self._output_volume_label.setText(f"{v}%")
        )
        output_vol_layout = QHBoxLayout()
        output_vol_layout.addWidget(self._output_volume_slider)
        output_vol_layout.addWidget(self._output_volume_label)
        output_vol_widget = QWidget()
        output_vol_widget.setLayout(output_vol_layout)
        layout.addRow("Output volume:", output_vol_widget)

        self._test_audio_btn = QPushButton("Test Audio")
        self._test_audio_btn.clicked.connect(self._on_test_audio)
        layout.addRow("", self._test_audio_btn)

        # Populate devices
        self._populate_devices()

        return widget

    def _populate_devices(self) -> None:
        """Fill device combo boxes from DeviceManager."""
        self._input_device_combo.clear()
        self._output_device_combo.clear()

        self._input_device_combo.addItem("(Default)", "")
        self._output_device_combo.addItem("(Default)", "")

        if self._device_manager is not None:
            self._device_manager.refresh()
            for dev in self._device_manager.get_sources():
                if not dev.is_monitor:
                    self._input_device_combo.addItem(dev.description, dev.name)
            for dev in self._device_manager.get_sinks():
                self._output_device_combo.addItem(dev.description, dev.name)

    # ---- Voice Tab ----

    def _create_voice_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)

        self._voice_mode_combo = QComboBox()
        self._voice_mode_combo.addItem("Push-to-Talk", "ptt")
        self._voice_mode_combo.addItem("Voice Activity", "vad")
        self._voice_mode_combo.addItem("Continuous", "continuous")
        layout.addRow("Voice mode:", self._voice_mode_combo)

        self._ptt_key_btn = QPushButton("Click to bind...")
        self._ptt_key_btn.setToolTip("Click, then press the desired PTT key")
        self._ptt_key_btn.clicked.connect(self._on_bind_ptt_key)
        layout.addRow("PTT key:", self._ptt_key_btn)

        self._vad_sensitivity_slider = QSlider(Qt.Orientation.Horizontal)
        self._vad_sensitivity_slider.setRange(0, 100)
        self._vad_sensitivity_label = QLabel("2%")
        self._vad_sensitivity_slider.valueChanged.connect(
            lambda v: self._vad_sensitivity_label.setText(f"{v}%")
        )
        vad_layout = QHBoxLayout()
        vad_layout.addWidget(self._vad_sensitivity_slider)
        vad_layout.addWidget(self._vad_sensitivity_label)
        vad_widget = QWidget()
        vad_widget.setLayout(vad_layout)
        layout.addRow("VAD sensitivity:", vad_widget)

        return widget

    # ---- Connection Tab ----

    def _create_connection_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Server list
        server_group = QGroupBox("Servers")
        server_layout = QVBoxLayout(server_group)

        self._server_list = QListWidget()
        server_layout.addWidget(self._server_list)

        btn_layout = QHBoxLayout()
        self._add_server_btn = QPushButton("Add")
        self._edit_server_btn = QPushButton("Edit")
        self._remove_server_btn = QPushButton("Remove")
        self._add_server_btn.clicked.connect(self._on_add_server)
        self._edit_server_btn.clicked.connect(self._on_edit_server)
        self._remove_server_btn.clicked.connect(self._on_remove_server)
        btn_layout.addWidget(self._add_server_btn)
        btn_layout.addWidget(self._edit_server_btn)
        btn_layout.addWidget(self._remove_server_btn)
        server_layout.addLayout(btn_layout)

        layout.addWidget(server_group)

        # Credentials
        cred_group = QGroupBox("Credentials")
        cred_layout = QFormLayout(cred_group)

        self._username_edit = QLineEdit()
        cred_layout.addRow("Username:", self._username_edit)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("(stored in keyring)")
        cred_layout.addRow("Password:", self._password_edit)

        layout.addWidget(cred_group)

        return widget

    # ---- General Tab ----

    def _create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self._start_minimized_check = QCheckBox("Start minimized")
        layout.addWidget(self._start_minimized_check)

        self._show_tray_check = QCheckBox("Show tray icon")
        layout.addWidget(self._show_tray_check)

        self._compact_mode_check = QCheckBox("Compact mode")
        layout.addWidget(self._compact_mode_check)

        layout.addStretch()
        return widget

    # ---- Load / Apply ----

    def _load_values(self) -> None:
        """Populate widgets from current config."""
        cfg = self._config

        # Audio
        self._input_volume_slider.setValue(cfg.audio.input_volume)
        self._output_volume_slider.setValue(cfg.audio.output_volume)

        # Select current device in combo
        idx = self._input_device_combo.findData(cfg.audio.input_device)
        if idx >= 0:
            self._input_device_combo.setCurrentIndex(idx)
        idx = self._output_device_combo.findData(cfg.audio.output_device)
        if idx >= 0:
            self._output_device_combo.setCurrentIndex(idx)

        # Voice
        mode_idx = self._voice_mode_combo.findData(cfg.ptt.mode)
        if mode_idx >= 0:
            self._voice_mode_combo.setCurrentIndex(mode_idx)
        self._ptt_key_btn.setText(cfg.ptt.evdev_key or "Click to bind...")
        vad_pct = int(cfg.ptt.vad_threshold * 100)
        self._vad_sensitivity_slider.setValue(vad_pct)

        # Connection
        self._username_edit.setText(cfg.server.username)
        self._server_list.addItem(f"{cfg.server.host}:{cfg.server.port}")

        # General
        self._start_minimized_check.setChecked(cfg.ui.start_minimized)
        self._show_tray_check.setChecked(cfg.ui.show_tray_icon)
        self._compact_mode_check.setChecked(cfg.ui.compact_mode)

    def _apply_settings(self) -> None:
        """Write widget values back to config."""
        cfg = self._config

        # Audio
        cfg.audio.input_device = self._input_device_combo.currentData() or ""
        cfg.audio.output_device = self._output_device_combo.currentData() or ""
        cfg.audio.input_volume = self._input_volume_slider.value()
        cfg.audio.output_volume = self._output_volume_slider.value()

        # Voice
        cfg.ptt.mode = self._voice_mode_combo.currentData() or "ptt"
        cfg.ptt.vad_threshold = self._vad_sensitivity_slider.value() / 100.0

        # Connection
        cfg.server.username = self._username_edit.text() or cfg.server.username

        # General
        cfg.ui.start_minimized = self._start_minimized_check.isChecked()
        cfg.ui.show_tray_icon = self._show_tray_check.isChecked()
        cfg.ui.compact_mode = self._compact_mode_check.isChecked()

        try:
            cfg.save()
        except Exception:
            logger.exception("Failed to save settings")

    def _on_ok(self) -> None:
        self._apply_settings()
        self.accept()

    # ---- Placeholder handlers ----

    def _on_test_audio(self) -> None:
        logger.info("Test audio clicked (placeholder)")

    def _on_bind_ptt_key(self) -> None:
        self._ptt_key_btn.setText("Press a key...")
        logger.info("PTT key binding requested (placeholder)")

    def _on_add_server(self) -> None:
        logger.info("Add server (placeholder)")

    def _on_edit_server(self) -> None:
        logger.info("Edit server (placeholder)")

    def _on_remove_server(self) -> None:
        current = self._server_list.currentItem()
        if current is not None:
            row = self._server_list.row(current)
            self._server_list.takeItem(row)
