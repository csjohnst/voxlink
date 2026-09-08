"""Tests for ChannelTree: channel moves, own-user tracking, drag-and-drop."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from voxlink.ui.channel_tree import ChannelTree

CHANNELS = {
    0: {"channel_id": 0, "name": "Root", "parent": None, "position": 0},
    1: {"channel_id": 1, "name": "Lobby", "parent": 0, "position": 0},
    3: {"channel_id": 3, "name": "Admin", "parent": 0, "position": 1},
}
USERS = {
    30: {"session": 30, "name": "Chris", "channel_id": 3, "mute": False, "deaf": False},
    2: {"session": 2, "name": "Tim", "channel_id": 3, "mute": False, "deaf": False},
    7: {"session": 7, "name": "Guest", "channel_id": 1, "mute": False, "deaf": False},
}


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def tree(qapp):
    t = ChannelTree()
    t.set_my_session(30)
    t.update_channels(CHANNELS, USERS)
    return t


def _channel_item(tree, cid):
    return tree._find_channel_item(cid)


def _user_item(tree, session):
    return tree._find_user_item(session)


def _collect(signal):
    got = []
    signal.connect(lambda *a: got.append(a))
    return got


def test_update_user_reparents_on_channel_change(tree):
    """A UserState with a new channel_id moves the item under the new channel."""
    assert _user_item(tree, 30).parent() is _channel_item(tree, 3)
    tree.update_user({"session": 30, "name": "Chris", "channel_id": 1})
    assert _user_item(tree, 30).parent() is _channel_item(tree, 1)
    assert _channel_item(tree, 3).childCount() == 1  # only Tim left


def test_update_user_same_channel_only_refreshes(tree):
    tree.update_user({"session": 2, "name": "Tim (away)", "channel_id": 3, "self_mute": True})
    item = _user_item(tree, 2)
    assert item.parent() is _channel_item(tree, 3)
    assert item.text(0) == "Tim (away)"


def test_own_user_is_bold_and_tracks_session_changes(tree):
    assert _user_item(tree, 30).font(0).bold()
    assert not _user_item(tree, 2).font(0).bold()
    tree.set_my_session(2)
    assert not _user_item(tree, 30).font(0).bold()
    assert _user_item(tree, 2).font(0).bold()


def test_item_flags(tree):
    ch = _channel_item(tree, 1).flags()
    assert not (ch & Qt.ItemFlag.ItemIsDragEnabled)
    assert ch & Qt.ItemFlag.ItemIsDropEnabled
    us = _user_item(tree, 30).flags()
    assert us & Qt.ItemFlag.ItemIsDragEnabled


def test_drop_own_user_on_channel_requests_join(tree):
    joins = _collect(tree.channel_join_requested)
    moves = _collect(tree.user_move_requested)
    assert tree._handle_drop(_user_item(tree, 30), _channel_item(tree, 1))
    assert joins == [(1,)]
    assert moves == []


def test_drop_own_user_on_user_targets_that_users_channel(tree):
    joins = _collect(tree.channel_join_requested)
    assert tree._handle_drop(_user_item(tree, 30), _user_item(tree, 7))  # Guest is in Lobby
    assert joins == [(1,)]


def test_drop_other_user_requests_server_move(tree):
    joins = _collect(tree.channel_join_requested)
    moves = _collect(tree.user_move_requested)
    assert tree._handle_drop(_user_item(tree, 2), _channel_item(tree, 1))
    assert moves == [(2, 1)]
    assert joins == []


def test_drop_on_current_channel_is_noop(tree):
    joins = _collect(tree.channel_join_requested)
    assert not tree._handle_drop(_user_item(tree, 30), _channel_item(tree, 3))
    assert not tree._handle_drop(_user_item(tree, 30), _user_item(tree, 2))  # Tim is in Admin too
    assert joins == []


def test_drop_channel_or_nothing_is_ignored(tree):
    joins = _collect(tree.channel_join_requested)
    assert not tree._handle_drop(_channel_item(tree, 1), _channel_item(tree, 3))
    assert not tree._handle_drop(_user_item(tree, 30), None)
    assert joins == []
