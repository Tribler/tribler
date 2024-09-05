# -*- mode: python -*-
from packaging.version import Version

block_cipher = None
import imp
import os
import re
import shutil
import sys

import aiohttp_apispec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root_dir = os.path.abspath(os.path.dirname(__name__))
src_dir = os.path.join(root_dir, "src")
sys.path.append(src_dir)

pyipv8_dir = os.path.join(root_dir, "pyipv8")
sys.path.append(pyipv8_dir)

# Import components that are not imported by the main script
import tribler.core.components as known_components

# Turn the tag into a sequence of integer values and normalize into a period-separated string.
raw_version = os.getenv("GITHUB_TAG")
version_numbers = [str(value) for value in map(int, re.findall(r"\d+", raw_version))]
version_str = str(Version(".".join(version_numbers)))

# PyInstaller can automatically generate metadata but I don't trust it (Quinten)
os.mkdir("tribler.dist-info")
with open("tribler.dist-info/METADATA", "w") as metadata_file:
    metadata_file.write(f"""Metadata-Version: 2.3
Name: Tribler
Version: {version_str}""")

# On macOS, we always show the console to prevent the double-dock bug (although the OS does not actually show the console).
# See https://github.com/Tribler/tribler/issues/3817
show_console = os.environ.get('SHOW_CONSOLE', 'false') == 'true'
if sys.platform == 'darwin':
    show_console = True

data_to_copy = [
    # UI related files
    (os.path.join(src_dir, "tribler", "ui", "dist"), 'ui/dist'),
    (os.path.join(src_dir, "tribler", "ui", "public"), 'ui/public'),

    # Tribler source files and resources
    (os.path.join(src_dir, "tribler", "core"), 'tribler_source/tribler/core'),
    (os.path.join(src_dir, "tribler", "ui"), 'tribler_source/tribler/ui'),
    (os.path.join(root_dir, "build", "win", "resources"), 'tribler_source/resources'),
    (os.path.join(root_dir, "tribler.dist-info", "METADATA"), 'tribler.dist-info'),

    (os.path.dirname(aiohttp_apispec.__file__), 'aiohttp_apispec')
]

# Importing lib2to3 as hidden import does not import all the necessary files for some reason so had to import as data.
try:
    lib2to3_dir = imp.find_module('lib2to3')[1]
    data_to_copy += [(lib2to3_dir, 'lib2to3')]
except ImportError:
    pass

if sys.platform.startswith('darwin'):
    # Create the right version info in the Info.plist file
    with open('build/mac/resources/Info.plist', 'r') as f:
        content = f.read()
        content = content.replace('__VERSION__', version_str)
    os.unlink('build/mac/resources/Info.plist')
    with open('build/mac/resources/Info.plist', 'w') as f:
        f.write(content)

# Embed the "Noto Color Emoji" font on Linux
ttf_path = os.path.join("/usr", "share", "fonts", "truetype", "noto", "NotoColorEmoji.ttf")
if sys.platform.startswith('linux') and os.path.exists(ttf_path):
    data_to_copy += [(ttf_path, 'fonts')]

excluded_libs = ['wx', 'PyQt4', 'FixTk', 'tcl', 'tk', '_tkinter', 'tkinter', 'Tkinter', 'matplotlib']

# Pony dependencies; each packages need to be added separatedly; added as hidden import
pony_deps = ['pony', 'pony.orm', 'pony.orm.dbproviders', 'pony.orm.dbproviders.sqlite']

# Hidden imports
hiddenimports = [
    'csv',
    'dataclasses',  # https://github.com/pyinstaller/pyinstaller/issues/5432
    'ecdsa',
    'ipv8',
    'PIL',
    'pkg_resources',
    # 'pkg_resources.py2_warn', # Workaround PyInstaller & SetupTools, https://github.com/pypa/setuptools/issues/1963
    'pyaes',
    'pydantic',
    'requests',
    'scrypt', '_scrypt',
    'sqlalchemy', 'sqlalchemy.ext.baked', 'sqlalchemy.ext.declarative',
    'tribler.core.logger.logger_streams',
    'typing_extensions',
]
hiddenimports += pony_deps
hiddenimports += [x for member in known_components.__dict__.values() for x in getattr(member, "hiddenimports", set())]

# Fix for issue: Could not load a pixbuf from icon theme.
# Unrecognized image file format (gdk-pixbuf-error-quark, 3).
# See: https://github.com/Tribler/tribler/issues/7457
if sys.platform.startswith('linux'):
    hiddenimports += ['gi', 'gi.repository.GdkPixbuf']

# https://github.com/pyinstaller/pyinstaller/issues/5359
hiddenimports += collect_submodules('pydantic')

sys.modules['FixTk'] = None
a = Analysis(['src/run_tribler.py'],
             pathex=[''],
             binaries=None,
             datas=data_to_copy,
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=excluded_libs,
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

# Add libsodium.dylib on OS X
if sys.platform == 'darwin':
    a.binaries = a.binaries - TOC([('/usr/local/lib/libsodium.so', None, None), ])
    a.binaries = a.binaries + TOC([('libsodium.dylib', '/usr/local/lib/libsodium.dylib', None), ])

exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='tribler',
          debug=False,
          strip=False,
          upx=True,
          console=show_console,
          icon='build/win/resources/tribler.ico')

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='tribler')

app = BUNDLE(coll,
             name='Tribler.app',
             icon='build/mac/resources/tribler.icns',
             bundle_identifier='nl.tudelft.tribler',
             info_plist={'CFBundleName': 'Tribler', 'CFBundleDisplayName': 'Tribler', 'NSHighResolutionCapable': 'True',
                         'CFBundleInfoDictionaryVersion': 1.0, 'CFBundleVersion': version_str,
                         'CFBundleShortVersionString': version_str},
             console=show_console)

# Replace the Info.plist file on MacOS
if sys.platform == 'darwin':
    shutil.copy('build/mac/resources/Info.plist', 'dist/Tribler.app/Contents/Info.plist')
