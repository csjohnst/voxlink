# Product Requirements Document: VoxLink

## Overview

VoxLink is a lightweight, Wayland-native voice chat client for Arch Linux that connects to existing Mumble/Murmur servers. It replaces the poorly-maintained Mumble client with a modern app built specifically for Hyprland and KDE Plasma on Wayland.

## Problem Statement

The official Mumble client has deteriorated support for modern Wayland compositors, particularly Hyprland and KDE Plasma. Key issues include broken global shortcuts (Push-To-Talk), unreliable audio device selection under PipeWire, and visual glitches on wlroots-based compositors. VoxLink solves this by building a clean, modern client from scratch using the Mumble protocol.

## Target Environment

- **OS**: Arch Linux (rolling release)
- **Primary DE**: Hyprland (wlroots-based Wayland compositor)
- **Secondary DE**: KDE Plasma 6 (Wayland session)
- **Audio**: PipeWire (with pipewire-pulse compatibility layer)
- **Display Protocol**: Wayland exclusively (no X11/Xwayland fallback required)

## Core Features

### 1. Mumble Server Connectivity
- Connect to any standard Mumble/Murmur server (protocol version 1.5.x)
- Support for username/password authentication
- TLS encrypted connections
- Server browser showing channels and connected users
- Channel navigation (join, switch channels)
- Display user states (muted, deafened, talking)

### 2. Audio I/O with Device Selection
- Enumerate all PipeWire audio sources (microphones) and sinks (speakers/headphones)
- Dropdown selection for input and output devices in settings
- Real-time device hot-swap (detect new/removed devices)
- Audio level meters for input monitoring (so user can verify mic is working)
- Opus codec encoding/decoding (Mumble standard)
- Configurable audio quality/bitrate
- Volume controls for input gain and output volume

### 3. Push-To-Talk (PTT) via Global Shortcut
- Wayland-native global keyboard shortcut binding using `xdg-desktop-portal` GlobalShortcuts API
- Works on both Hyprland (via `xdg-desktop-portal-hyprland`) and KDE Plasma (via `xdg-desktop-portal-kde`)
- User-configurable PTT key binding through the UI
- Visual indicator showing when PTT is active (transmitting)
- Fallback: if portal GlobalShortcuts unavailable, support evdev direct input reading as secondary method
- Optional: Voice Activity Detection (VAD) mode as alternative to PTT

### 4. User Interface
- **Toolkit**: Qt6 (PySide6) — native feel on KDE, works well on Hyprland via qt6-wayland
- **Layout**: Compact single-window design
  - Left panel: Channel tree with users
  - Right panel: Chat/status area
  - Bottom bar: PTT status, audio levels, mute/deafen buttons
  - System tray icon with status indicator
- **Settings dialog**: Audio device selection, PTT key binding, server management, audio quality
- **Theme**: Follows system Qt theme (works with both Breeze on KDE and qt6ct on Hyprland)
- Minimal, clean aesthetic — not trying to clone Mumble's UI, just the functionality

## Technical Architecture

### Language & Framework
- **Python 3.12+** with **PySide6** (Qt6 bindings)
- Chosen for rapid development and good Qt6/PipeWire ecosystem support

### Key Dependencies
| Component | Library | Purpose |
|-----------|---------|---------|
| Mumble Protocol | `pymumble` (sourcehut 2.0 fork) | Mumble server connection, audio send/receive |
| Audio I/O | `pulsectl` + PipeWire-pulse | Device enumeration and selection |
| Audio Streaming | PulseAudio Simple API via `pasimple` | Low-latency audio capture/playback |
| Opus Codec | `opuslib` / system `libopus` | Audio encoding/decoding (handled by pymumble) |
| UI Framework | `PySide6` | Qt6 GUI |
| Global Shortcuts | D-Bus (`dbus-next`) | xdg-desktop-portal GlobalShortcuts interface |
| Configuration | `tomli` / `tomli-w` | TOML config file management |
| System Tray | PySide6 QSystemTrayIcon | Tray icon with status |

