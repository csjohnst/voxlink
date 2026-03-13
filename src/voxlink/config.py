"""TOML configuration management for VoxLink."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "voxlink"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"


@dataclass
class ServerConfig:
    """Mumble server connection settings."""

    host: str = "localhost"
    port: int = 64738
    username: str = "VoxLinkUser"
    auto_connect: bool = False


@dataclass
class AudioConfig:
    """Audio device and quality settings."""

    input_device: str = ""
    output_device: str = ""
    input_volume: int = 80
    output_volume: int = 100
    quality: str = "high"
    noise_suppression: bool = True


@dataclass
class PTTConfig:
    """Push-to-talk and voice activation settings."""

    mode: str = "ptt"
    shortcut_method: str = "portal"
    evdev_key: str = "KEY_F13"
    vad_threshold: float = 0.02


@dataclass
class UIConfig:
    """User interface settings."""

    theme: str = "auto"  # "auto", "dark", "light"
    start_minimized: bool = False
    show_tray_icon: bool = True
    compact_mode: bool = False


@dataclass
class VoxLinkConfig:
    """Top-level VoxLink configuration."""

    server: ServerConfig = field(default_factory=ServerConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    ptt: PTTConfig = field(default_factory=PTTConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> VoxLinkConfig:
        """Load configuration from a TOML file.

        Args:
            path: Path to config file. Uses default if None.

        Returns:
            Loaded configuration, or defaults if file doesn't exist.
        """
        path = path or DEFAULT_CONFIG_PATH
        if not path.exists():
            logger.info("No config file found at %s, using defaults", path)
            return cls()

        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to parse config at %s, using defaults", path)
            return cls()

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> VoxLinkConfig:
        """Build config from a parsed TOML dictionary."""
        return cls(
            server=_update_dataclass(ServerConfig(), data.get("server", {})),
            audio=_update_dataclass(AudioConfig(), data.get("audio", {})),
            ptt=_update_dataclass(PTTConfig(), data.get("ptt", {})),
            ui=_update_dataclass(UIConfig(), data.get("ui", {})),
        )

    def save(self, path: Path | None = None) -> None:
        """Save configuration to a TOML file.

        Args:
            path: Path to config file. Uses default if None.
        """
        path = path or DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "server": asdict(self.server),
            "audio": asdict(self.audio),
            "ptt": asdict(self.ptt),
            "ui": asdict(self.ui),
        }
        path.write_text(tomli_w.dumps(data), encoding="utf-8")
        logger.info("Config saved to %s", path)


def _update_dataclass[T](instance: T, overrides: dict[str, Any]) -> T:
    """Apply dictionary overrides to a dataclass instance."""
    valid_fields = {f.name for f in fields(instance)}  # type: ignore[arg-type]
    for key, value in overrides.items():
        if key in valid_fields:
            setattr(instance, key, value)
        else:
            logger.warning("Unknown config key ignored: %s", key)
    return instance
