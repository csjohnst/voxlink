#!/bin/bash
# Verify that versions in pyproject.toml and PKGBUILD are in sync.
# Used as a pre-commit hook to prevent version drift.

set -e

PYPROJECT_VER=$(grep -Po '(?<=^version = ")[^"]+' pyproject.toml)
PKGBUILD_VER=$(grep -Po '(?<=^pkgver=).+' PKGBUILD)

if [ -z "$PYPROJECT_VER" ]; then
    echo "ERROR: Could not read version from pyproject.toml"
    exit 1
fi

if [ -z "$PKGBUILD_VER" ]; then
    echo "ERROR: Could not read pkgver from PKGBUILD"
    exit 1
fi

if [ "$PYPROJECT_VER" != "$PKGBUILD_VER" ]; then
    echo "ERROR: Version mismatch!"
    echo "  pyproject.toml: $PYPROJECT_VER"
    echo "  PKGBUILD:       $PKGBUILD_VER"
    echo ""
    echo "Update both files to the same version before committing."
    exit 1
fi

echo "Version sync OK: $PYPROJECT_VER"
