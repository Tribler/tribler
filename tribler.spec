# -*- mode: python -*-
block_cipher = None
import imp
import os
import pkgutil
import sys
import shutil

import aiohttp_apispec
import sentry_sdk

root_dir = os.path.abspath(os.path.dirname(__name__))
src_dir = os.path.join(root_dir, "src")

tribler_components = [
    os.path.join(src_dir, "pyipv8"),
    os.path.join(src_dir, "tribler-common"),
    os.path.join(src_dir, "tribler-core"),
    os.path.join(src_dir, "tribler-gui"),
]

for component in tribler_components:
    sys.path.append(str(component))

from tribler_core.version import version_id
version_str = version_id.split('-')[0]

# On macOS, we always show the console to prevent the double-dock bug (although the OS does not actually show the console).
# See https://github.com/Tribler/tribler/issues/3817
show_console = os.environ.get('SHOW_CONSOLE', 'false') == 'true'
if sys.platform == 'darwin':
    show_console = True

widget_files = []
for file in os.listdir(os.path.join(src_dir, "tribler-gui", "tribler_gui", "widgets")):
    if file.endswith(".py"):
        widget_files.append('tribler_gui.widgets.%s' % file[:-3])

data_to_copy = [
    (os.path.join(src_dir, "tribler-gui", "tribler_gui", "qt_resources"), 'qt_resources'),
    (os.path.join(src_dir, "tribler-gui", "tribler_gui", "images"), 'images'),
    (os.path.join(src_dir, "tribler-gui", "tribler_gui", "i18n"), 'i18n'),
    (os.path.join(src_dir, "tribler-core", "tribler_core"), 'tribler_source/tribler_core'),
    (os.path.join(src_dir, "tribler-gui", "tribler_gui"), 'tribler_source/tribler_gui'),
    (os.path.join(root_dir, "build", "win", "resources"), 'tribler_source/resources'),
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

# Sentry hidden imports
def get_sentry_hooks():
    package = sentry_sdk.integrations
    sentry_hooks = ['sentry_sdk', 'sentry_sdk.integrations']
    for _, modname, _ in pkgutil.walk_packages(path=package.__path__,
                                               prefix=package.__name__ + '.',
                                               onerror=lambda x: None):
        sentry_hooks.append(modname)
    return sentry_hooks

# Hidden imports
hiddenimports = [
    'csv',
    'ecdsa',
    'pyaes',
    'PIL',
    'scrypt', '_scrypt',
    'sqlalchemy', 'sqlalchemy.ext.baked', 'sqlalchemy.ext.declarative',
    'pkg_resources', 'pkg_resources.py2_warn', # Workaround PyInstaller & SetupTools, https://github.com/pypa/setuptools/issues/1963
    'requests',
    'PyQt5.QtTest',
    'pyqtgraph'] + widget_files + pony_deps + get_sentry_hooks()


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
    a.binaries = a.binaries - TOC([('/usr/local/lib/libsodium.so', None, None),])
    a.binaries = a.binaries + TOC([('libsodium.dylib', '/usr/local/lib/libsodium.dylib', None),])

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
             info_plist={'CFBundleName': 'Tribler', 'CFBundleDisplayName': 'Tribler', 'NSHighResolutionCapable': 'True', 'CFBundleInfoDictionaryVersion': 1.0, 'CFBundleVersion': version_str, 'CFBundleShortVersionString': version_str},
             console=show_console)

# Replace the Info.plist file on MacOS
if sys.platform == 'darwin':
    shutil.copy('build/mac/resources/Info.plist', 'dist/Tribler.app/Contents/Info.plist')

# On Windows 10, we have to make sure that qwindows.dll is in the right path
if sys.platform == 'win32':
    shutil.copytree(os.path.join('dist', 'tribler', 'PyQt5', 'Qt', 'plugins', 'platforms'), os.path.join('dist', 'tribler', 'platforms'))
