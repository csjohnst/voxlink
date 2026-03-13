"""Channel and user tree widget."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QTreeWidget

logger = logging.getLogger(__name__)


class ChannelTree(QTreeWidget):
    """Displays the server channel hierarchy with users.

    Channels are top-level items; users are children of their
    current channel. Icons indicate user state (talking, muted, deafened).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderLabel("Channels")

    def update_channels(self, channels: dict) -> None:
        """Rebuild the channel tree from server data."""
        raise NotImplementedError

    def update_user(self, user_data: dict) -> None:
        """Update a single user's display state."""
        raise NotImplementedError
