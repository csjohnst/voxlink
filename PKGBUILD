# Maintainer: Chris Johnston
pkgname=voxlink
pkgver=0.1.0
pkgrel=1
pkgdesc="Wayland-native Mumble voice chat client"
arch=('x86_64')
url="https://github.com/csjohnst/voxlink"
license=('GPL-3.0-only')
depends=(
    'libpulse'
    'opus'
    'qt6-base'
    'qt6-wayland'
    'xdg-desktop-portal'
)
makedepends=(
    'python'
    'python-pip'
    'python-virtualenv'
    'upx'
)
optdepends=(
    'xdg-desktop-portal-hyprland: Global shortcuts on Hyprland'
    'xdg-desktop-portal-kde: Global shortcuts on KDE Plasma'
)
source=("git+https://github.com/csjohnst/voxlink.git#tag=v${pkgver}")
sha256sums=('SKIP')

build() {
    cd "$srcdir/voxlink"

    # Create isolated venv for building
    python -m venv --system-site-packages buildenv
    source buildenv/bin/activate

    # Install package and build deps
    pip install -e ".[dev,evdev]"

    # Build single binary with PyInstaller
    pyinstaller --clean --noconfirm voxlink.spec

    deactivate
}

package() {
    cd "$srcdir/voxlink"

    # Install binary
    install -Dm755 "dist/voxlink" "$pkgdir/usr/bin/voxlink"

    # Install desktop file
    install -Dm644 "resources/voxlink.desktop" \
        "$pkgdir/usr/share/applications/voxlink.desktop"

    # Install icon
    install -Dm644 "resources/icons/voxlink.svg" \
        "$pkgdir/usr/share/icons/hicolor/scalable/apps/voxlink.svg"

    # Install license
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
