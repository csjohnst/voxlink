"""Tests for VoxLink configuration loading and saving."""

from pathlib import Path
from voxlink.config import VoxLinkConfig


def test_default_config():
    """Default config has sensible values."""
    config = VoxLinkConfig()
    assert config.server.host == "localhost"
    assert config.server.port == 64738
    assert config.audio.input_volume == 80
    assert config.ptt.mode == "ptt"
    assert config.ui.show_tray_icon is True


def test_load_missing_file(tmp_path: Path):
    """Loading from a nonexistent path returns defaults."""
    config = VoxLinkConfig.load(tmp_path / "nonexistent.toml")
    assert config.server.host == "localhost"


def test_save_and_load(tmp_path: Path):
    """Config round-trips through save/load."""
    path = tmp_path / "config.toml"
    config = VoxLinkConfig()
    config.server.host = "test.example.com"
    config.audio.input_volume = 50
    config.save(path)

    loaded = VoxLinkConfig.load(path)
    assert loaded.server.host == "test.example.com"
    assert loaded.audio.input_volume == 50
