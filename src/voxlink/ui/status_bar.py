"""Bottom status bar with PTT indicator and audio levels — Fluent Design."""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSizePolicy
from qfluentwidgets import (
    BodyLabel,
    ToggleToolButton,
    FluentIcon,
    PillPushButton,
    ToolTipFilter,
    ToolTipPosition,
    isDarkTheme,
)

logger = logging.getLogger(__name__)


class AudioLevelMeter(QWidget):
    """Custom-painted horizontal audio level bar with Fluent-aware colors."""

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

        dark = isDarkTheme()

        # Background
        bg = QColor("#2d2d2d") if dark else QColor("#e5e5e5")
        painter.fillRect(0, 0, w, h, bg)

        # Level bar with gradient from green to yellow to red
        bar_width = int(w * self._level)
        if bar_width > 0:
            if self._level < 0.6:
                color = QColor("#4ade80") if dark else QColor("#22c55e")
            elif self._level < 0.85:
                color = QColor("#fbbf24") if dark else QColor("#eab308")
            else:
                color = QColor("#ef4444") if dark else QColor("#dc2626")
            painter.fillRect(0, 0, bar_width, h, color)

        # Rounded border
        border = QColor(80, 80, 80) if dark else QColor(180, 180, 180)
        painter.setPen(border)
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)
        painter.end()


class StatusBar(QWidget):
    """Status bar showing PTT state, audio levels, and mute/deafen controls.

    Components:
    - PTT indicator (PillPushButton, green when active, grey when idle)
    - Audio input level meter (custom painted, Fluent-aware)
    - Mute/Deafen toggle buttons (ToggleToolButton with FluentIcon)
    - Connection status text (BodyLabel)
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

        # PTT indicator — PillPushButton used purely as a visual indicator
        self._ptt_pill = PillPushButton("PTT")
        self._ptt_pill.setFixedWidth(56)
        self._ptt_pill.setEnabled(False)  # not interactive
        self._ptt_pill.setStyleSheet(
            "PillPushButton { background-color: #555; color: white; "
            "border-radius: 14px; font-weight: bold; }"
        )
        self._ptt_pill.installEventFilter(
            ToolTipFilter(self._ptt_pill, showDelay=300, position=ToolTipPosition.TOP)
        )
        self._ptt_pill.setToolTip("Push-to-Talk indicator")
        layout.addWidget(self._ptt_pill)

        # Audio input level meter
        in_label = BodyLabel("In:")
        layout.addWidget(in_label)
        self._level_meter = AudioLevelMeter()
        self._level_meter.installEventFilter(
            ToolTipFilter(self._level_meter, showDelay=300, position=ToolTipPosition.TOP)
        )
        self._level_meter.setToolTip("Input audio level")
        layout.addWidget(self._level_meter)

        # Mute button
        self._mute_btn = ToggleToolButton(FluentIcon.MICROPHONE)
        self._mute_btn.installEventFilter(
            ToolTipFilter(self._mute_btn, showDelay=300, position=ToolTipPosition.TOP)
        )
        self._mute_btn.setToolTip("Toggle microphone mute (Ctrl+M)")
        self._mute_btn.clicked.connect(self._on_mute_clicked)
        layout.addWidget(self._mute_btn)

        # Deafen button
        self._deafen_btn = ToggleToolButton(FluentIcon.HEADPHONE)
        self._deafen_btn.installEventFilter(
            ToolTipFilter(self._deafen_btn, showDelay=300, position=ToolTipPosition.TOP)
        )
        self._deafen_btn.setToolTip("Toggle audio deafen (Ctrl+D)")
        self._deafen_btn.clicked.connect(self._on_deafen_clicked)
        layout.addWidget(self._deafen_btn)

        # Connection status
        self._status_label = BodyLabel("Disconnected")
        self._status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._status_label)

    def _on_mute_clicked(self) -> None:
        checked = self._mute_btn.isChecked()
        self._is_muted = checked
        self._mute_btn.setIcon(FluentIcon.MUTE if checked else FluentIcon.MICROPHONE)
        self._mute_btn.setToolTip("Unmute (Ctrl+M)" if checked else "Toggle microphone mute (Ctrl+M)")
        self.mute_toggled.emit(checked)

    def _on_deafen_clicked(self) -> None:
        checked = self._deafen_btn.isChecked()
        self._is_deafened = checked
        self._deafen_btn.setToolTip(
            "Undeafen (Ctrl+D)" if checked else "Toggle audio deafen (Ctrl+D)"
        )
        self.deafen_toggled.emit(checked)

    def set_ptt_active(self, active: bool) -> None:
        """Update the PTT indicator state."""
        if active:
            self._ptt_pill.setStyleSheet(
                "PillPushButton { background-color: #4ade80; color: white; "
                "border-radius: 14px; font-weight: bold; }"
            )
        else:
            self._ptt_pill.setStyleSheet(
                "PillPushButton { background-color: #555; color: white; "
                "border-radius: 14px; font-weight: bold; }"
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
        self._is_muted = muted
        self._mute_btn.setIcon(FluentIcon.MUTE if muted else FluentIcon.MICROPHONE)
        self._mute_btn.setToolTip(
            "Unmute (Ctrl+M)" if muted else "Toggle microphone mute (Ctrl+M)"
        )
        self.mute_toggled.emit(muted)

    def set_deafened(self, deafened: bool) -> None:
        """Programmatically set deafen state (e.g. from keyboard shortcut)."""
        self._deafen_btn.setChecked(deafened)
        self._is_deafened = deafened
        self._deafen_btn.setToolTip(
            "Undeafen (Ctrl+D)" if deafened else "Toggle audio deafen (Ctrl+D)"
        )
        self.deafen_toggled.emit(deafened)
