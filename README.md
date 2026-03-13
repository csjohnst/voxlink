# VoxLink

Wayland-native Mumble voice chat client for Arch Linux. Built for Hyprland and KDE Plasma.

## System Dependencies

```bash
sudo pacman -S python python-pip pipewire pipewire-pulse opus qt6-wayland \
  xdg-desktop-portal xdg-desktop-portal-hyprland pyside6
```

For KDE Plasma, replace `xdg-desktop-portal-hyprland` with `xdg-desktop-portal-kde`.

## Install (Arch Linux package)

Builds a self-contained single binary and installs it as a pacman package:

```bash
git clone https://github.com/csjohnst/voxlink.git
cd voxlink
makepkg -si
```

This installs `/usr/bin/voxlink` with a desktop entry and icon. No Python runtime needed at install time — everything is bundled.

To uninstall: `sudo pacman -R voxlink`

## Install (development)

```bash
git clone https://github.com/csjohnst/voxlink.git
cd voxlink
pip install -e ".[dev,evdev]"
```

## Usage

```bash
# Launch the GUI
voxlink

# Test connection to a server
voxlink --test-connection --server mumble.example.com --user testuser

# List audio devices
voxlink --list-devices

# Test PTT shortcut
voxlink --test-ptt
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
