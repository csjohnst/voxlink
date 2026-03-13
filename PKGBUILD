# Maintainer: Chris <chris@example.com>
pkgname=voxlink
pkgver=0.1.0
pkgrel=1
pkgdesc="Wayland-native Mumble voice chat client"
arch=('any')
url="https://github.com/csjohnst/voxlink"
license=('MIT')
depends=('python' 'python-pyside6' 'pipewire' 'pipewire-pulse' 'libopus' 'qt6-wayland'
         'xdg-desktop-portal' 'python-keyring')
makedepends=('python-build' 'python-installer' 'python-hatchling')
optdepends=('xdg-desktop-portal-hyprland: Global shortcuts on Hyprland'
            'xdg-desktop-portal-kde: Global shortcuts on KDE Plasma'
            'python-evdev: Fallback global shortcuts via evdev')
source=("$pkgname-$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
  cd "$pkgname-$pkgver"
  python -m build --wheel --no-isolation
}

package() {
  cd "$pkgname-$pkgver"
  python -m installer --destdir="$pkgdir" dist/*.whl
  install -Dm644 resources/voxlink.desktop "$pkgdir/usr/share/applications/voxlink.desktop"
  install -Dm644 resources/icons/voxlink.svg "$pkgdir/usr/share/icons/hicolor/scalable/apps/voxlink.svg"
}
