"""Channel and user tree widget — Fluent Design."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QDragMoveEvent, QDropEvent, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QTreeWidgetItem
from qfluentwidgets import (
    Action,
    BodyLabel,
    FluentIcon,
    MessageBox,
    RoundMenu,
    Slider,
    TreeWidget,
    isDarkTheme,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# Item data role for storing IDs
_ROLE_ID = Qt.ItemDataRole.UserRole
_ROLE_TYPE = Qt.ItemDataRole.UserRole + 1

_TYPE_CHANNEL = "channel"
_TYPE_USER = "user"


def _channel_flags(flags: Qt.ItemFlag) -> Qt.ItemFlag:
    """Channels accept drops but cannot be dragged."""
    return (flags | Qt.ItemFlag.ItemIsDropEnabled) & ~Qt.ItemFlag.ItemIsDragEnabled


def _user_flags(flags: Qt.ItemFlag) -> Qt.ItemFlag:
    """Users can be dragged; dropping onto a user targets that user's channel."""
    return flags | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled


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
    _ICON_NORMAL = _circle_icon(QColor(180, 180, 180) if dark else QColor(140, 140, 140))
    _ICON_TALKING = _circle_icon(QColor("#4ade80") if dark else QColor("#22c55e"))
    _ICON_MUTED = _circle_icon(QColor("#ef4444") if dark else QColor("#dc2626"))
    _ICON_DEAFENED = _circle_icon(QColor("#fbbf24") if dark else QColor("#eab308"))
    _ICON_CHANNEL = _circle_icon(QColor("#60a5fa") if dark else QColor("#3b82f6"))


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

    Moving between channels: drag your own name onto a channel (or onto a
    user inside it), or double-click the channel. Dragging another user onto
    a channel requests a server-side move of that user (needs Move permission).
    """

    channel_join_requested = Signal(int)
    user_move_requested = Signal(int, int)  # session_id, channel_id
    user_mute_toggled = Signal(int, bool)  # session_id, muted
    user_volume_changed = Signal(int, float)  # session_id, volume (0.0-2.0)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderLabel("Channels")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setAnimated(True)
        self.setIndentation(16)
        # Drag-and-drop: users are draggable, channels (and users, resolving to
        # their channel) accept drops. dropEvent is overridden so Qt never
        # re-parents items itself; the server's UserState update does that.
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._my_session: int | None = None
        self._muted_sessions: set[int] = set()
        self._user_volumes: dict[int, float] = {}  # session -> volume multiplier
        self._talking_sessions: set[int] = set()
        self._talking_timers: dict[int, QTimer] = {}  # session -> decay timer

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
            item.setFlags(_channel_flags(item.flags()))
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
                    channel_items[channel_id].addChild(self._make_user_item(user_data))

        self.expandAll()

    def update_user(self, user_data: dict) -> None:
        """Update a single user's display state."""
        _ensure_icons()
        session = user_data.get("session")
        if session is None:
            return

        item = self._find_user_item(session)
        if item is None:
            # Unknown user (e.g. state arrived before the tree was built)
            self.add_user(user_data)
            return

        item.setText(0, user_data.get("name", item.text(0)))
        item.setIcon(0, _user_icon(user_data))
        self._style_user_item(item, session)

        # Re-parent when the user changed channel; this is what makes a
        # channel move visible (the server confirms it via UserState).
        new_channel = user_data.get("channel_id")
        if new_channel is None:
            return
        current_parent = item.parent()
        current_channel = current_parent.data(0, _ROLE_ID) if current_parent is not None else None
        if new_channel == current_channel:
            return
        target = self._find_channel_item(new_channel)
        if target is None:
            logger.warning("Channel %s not in tree; cannot move %s", new_channel, session)
            return
        if current_parent is not None:
            current_parent.removeChild(item)
        target.addChild(item)
        target.setExpanded(True)

    def add_user(self, user_data: dict) -> None:
        """Add a user to the appropriate channel."""
        _ensure_icons()
        channel_id = user_data.get("channel_id")
        if channel_id is None:
            return

        channel_item = self._find_channel_item(channel_id)
        if channel_item is None:
            return

        channel_item.addChild(self._make_user_item(user_data))

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

    # ---- Own-user tracking ----

    def set_my_session(self, session: int | None) -> None:
        """Tell the tree which session is the local user (bolded; drag = join)."""
        if session == self._my_session:
            return
        old = self._my_session
        self._my_session = session
        for sid in (old, session):
            if sid is None:
                continue
            item = self._find_user_item(sid)
            if item is not None:
                self._style_user_item(item, sid)

    def my_session(self) -> int | None:
        return self._my_session

    def _make_user_item(self, user_data: dict) -> QTreeWidgetItem:
        user_item = QTreeWidgetItem()
        user_item.setText(0, user_data.get("name", "Unknown"))
        user_item.setIcon(0, _user_icon(user_data))
        user_item.setData(0, _ROLE_ID, user_data.get("session"))
        user_item.setData(0, _ROLE_TYPE, _TYPE_USER)
        user_item.setFlags(_user_flags(user_item.flags()))
        self._style_user_item(user_item, user_data.get("session"))
        return user_item

    def _style_user_item(self, item: QTreeWidgetItem, session: int | None) -> None:
        font = item.font(0)
        font.setBold(session is not None and session == self._my_session)
        item.setFont(0, font)

    # ---- Drag and drop ----

    def _channel_id_of_item(self, item: QTreeWidgetItem | None) -> int | None:
        """Resolve an item to a channel id: channels map to themselves, users to their channel."""
        if item is None:
            return None
        if item.data(0, _ROLE_TYPE) == _TYPE_CHANNEL:
            return item.data(0, _ROLE_ID)
        if item.data(0, _ROLE_TYPE) == _TYPE_USER:
            parent = item.parent()
            return parent.data(0, _ROLE_ID) if parent is not None else None
        return None

    def _dragged_item(self) -> QTreeWidgetItem | None:
        selected = self.selectedItems()
        return selected[0] if selected else self.currentItem()

    def _handle_drop(self, dragged: QTreeWidgetItem | None, target: QTreeWidgetItem | None) -> bool:
        """Turn a drop into a join/move request. Returns True if a request was emitted.

        Only user items can be dropped. Dropping onto a user means that user's
        channel. Dropping onto the channel the user is already in is a no-op.
        The local user emits channel_join_requested; anyone else emits
        user_move_requested (the server enforces permission).
        """
        if dragged is None or dragged.data(0, _ROLE_TYPE) != _TYPE_USER:
            return False
        session = dragged.data(0, _ROLE_ID)
        target_channel = self._channel_id_of_item(target)
        if session is None or target_channel is None:
            return False
        if target_channel == self._channel_id_of_item(dragged):
            return False
        if session == self._my_session:
            logger.info("Drag: join channel %s", target_channel)
            self.channel_join_requested.emit(target_channel)
        else:
            logger.info("Drag: move session %s to channel %s", session, target_channel)
            self.user_move_requested.emit(session, target_channel)
        return True

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        super().dragMoveEvent(event)
        target = self.itemAt(event.position().toPoint())
        if self._channel_id_of_item(target) is None:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        target = self.itemAt(event.position().toPoint())
        self._handle_drop(self._dragged_item(), target)
        # Never let Qt re-parent the item; the server's UserState does that.
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()

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

        session_id = item.data(0, _ROLE_ID)
        if session_id is None:
            return

        menu = RoundMenu(parent=self)

        is_muted = session_id in self._muted_sessions
        mute_action = Action(
            FluentIcon.MUTE if not is_muted else FluentIcon.VOLUME,
            "Unmute locally" if is_muted else "Mute locally",
            parent=menu,
        )
        menu.addAction(mute_action)

        volume_action = Action(FluentIcon.VOLUME, "Adjust volume...", parent=menu)
        menu.addAction(volume_action)

        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action == mute_action:
            if is_muted:
                self._muted_sessions.discard(session_id)
            else:
                self._muted_sessions.add(session_id)
            self.user_mute_toggled.emit(session_id, not is_muted)
            # Update icon
            self._update_user_mute_icon(item, not is_muted)

        elif action == volume_action:
            self._show_volume_dialog(session_id, item)

    def _update_user_mute_icon(self, item, muted: bool) -> None:
        """Update user icon to reflect local mute state."""
        _ensure_icons()
        if muted:
            item.setIcon(0, _ICON_MUTED)
        # else restore from user data - we'd need to store it

    def _show_volume_dialog(self, session_id: int, item) -> None:
        """Show a volume adjustment dialog for a user."""
        current_vol = self._user_volumes.get(session_id, 1.0)

        # Create a simple dialog with a slider
        dlg = MessageBox(
            f"Volume: {item.text(0)}",
            "",
            self.window(),
        )

        slider = Slider(Qt.Orientation.Horizontal)
        slider.setRange(0, 200)  # 0% to 200%
        slider.setValue(int(current_vol * 100))

        vol_label = BodyLabel(f"{int(current_vol * 100)}%")
        slider.valueChanged.connect(lambda v: vol_label.setText(f"{v}%"))

        dlg.viewLayout.addWidget(BodyLabel("Volume"))
        dlg.viewLayout.addWidget(slider)
        dlg.viewLayout.addWidget(vol_label)

        dlg.yesButton.setText("Apply")
        dlg.cancelButton.setText("Cancel")

        if dlg.exec():
            new_vol = slider.value() / 100.0
            self._user_volumes[session_id] = new_vol
            self.user_volume_changed.emit(session_id, new_vol)

    def set_user_talking(self, session_id: int) -> None:
        """Mark a user as talking (green icon) with auto-decay."""
        _ensure_icons()
        if session_id not in self._talking_sessions:
            self._talking_sessions.add(session_id)
            # Find and update the icon
            item = self._find_user_item(session_id)
            if item is not None and session_id not in self._muted_sessions:
                item.setIcon(0, _ICON_TALKING)  # type: ignore[arg-type]

        # Reset or create the decay timer (200ms after last audio = stop talking)
        timer = self._talking_timers.get(session_id)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda sid=session_id: self._on_talking_timeout(sid))
            self._talking_timers[session_id] = timer
        timer.start(200)

    def _on_talking_timeout(self, session_id: int) -> None:
        """Clear talking state after no audio for a short period."""
        _ensure_icons()
        self._talking_sessions.discard(session_id)
        item = self._find_user_item(session_id)
        if item is not None:
            if session_id in self._muted_sessions:
                item.setIcon(0, _ICON_MUTED)  # type: ignore[arg-type]
            else:
                item.setIcon(0, _ICON_NORMAL)  # type: ignore[arg-type]

    def _find_user_item(self, session_id: int) -> QTreeWidgetItem | None:
        """Find a user item by session ID across the whole tree."""
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            child = root.child(i)
            if child is None:
                continue
            found = self._find_user_in_subtree(child, session_id)
            if found is not None:
                return found
        return None

    def is_user_muted(self, session_id: int) -> bool:
        """Check if a user is locally muted."""
        return session_id in self._muted_sessions

    def get_user_volume(self, session_id: int) -> float:
        """Get per-user volume multiplier (default 1.0)."""
        return self._user_volumes.get(session_id, 1.0)
