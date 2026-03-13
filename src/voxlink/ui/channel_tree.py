"""Channel and user tree widget — Fluent Design."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QPixmap, QPainter, QIcon, QBrush
from PySide6.QtWidgets import QTreeWidgetItem
from qfluentwidgets import TreeWidget, RoundMenu, Action, FluentIcon, isDarkTheme

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# Item data role for storing IDs
_ROLE_ID = Qt.ItemDataRole.UserRole
_ROLE_TYPE = Qt.ItemDataRole.UserRole + 1

_TYPE_CHANNEL = "channel"
_TYPE_USER = "user"


def _circle_icon(color: QColor, size: int = 14) -> QIcon:
    """Generate a small colored circle icon."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.end()
    return QIcon(pixmap)


# Pre-built user state icons (lazily initialised)
_ICON_NORMAL = None
_ICON_TALKING = None
_ICON_MUTED = None
_ICON_DEAFENED = None
_ICON_CHANNEL = None


def _ensure_icons() -> None:
    """Lazily create icons (must be called after QApplication exists)."""
    global _ICON_NORMAL, _ICON_TALKING, _ICON_MUTED, _ICON_DEAFENED, _ICON_CHANNEL
    if _ICON_NORMAL is not None:
        return

    dark = isDarkTheme()

    # Adapt icon colours for dark/light theme
    _ICON_NORMAL = _circle_icon(
        QColor(180, 180, 180) if dark else QColor(140, 140, 140)
    )
    _ICON_TALKING = _circle_icon(
        QColor("#4ade80") if dark else QColor("#22c55e")
    )
    _ICON_MUTED = _circle_icon(
        QColor("#ef4444") if dark else QColor("#dc2626")
    )
    _ICON_DEAFENED = _circle_icon(
        QColor("#fbbf24") if dark else QColor("#eab308")
    )
    _ICON_CHANNEL = _circle_icon(
        QColor("#60a5fa") if dark else QColor("#3b82f6")
    )


def _user_icon(user_data: dict) -> QIcon:
    """Return the appropriate icon for a user's state."""
    _ensure_icons()
    assert _ICON_NORMAL is not None
    if user_data.get("deaf") or user_data.get("self_deaf"):
        return _ICON_DEAFENED  # type: ignore[return-value]
    if user_data.get("mute") or user_data.get("self_mute"):
        return _ICON_MUTED  # type: ignore[return-value]
    return _ICON_NORMAL  # type: ignore[return-value]


