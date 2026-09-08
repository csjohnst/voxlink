#!/bin/bash
# Verify that versions in pyproject.toml, PKGBUILD and src/voxlink/__init__.py are in sync.
# Used as a pre-commit hook to prevent version drift.

set -e

PYPROJECT_VER=$(grep -Po '(?<=^version = ")[^"]+' pyproject.toml)
PKGBUILD_VER=$(grep -Po '(?<=^pkgver=).+' PKGBUILD)
INIT_VER=$(grep -Po '(?<=^__version__ = ")[^"]+' src/voxlink/__init__.py)

if [ -z "$PYPROJECT_VER" ]; then
    echo "ERROR: Could not read version from pyproject.toml"
    exit 1
fi

if [ -z "$PKGBUILD_VER" ]; then
    echo "ERROR: Could not read pkgver from PKGBUILD"
    exit 1
fi

if [ -z "$INIT_VER" ]; then
    echo "ERROR: Could not read __version__ from src/voxlink/__init__.py"
    exit 1
fi

if [ "$PYPROJECT_VER" != "$PKGBUILD_VER" ] || [ "$PYPROJECT_VER" != "$INIT_VER" ]; then
    echo "ERROR: Version mismatch!"
    echo "  pyproject.toml:           $PYPROJECT_VER"
    echo "  PKGBUILD:                 $PKGBUILD_VER"
    echo "  src/voxlink/__init__.py:  $INIT_VER"
    echo ""
    echo "Update all three files to the same version before committing."
    exit 1
fi

echo "Version sync OK: $PYPROJECT_VER"
