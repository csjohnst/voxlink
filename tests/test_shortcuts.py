"""Tests for shortcut manager."""

from voxlink.config import PTTConfig
from voxlink.shortcuts.manager import ShortcutManager


def test_shortcut_manager_init():
    """ShortcutManager initializes with no active method."""
    config = PTTConfig()
    manager = ShortcutManager(config)
    assert manager.active_method == "none"