class ChannelTree(TreeWidget):
    """Displays the server channel hierarchy with users.

    Channels are top-level items; users are children of their
    current channel. Icons indicate user state (talking, muted, deafened).
    Uses Fluent Design TreeWidget with RoundMenu context menus.
    """

    channel_join_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderLabel("Channels")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setAnimated(True)
        self.setIndentation(16)

    def update_channels(self, channels: dict, users: dict | None = None) -> None:
        """Rebuild the channel tree from server data.

        Args:
            channels: Dict of {channel_id: channel_info}.
            users: Optional dict of {session: user_info}.
        """
        _ensure_icons()
        self.clear()

        # Build channel items keyed by channel_id
        channel_items: dict[int, QTreeWidgetItem] = {}

        # Sort channels by position then name
        sorted_channels = sorted(
            channels.values(),
            key=lambda c: (c.get("position", 0), c.get("name", "")),
        )

        # First pass: create all channel items
        for ch in sorted_channels:
            cid = ch.get("channel_id")
            if cid is None:
                continue
            item = QTreeWidgetItem()
            item.setText(0, ch.get("name", f"Channel {cid}"))
            item.setIcon(0, _ICON_CHANNEL)  # type: ignore[arg-type]
            item.setData(0, _ROLE_ID, cid)
            item.setData(0, _ROLE_TYPE, _TYPE_CHANNEL)
            item.setExpanded(True)
            channel_items[cid] = item

        # Second pass: build hierarchy
        for ch in sorted_channels:
            cid = ch.get("channel_id")
            if cid is None or cid not in channel_items:
                continue
            parent_id = ch.get("parent")
            item = channel_items[cid]
            if parent_id is not None and parent_id in channel_items and parent_id != cid:
                channel_items[parent_id].addChild(item)
            else:
                self.addTopLevelItem(item)

        # Add users to their channels
        if users:
            for user_data in users.values():
                channel_id = user_data.get("channel_id")
                if channel_id is not None and channel_id in channel_items:
                    user_item = QTreeWidgetItem()
                    user_item.setText(0, user_data.get("name", "Unknown"))
                    user_item.setIcon(0, _user_icon(user_data))
                    user_item.setData(0, _ROLE_ID, user_data.get("session"))
                    user_item.setData(0, _ROLE_TYPE, _TYPE_USER)
                    channel_items[channel_id].addChild(user_item)

        self.expandAll()

    def update_user(self, user_data: dict) -> None:
        """Update a single user's display state."""
        _ensure_icons()
        session = user_data.get("session")
        if session is None:
            return

        # Find the user item by session ID
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            channel_item = root.child(i)
            if channel_item is None:
                continue
            item = self._find_user_in_subtree(channel_item, session)
            if item is not None:
                item.setText(0, user_data.get("name", item.text(0)))
                item.setIcon(0, _user_icon(user_data))
                return

    def add_user(self, user_data: dict) -> None:
        """Add a user to the appropriate channel."""
        _ensure_icons()
        channel_id = user_data.get("channel_id")
        if channel_id is None:
            return

        channel_item = self._find_channel_item(channel_id)
        if channel_item is None:
            return

        user_item = QTreeWidgetItem()
        user_item.setText(0, user_data.get("name", "Unknown"))
        user_item.setIcon(0, _user_icon(user_data))
        user_item.setData(0, _ROLE_ID, user_data.get("session"))
        user_item.setData(0, _ROLE_TYPE, _TYPE_USER)
        channel_item.addChild(user_item)

    def remove_user(self, user_data: dict) -> None:
        """Remove a user from the tree."""
        session = user_data.get("session")
        if session is None:
            return

        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            channel_item = root.child(i)
            if channel_item is None:
                continue
            item = self._find_user_in_subtree(channel_item, session)
            if item is not None:
                parent = item.parent()
                if parent is not None:
                    parent.removeChild(item)
                return

    def _find_channel_item(self, channel_id: int) -> QTreeWidgetItem | None:
        """Find a channel item by ID, searching the full tree."""
        root = self.invisibleRootItem()
        return self._find_item_recursive(root, _ROLE_ID, channel_id, _TYPE_CHANNEL)

    def _find_item_recursive(
        self, parent: QTreeWidgetItem, role: int, value: int, type_filter: str
    ) -> QTreeWidgetItem | None:
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child is None:
                continue
            if child.data(0, _ROLE_TYPE) == type_filter and child.data(0, role) == value:
                return child
            found = self._find_item_recursive(child, role, value, type_filter)
            if found is not None:
                return found
        return None

    def _find_user_in_subtree(
        self, parent: QTreeWidgetItem, session: int
    ) -> QTreeWidgetItem | None:
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child is None:
                continue
            if child.data(0, _ROLE_TYPE) == _TYPE_USER and child.data(0, _ROLE_ID) == session:
                return child
            found = self._find_user_in_subtree(child, session)
            if found is not None:
                return found
        return None

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle double-click: join channel if a channel was clicked."""
        if item.data(0, _ROLE_TYPE) == _TYPE_CHANNEL:
            channel_id = item.data(0, _ROLE_ID)
            if channel_id is not None:
                self.channel_join_requested.emit(channel_id)

    def _show_context_menu(self, pos) -> None:
        """Show Fluent RoundMenu context menu for users."""
        item = self.itemAt(pos)
        if item is None or item.data(0, _ROLE_TYPE) != _TYPE_USER:
            return

        menu = RoundMenu(parent=self)
        mute_action = Action(FluentIcon.MUTE, "Mute locally", parent=menu)
        volume_action = Action(FluentIcon.VOLUME, "Adjust volume...", parent=menu)
        menu.addAction(mute_action)
        menu.addAction(volume_action)

        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action == mute_action:
            logger.info(
                "Local mute for user session=%s (placeholder)", item.data(0, _ROLE_ID)
            )
        elif action == volume_action:
            logger.info(
                "Volume adjust for user session=%s (placeholder)", item.data(0, _ROLE_ID)
            )
