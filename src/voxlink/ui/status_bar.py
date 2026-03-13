"""Bottom status bar with PTT indicator and audio levels."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class StatusBar(QWidget):
    """Status bar showing PTT state, audio levels, and mute/deafen controls.

    Components:
    - PTT indicator (grey idle, green transmitting)
    - Audio input level meter (horizontal bar)
    - Mute/Deafen toggle buttons
    - Connection status text
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    def set_ptt_active(self, active: bool) -> None:
        """Update the PTT indicator state."""
        raise NotImplementedError

    def set_input_level(self, level: float) -> None:
        """Update the input audio level meter (0.0 - 1.0)."""
        raise NotImplementedError

    def set_connection_status(self, text: str) -> None:
        """Update the connection status text."""
        raise NotImplementedError
