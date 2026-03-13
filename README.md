# VoxLink

Wayland-native Mumble voice chat client for Arch Linux. Built for Hyprland and KDE Plasma.

## System Dependencies

```bash
sudo pacman -S python python-pip pipewire pipewire-pulse opus qt6-wayland \
  xdg-desktop-portal xdg-desktop-portal-hyprland pyside6
```

For KDE Plasma, replace `xdg-desktop-portal-hyprland` with `xdg-desktop-portal-kde`.

## Install

```bash
# Clone
git clone https://github.com/csjohnst/voxlink.git
cd voxlink

# Install in editable mode
pip install -e ".[dev]"

# Or with evdev fallback support
pip install -e ".[dev,evdev]"
```

## Usage

```bash
# Launch the GUI
python -m voxlink

# Test connection to a server
python -m voxlink --test-connection --server mumble.example.com --user testuser

# List audio devices
python -m voxlink --list-devices

# Test PTT shortcut
python -m voxlink --test-ptt
```

## Configuration

Config is stored at `~/.config/voxlink/config.toml`. A default config is created on first run.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

GPL-3.0 — see [LICENSE](LICENSE) for details.
