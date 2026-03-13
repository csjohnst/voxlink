"""Bottom status bar with PTT indicator and audio levels."""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)

logger = logging.getLogger(__name__)


class AudioLevelMeter(QWidget):
    """Custom-painted horizontal audio level bar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._level: float = 0.0
        self.setFixedHeight(16)
        self.setMinimumWidth(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_level(self, level: float) -> None:
        """Set level (0.0 - 1.0) and repaint."""
        self._level = max(0.0, min(1.0, level))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor(60, 60, 60))

        # Level bar with gradient from green to yellow to red
        bar_width = int(w * self._level)
        if bar_width > 0:
            if self._level < 0.6:
                color = QColor(76, 175, 80)  # green
            elif self._level < 0.85:
                color = QColor(255, 193, 7)  # yellow
            else:
                color = QColor(244, 67, 54)  # red
            painter.fillRect(0, 0, bar_width, h, color)

        # Border
        painter.setPen(QColor(100, 100, 100))
        painter.drawRect(0, 0, w - 1, h - 1)
        painter.end()


class StatusBar(QWidget):
    """Status bar showing PTT state, audio levels, and mute/deafen controls.

    Components:
    - PTT indicator (grey idle, green transmitting)
    - Audio input level meter (horizontal bar)
    - Mute/Deafen toggle buttons
    - Connection status text
    """

    mute_toggled = Signal(bool)
    deafen_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_muted = False
        self._is_deafened = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        # PTT indicator
        self._ptt_label = QLabel("PTT")
        self._ptt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ptt_label.setFixedWidth(48)
        self._ptt_label.setStyleSheet(
            "QLabel { background-color: #555; color: white; "
            "border-radius: 4px; padding: 2px 6px; font-weight: bold; }"
        )
        self._ptt_label.setToolTip("Push-to-Talk indicator")
        layout.addWidget(self._ptt_label)

        # Audio input level meter
        layout.addWidget(QLabel("In:"))
        self._level_meter = AudioLevelMeter()
        self._level_meter.setToolTip("Input audio level")
        layout.addWidget(self._level_meter)

        # Mute button
        self._mute_btn = QPushButton("Mute")
        self._mute_btn.setCheckable(True)
        self._mute_btn.setFixedWidth(70)
        self._mute_btn.setToolTip("Toggle microphone mute (Ctrl+M)")
        self._mute_btn.clicked.connect(self._on_mute_clicked)
        layout.addWidget(self._mute_btn)

        # Deafen button
        self._deafen_btn = QPushButton("Deafen")
        self._deafen_btn.setCheckable(True)
        self._deafen_btn.setFixedWidth(70)
        self._deafen_btn.setToolTip("Toggle audio deafen (Ctrl+D)")
        self._deafen_btn.clicked.connect(self._on_deafen_clicked)
        layout.addWidget(self._deafen_btn)

        # Connection status
        self._status_label = QLabel("Disconnected")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._status_label)

    def _on_mute_clicked(self, checked: bool) -> None:
        self._is_muted = checked
        self._mute_btn.setText("Unmute" if checked else "Mute")
        self._mute_btn.setStyleSheet(
            "QPushButton { background-color: #c62828; color: white; }" if checked else ""
        )
        self.mute_toggled.emit(checked)

    def _on_deafen_clicked(self, checked: bool) -> None:
        self._is_deafened = checked
        self._deafen_btn.setText("Undeafen" if checked else "Deafen")
        self._deafen_btn.setStyleSheet(
            "QPushButton { background-color: #e65100; color: white; }" if checked else ""
        )
        self.deafen_toggled.emit(checked)

    def set_ptt_active(self, active: bool) -> None:
        """Update the PTT indicator state."""
        if active:
            self._ptt_label.setStyleSheet(
                "QLabel { background-color: #4caf50; color: white; "
                "border-radius: 4px; padding: 2px 6px; font-weight: bold; }"
            )
        else:
            self._ptt_label.setStyleSheet(
                "QLabel { background-color: #555; color: white; "
                "border-radius: 4px; padding: 2px 6px; font-weight: bold; }"
            )

    def set_input_level(self, level: float) -> None:
        """Update the input audio level meter (0.0 - 1.0)."""
        self._level_meter.set_level(level)

    def set_connection_status(self, text: str) -> None:
        """Update the connection status text."""
        self._status_label.setText(text)

    def set_muted(self, muted: bool) -> None:
        """Programmatically set mute state (e.g. from keyboard shortcut)."""
        self._mute_btn.setChecked(muted)
        self._on_mute_clicked(muted)

    def set_deafened(self, deafened: bool) -> None:
        """Programmatically set deafen state (e.g. from keyboard shortcut)."""
        self._deafen_btn.setChecked(deafened)
        self._on_deafen_clicked(deafened)