### Audio Pipeline
```
Microphone → PipeWire (via pulse-simple) → PCM capture → Opus encode → pymumble send
pymumble receive → Opus decode → PCM playback → PipeWire (via pulse-simple) → Speakers
```

### Global Shortcuts Architecture
```
xdg-desktop-portal D-Bus interface
    ├── Hyprland: xdg-desktop-portal-hyprland (GlobalShortcuts portal)
    └── KDE: xdg-desktop-portal-kde (GlobalShortcuts portal)

App registers shortcut via D-Bus → Portal presents bind dialog → User binds key
Portal emits Activated/Deactivated signals → App starts/stops transmitting
```

**Fallback chain**:
1. xdg-desktop-portal GlobalShortcuts (preferred, works on both DEs)
2. evdev direct input reading (requires user in `input` group, works everywhere)
3. Window-focused Qt key events (only when app is focused, worst case)

### Project Structure
```
voxlink/
├── pyproject.toml              # Project metadata, dependencies
├── README.md
├── src/
│   └── voxlink/
│       ├── __init__.py
│       ├── __main__.py         # Entry point
│       ├── app.py              # QApplication setup, main window
│       ├── config.py           # TOML config management
│       ├── mumble/
│       │   ├── __init__.py
│       │   ├── client.py       # Mumble connection manager (wraps pymumble)
│       │   └── events.py       # Qt signals for mumble events
│       ├── audio/
│       │   ├── __init__.py
│       │   ├── devices.py      # PipeWire device enumeration via pulsectl
│       │   ├── capture.py      # Microphone capture stream
│       │   └── playback.py     # Speaker playback stream
│       ├── shortcuts/
│       │   ├── __init__.py
│       │   ├── portal.py       # xdg-desktop-portal GlobalShortcuts via D-Bus
│       │   ├── evdev.py        # Fallback evdev input reader
│       │   └── manager.py      # Shortcut strategy selector
│       └── ui/
│           ├── __init__.py
│           ├── main_window.py  # Main window layout
│           ├── channel_tree.py # Channel/user tree widget
│           ├── status_bar.py   # Bottom bar with PTT status, levels
│           ├── settings.py     # Settings dialog
│           └── tray.py         # System tray icon
├── resources/
│   ├── icons/                  # App icons (SVG)
│   └── voxlink.desktop         # Desktop entry file
└── tests/
    ├── test_config.py
    ├── test_devices.py
    └── test_shortcuts.py
```

### Configuration File
Stored at `~/.config/voxlink/config.toml`:
```toml
[server]
host = "mumble.example.com"
port = 64738
username = "chris"
# password stored in system keyring, not plaintext

[audio]
input_device = "alsa_input.usb-device"    # PipeWire device name
output_device = "alsa_output.pci-device"
input_volume = 80       # 0-100
output_volume = 100     # 0-100
quality = "high"        # low/medium/high (maps to opus bitrate)
noise_suppression = true

[ptt]
mode = "ptt"            # "ptt" or "vad" or "continuous"
shortcut_method = "portal"  # "portal" or "evdev"
evdev_key = "KEY_F13"   # Only used if method = evdev
vad_threshold = 0.02    # Only used if mode = vad

[ui]
start_minimized = false
show_tray_icon = true
compact_mode = false
```

## Non-Functional Requirements

- **Latency**: Audio round-trip should be under 100ms (comparable to Mumble)
- **CPU**: Idle CPU usage under 2%, active voice under 5%
- **Memory**: Under 150MB RAM
- **Startup**: Under 3 seconds to connected state
- **Reliability**: Auto-reconnect on connection loss with exponential backoff

## Out of Scope (v1)

- Positional audio
- Certificate-based authentication (username/password only for v1)
- Text chat (display only, no send — focus is voice)
- Server administration features
- Recording
- Noise cancellation (can be added later via RNNoise)
- Flatpak/Snap packaging

## Success Criteria

1. Can connect to a Mumble server, join channels, and hear other users
2. PTT works globally in both Hyprland and KDE Plasma (window doesn't need focus)
3. Audio input/output device can be selected and changed without restarting
4. App appears in system tray with status indicator
5. No crashes or audio glitches during normal 2+ hour voice sessions
