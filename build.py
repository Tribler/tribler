"""
This file includes the build configuration for the Tribler.
The exports of this file are used in setup.py to build the executable or wheel package.

Building executable depends on cx_Freeze.

1) If cx_Freeze is not installed,
setuptools is used to build the wheel package.

To create a wheel package:
python setup.py bdist_wheel

2) If cx_Freeze is installed,

To create a build:
python setup.py build

To create a distributable package:
python setup.py bdist

To create a distributable package for a specific platform:
python setup.py bdist_mac
python setup.py bdist_win
"""
import os
import re
import shutil
import sys
from pathlib import Path

from setuptools import find_packages

try:
    import cx_Freeze
except ImportError:
    cx_Freeze = None

if cx_Freeze is None:
    # If cx_Freeze is not installed, use setuptools to build the wheel package
    from setuptools import setup
    app_executable = None
    build_exe_options = {}

else:
    from cx_Freeze import setup, Executable

    app_name = "Tribler" if sys.platform != "linux" else "tribler"
    app_script = "src/tribler/run.py"
    app_icon_path = "build/win/resources/tribler.ico" if sys.platform == "win32" else "build/mac/resources/tribler.icns"
    app_executable = Executable(
        target_name=app_name,
        script=app_script,
        base="Win32GUI" if sys.platform == "win32" else None,
        icon=app_icon_path,
    )

    # These packages will be included in the build
    sys.path.insert(0, 'src')
    included_packages = [
        "aiohttp_apispec",
        "sentry_sdk",
        "ipv8",
        "PIL",
        "pkg_resources",
        "pydantic",
        "pyqtgraph",
        "PyQt5.QtTest",
        "requests",
        "tribler.core",
        "tribler.gui",
        "faker",
        "libtorrent",
        "ssl",
    ]

    # These files will be included in the build
    included_files = [
        ("src/tribler/gui/qt_resources", "qt_resources"),
        ("src/tribler/gui/images", "images"),
        ("src/tribler/gui/i18n", "i18n"),
        ("src/tribler/core", "tribler_source/tribler/core"),
        ("src/tribler/gui", "tribler_source/tribler/gui"),
        ("build/win/resources", "tribler_source/resources"),
    ]

    # These packages will be excluded from the build
    excluded_packages = [
        'wx',
        'PyQt4',
        'FixTk',
        'tcl',
        'tk',
        '_tkinter',
        'tkinter',
        'Tkinter',
        'matplotlib'
    ]

    build_exe_options = {
        "packages": included_packages,
        "excludes": excluded_packages,
        "include_files": included_files,
        "include_msvcr": True,
        'build_exe': 'dist/tribler'
    }

__all__ = ["setup", "app_executable", "build_exe_options"]
