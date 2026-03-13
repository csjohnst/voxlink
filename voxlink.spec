# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for VoxLink single-binary build."""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all submodules that use lazy imports
hiddenimports = [
    *collect_submodules("voxlink"),
    *collect_submodules("mumble"),
    *collect_submodules("qfluentwidgets"),
    "pasimple",
    "pulsectl",
    "dbus_next",
    "evdev",
    "opuslib",
    "tomli",
    "tomli_w",
    "keyring",
    "google.protobuf",
]

# Collect data files needed at runtime
datas = [
    ("resources/icons/voxlink.svg", "resources/icons"),
    *collect_data_files("qfluentwidgets"),
    *collect_data_files("mumble"),
]

a = Analysis(
    ["src/voxlink/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="voxlink",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
