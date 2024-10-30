"""
This file includes the build configuration for the Tribler.
The exports of this file are used in setup.py to build the executable or wheel package.

There are two build options:
1) setuptools is used to build the wheel package.

To create a wheel package:
python setup.py bdist_wheel

2) Building executable is done using cx_Freeze.

To build an executable:
python setup.py build

To create a distributable package:
python setup.py bdist

To create a distributable package for a specific platform:
python setup.py bdist_mac
python setup.py bdist_win

Building wheel and building executable had to be separated because cx_Freeze does not
support building wheels. Therefore, the build options are separated into two functions
and the appropriate function is called based on the command line arguments.
"""
import sys
import platform


def get_wheel_build_options():
    from setuptools import setup as _setup
    _setup_options = {"build_exe": {}}
    _setup_executables = None
    return _setup, _setup_options, _setup_executables


def get_freeze_build_options():
    from cx_Freeze import setup as _setup, Executable

    # These packages will be included in the build
    sys.path.insert(0, 'src')
    sys.path.insert(0, 'pyipv8')
    included_packages = [
        "aiohttp_apispec",
        "pkg_resources",
        "requests",
        "tribler.core",
        "libtorrent",
        "ssl",
    ]

    if platform.system() != 'Windows':
        included_packages.append("gi")

    # These files will be included in the build
    included_files = [
        ("src/tribler/ui/public", "lib/tribler/ui/public"),
        ("src/tribler/ui/dist", "lib/tribler/ui/dist"),
        ("src/tribler/core", "tribler_source/tribler/core"),
        ("src/tribler/ui/public", "tribler_source/tribler/ui/public"),
        ("src/tribler/ui/dist", "tribler_source/tribler/ui/dist"),
        ("build/win/resources", "tribler_source/resources"),
        ("tribler.dist-info/METADATA", "lib/tribler.dist-info/METADATA"),
    ]

    if platform.system() == "Linux" and platform.machine() == "aarch64":
        included_files.append(("libcrypt-06cd74a6.so.2", "lib/libcrypt-06cd74a6.so.2"))

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
        'matplotlib',
        'numpy',
        'tribler.ui'
    ]

    _setup_options = {
        "build_exe": {
            "packages": included_packages,
            "excludes": excluded_packages,
            "include_files": included_files,
            "include_msvcr": True,
            'build_exe': 'dist/tribler'
        }
    }
    if platform.system() == 'Linux':
        _setup_options["build_exe"]["bin_includes"] = "libffi.so"

    app_name = "Tribler" if sys.platform != "linux" else "tribler"
    app_script = "src/tribler/run.py"
    app_icon_path = "build/win/resources/tribler.ico" if sys.platform == "win32" else "build/mac/resources/tribler.icns"
    _setup_executables = [
        Executable(
            target_name=app_name,
            script=app_script,
            base="Win32GUI" if sys.platform == "win32" else None,
            icon=app_icon_path,
        )
    ]
    return _setup, _setup_options, _setup_executables


# Based on the command line arguments, get the build options.
# If the command line arguments include 'setup.py' and 'bdist_wheel',
# then the options are for building a wheel package.
# Otherwise, the options are for building an executable (any other).
if {'setup.py', 'bdist_wheel'}.issubset(sys.argv):
    setup, setup_options, setup_executables = get_wheel_build_options()
else:
    setup, setup_options, setup_executables = get_freeze_build_options()
