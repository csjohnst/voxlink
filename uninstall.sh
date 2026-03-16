#!/bin/bash
set -e
echo "=== VoxLink Uninstaller ==="

# Desktop file
if [ -f ~/.local/share/applications/voxlink.desktop ]; then
  rm ~/.local/share/applications/voxlink.desktop
  echo "Removed desktop entry"
fi

# Icon
if [ -f ~/.local/share/icons/hicolor/scalable/apps/voxlink.svg ]; then
  rm ~/.local/share/icons/hicolor/scalable/apps/voxlink.svg
  echo "Removed icon"
fi

# Launcher script
if [ -f ~/.local/bin/voxlink ]; then
  rm ~/.local/bin/voxlink
  echo "Removed launcher script"
fi

# Virtual environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SCRIPT_DIR/.venv" ]; then
  rm -rf "$SCRIPT_DIR/.venv"
  echo "Removed virtual environment"
fi

echo ""
echo "=== Uninstall complete! ==="
echo "System packages (python, pipewire, etc.) were not removed."
echo "Remove the project directory manually if desired: rm -rf $SCRIPT_DIR"
