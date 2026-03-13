"""Integration tests for VoxLink (headless/offscreen)."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtWidgets import QApplication
from voxlink.config import VoxLinkConfig
from voxlink.audio.devices import DeviceManager, AudioDevice
from voxlink.audio.capture import CaptureManager
from voxlink.audio.playback import PlaybackManager
from voxlink.mumble.client import MumbleClient, ConnectionState
from voxlink.shortcuts.manager import ShortcutManager
from voxlink.ui.main_window import MainWindow
from voxlink.ui.status_bar import StatusBar, AudioLevelMeter
from voxlink.ui.channel_tree import ChannelTree
from voxlink.ui.tray import TrayIcon
from voxlink.ui.settings import SettingsPage


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def config():
    return VoxLinkConfig()


@pytest.fixture
def managers(config):
    dm = DeviceManager()
    cm = CaptureManager(config.audio)
    pm = PlaybackManager(config.audio)
    mc = MumbleClient(config.server)
    sm = ShortcutManager(config.ptt)
    return dm, cm, pm, mc, sm


def test_main_window_creation(qapp, config, managers):
    dm, cm, pm, mc, sm = managers
    window = MainWindow(config=config, device_manager=dm, capture_manager=cm,
                       playback_manager=pm, mumble_client=mc, shortcut_manager=sm)
    assert window.windowTitle().startswith("VoxLink")
    assert window.minimumWidth() >= 600
    assert window.minimumHeight() >= 400


def test_status_bar_ptt_indicator(qapp):
    bar = StatusBar()
    bar.set_ptt_active(True)
    bar.set_ptt_active(False)
    bar.set_input_level(0.5)
    bar.set_connection_status("Test")


def test_channel_tree_update(qapp):
    tree = ChannelTree()
    channels = {
        0: {"channel_id": 0, "name": "Root", "parent": None, "position": 0},
        1: {"channel_id": 1, "name": "General", "parent": 0, "position": 0},
        2: {"channel_id": 2, "name": "AFK", "parent": 0, "position": 1},
    }
    users = {
        1: {"session": 1, "name": "Alice", "channel_id": 1, "mute": False, "deaf": False},
        2: {"session": 2, "name": "Bob", "channel_id": 1, "mute": True, "deaf": False},
    }
    tree.update_channels(channels, users)
    assert tree.topLevelItemCount() >= 1


def test_tray_icon_creation(qapp, config, managers):
    dm, cm, pm, mc, sm = managers
    window = MainWindow(config=config, device_manager=dm, capture_manager=cm,
                       playback_manager=pm, mumble_client=mc, shortcut_manager=sm)
    tray = TrayIcon(window, config.ui)
    tray.set_connected()
    tray.set_disconnected()


def test_settings_page_creation(qapp, config):
    dm = DeviceManager()
    page = SettingsPage(config, dm)
    assert page.objectName() == "settingsPage"


def test_mumble_client_initial_state(config):
    mc = MumbleClient(config.server)
    assert mc.state == ConnectionState.DISCONNECTED
    assert mc.get_channels() == {}
    assert mc.get_users() == {}


def test_audio_level_meter(qapp):
    meter = AudioLevelMeter()
    meter.set_level(0.0)
    meter.set_level(0.5)
    meter.set_level(1.0)
    meter.set_level(1.5)  # should clamp to 1.0


def test_connection_state_transitions(config):
    mc = MumbleClient(config.server)
    assert mc.state == ConnectionState.DISCONNECTED
    # disconnect when already disconnected should be safe
    mc.disconnect()
    assert mc.state == ConnectionState.DISCONNECTED
