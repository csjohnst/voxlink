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

## Moving between channels

Drag your own name onto a channel (or onto someone already in it), or
double-click the channel. Your name is shown in bold. Dragging another user
onto a channel asks the server to move them, which needs Move permission
there.

## Configuration

Config is stored at `~/.config/voxlink/config.toml`. A default config is created on first run.

### Client certificates

Mumble servers register usernames against a client certificate. If a server
rejects you with "Wrong certificate or password for existing user", point
VoxLink at the same certificate your Mumble desktop client uses:

```toml
[server]
certfile = "~/.config/voxlink/certs/client.pem"
keyfile = "~/.config/voxlink/certs/client.key"
```

Mumble exports certificates as PKCS#12 (`.p12`, usually with an empty
passphrase). Convert to the PEM pair pymumble expects:

```bash
openssl pkcs12 -in cert.p12 -legacy -passin pass: -clcerts -nokeys -out client.pem
openssl pkcs12 -in cert.p12 -legacy -passin pass: -nocerts -nodes -out client.key
chmod 600 client.pem client.key
```

Verify with `voxlink --test-connection --server HOST --user NAME` (it reads the
certificate from the config, or pass `--cert`/`--key` explicitly).

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

GPL-3.0 — see [LICENSE](LICENSE) for details.
