"""Compact floating overlay showing channel users and talking state."""

from __future__ import annotations

import time
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, QPoint, Signal
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QMouseEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow

logger = logging.getLogger(__name__)

# Talking indicator colors
_COLOR_TALKING = QColor("#4ade80")
_COLOR_IDLE = QColor(180, 180, 180)
_COLOR_BG = QColor(30, 30, 30, 200)  # semi-transparent dark
_COLOR_BG_LIGHT = QColor(240, 240, 240, 200)  # semi-transparent light
_COLOR_BORDER = QColor(80, 80, 80, 150)


class _UserRow(QWidget):
    """Single user row in the compact overlay."""

    def __init__(self, name: str, session_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session_id = session_id
        self._talking = False
        self._last_spoke: float | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        # Talking indicator dot
        self._dot = QLabel()
        self._dot.setFixedSize(10, 10)
        self._update_dot()
        layout.addWidget(self._dot)

        # Username
        self._name_label = QLabel(name)
        self._name_label.setStyleSheet("color: white; font-size: 12px;")
        layout.addWidget(self._name_label, 1)

        # Time since last spoke
        self._time_label = QLabel("")
        self._time_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 10px;")
        self._time_label.setMinimumWidth(30)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._time_label)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(24)

    def set_talking(self, talking: bool) -> None:
        self._talking = talking
        if talking:
            self._last_spoke = time.monotonic()
        self._update_dot()

    def update_time_label(self) -> None:
        if self._talking:
            self._time_label.setText("")
            return
        if self._last_spoke is None:
            self._time_label.setText("")
            return
        elapsed = time.monotonic() - self._last_spoke
        if elapsed < 60:
            self._time_label.setText(f"{int(elapsed)}s")
        elif elapsed < 3600:
            self._time_label.setText(f"{int(elapsed // 60)}m")
        else:
            self._time_label.setText("")
            self._last_spoke = None  # stop showing after 1h

    def _update_dot(self) -> None:
        color = _COLOR_TALKING if self._talking else _COLOR_IDLE
        self._dot.setStyleSheet(
            f"background-color: {color.name()}; "
            f"border-radius: 5px; "
            f"min-width: 10px; max-width: 10px; "
            f"min-height: 10px; max-height: 10px;"
        )


class CompactOverlay(QWidget):
    """Floating translucent overlay showing users and talking state.

    Signals:
        restore_requested: Emitted when user wants to return to full app.
    """

    restore_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(180)
        self.setMaximumWidth(280)

        self._user_rows: dict[int, _UserRow] = {}  # session_id -> row
        self._drag_pos: QPoint | None = None

        # Main layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # Header
        self._header = QLabel("  VoxLink")
        self._header.setStyleSheet(
            "color: #4ade80; font-size: 11px; font-weight: bold; padding: 4px 6px;"
        )
        self._header.setFixedHeight(22)
        self._layout.addWidget(self._header)

        # User list container
        self._user_container = QWidget()
        self._user_layout = QVBoxLayout(self._user_container)
        self._user_layout.setContentsMargins(0, 0, 0, 0)
        self._user_layout.setSpacing(0)
        self._layout.addWidget(self._user_container)

        # Update timer for "last spoke" labels
        # Fast timer for talking decay (200ms) and time label updates
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_time_labels)
        self._update_timer.start(200)

        self.adjustSize()

    def paintEvent(self, event) -> None:
        """Draw rounded semi-transparent background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(_COLOR_BG))
        painter.setPen(QPen(_COLOR_BORDER, 1))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
        painter.end()

    def set_users(self, users: dict) -> None:
        """Update the user list. users: {session_id: {"name": str, ...}}"""
        current_sessions = set(self._user_rows.keys())
        new_sessions = set()

        for session_id, user_data in users.items():
            new_sessions.add(session_id)
            if session_id not in self._user_rows:
                row = _UserRow(user_data.get("name", "Unknown"), session_id)
                self._user_rows[session_id] = row
                self._user_layout.addWidget(row)

        # Remove users that left
        for session_id in current_sessions - new_sessions:
            row = self._user_rows.pop(session_id)
            self._user_layout.removeWidget(row)
            row.deleteLater()

        self.adjustSize()

    def add_user(self, session_id: int, name: str) -> None:
        if session_id not in self._user_rows:
            row = _UserRow(name, session_id)
            self._user_rows[session_id] = row
            self._user_layout.addWidget(row)
            self.adjustSize()

    def remove_user(self, session_id: int) -> None:
        row = self._user_rows.pop(session_id, None)
        if row is not None:
            self._user_layout.removeWidget(row)
            row.deleteLater()
            self.adjustSize()

    def set_user_talking(self, session_id: int) -> None:
        row = self._user_rows.get(session_id)
        if row is not None:
            row.set_talking(True)

    def clear_users(self) -> None:
        for row in self._user_rows.values():
            self._user_layout.removeWidget(row)
            row.deleteLater()
        self._user_rows.clear()
        self.adjustSize()

    def _update_time_labels(self) -> None:
        for row in self._user_rows.values():
            # Decay talking state after 200ms of no audio
            if row._talking and row._last_spoke is not None:
                if time.monotonic() - row._last_spoke > 0.2:
                    row.set_talking(False)
            row.update_time_label()

    # ---- Dragging ----

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Double-click to restore full app."""
        self.restore_requested.emit()
        event.accept()
