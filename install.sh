#!/bin/bash
set -e
echo "=== VoxLink Installer for Arch Linux ==="

# System deps
echo "Installing system dependencies..."
sudo pacman -S --needed --noconfirm python python-pip pipewire pipewire-pulse libopus qt6-wayland \
  xdg-desktop-portal python-pyside6

# Detect portal
if pacman -Q xdg-desktop-portal-hyprland &>/dev/null; then
  echo "Detected xdg-desktop-portal-hyprland"
elif pacman -Q xdg-desktop-portal-kde &>/dev/null; then
  echo "Detected xdg-desktop-portal-kde"
else
  echo "WARNING: No desktop portal detected. Install xdg-desktop-portal-hyprland or xdg-desktop-portal-kde for global shortcuts."
fi

# Venv
echo "Creating virtual environment..."
python -m venv .venv
source .venv/bin/activate

# Install
echo "Installing VoxLink..."
pip install -e ".[dev]"

# Desktop file and icon
echo "Installing desktop file and icon..."
mkdir -p ~/.local/share/applications
cp resources/voxlink.desktop ~/.local/share/applications/
mkdir -p ~/.local/share/icons/hicolor/scalable/apps
cp resources/icons/voxlink.svg ~/.local/share/icons/hicolor/scalable/apps/

# Launcher script
echo "Creating launcher script..."
VENV_PYTHON="$(pwd)/.venv/bin/python"
mkdir -p ~/.local/bin
cat > ~/.local/bin/voxlink << LAUNCHER
#!/bin/bash
exec "$VENV_PYTHON" -m voxlink "\$@"
LAUNCHER
chmod +x ~/.local/bin/voxlink

echo ""
echo "=== Installation complete! ==="
echo "Run 'voxlink' or use the desktop entry."
echo "Make sure ~/.local/bin is in your PATH."
