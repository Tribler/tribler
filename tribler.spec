# -*- mode: python -*-

block_cipher = None

import imp
import os
import sys
import shutil

sys.path.insert(0, os.getcwd())

from Tribler.Core.version import version_id

version_str = version_id.split('-')[0]

# On macOS, we always show the console to prevent the double-dock bug (although the OS does not actually show the console).
# See https://github.com/Tribler/tribler/issues/3817
show_console = False
if sys.platform == 'darwin':
    show_console = True

widget_files = []
for file in os.listdir("TriblerGUI/widgets"):
    if file.endswith(".py"):
        widget_files.append('TriblerGUI.widgets.%s' % file[:-3])

data_to_copy = [('TriblerGUI/qt_resources', 'qt_resources'), ('TriblerGUI/images', 'images'), ('twisted', 'twisted'), ('Tribler', 'tribler_source/Tribler'), ('logger.conf', '.')]

# For bitcoinlib, we have to copy the data directory to the root directory of the installation dir, otherwise
# the library is unable to find the data files.
try:
    bitcoinlib_dir = imp.find_module('bitcoinlib')[1]
    data_to_copy += [(bitcoinlib_dir, 'bitcoinlib')]
except ImportError:
    pass

# Importing lib2to3 as hidden import does not import all the necessary files for some reason so had to import as data.
try:
    lib2to3_dir = imp.find_module('lib2to3')[1]
    data_to_copy += [(lib2to3_dir, 'lib2to3')]
except ImportError:
    pass

if sys.platform.startswith('darwin'):
    data_to_copy += [('/Applications/VLC.app/Contents/MacOS/lib', 'vlc/lib'), ('/Applications/VLC.app/Contents/MacOS/plugins', 'vlc/plugins')]

    # Create the right version info in the Info.plist file
    with open('Tribler/Main/Build/Mac/Info.plist', 'r') as f:
        content = f.read()
        content = content.replace('__VERSION__', version_str)

    os.unlink('Tribler/Main/Build/Mac/Info.plist')
    with open('Tribler/Main/Build/Mac/Info.plist', 'w') as f:
        f.write(content)

excluded_libs = ['wx', 'bitcoinlib', 'PyQt4', 'FixTk', 'tcl', 'tk', '_tkinter', 'tkinter', 'Tkinter']

# Pony dependencies; each packages need to be added separatedly; added as hidden import
pony_deps = ['pony', 'pony.orm', 'pony.orm.dbproviders', 'pony.orm.dbproviders.sqlite']

sys.modules['FixTk'] = None

a = Analysis(['run_tribler.py'],
             pathex=['/Users/martijndevos/Documents/tribler'],
             binaries=None,
             datas=data_to_copy,
             hiddenimports=['csv', 'ecdsa', 'pyaes', 'scrypt', '_scrypt', 'sqlalchemy', 'sqlalchemy.ext.baked', 'sqlalchemy.ext.declarative', 'requests', 'PyQt5.QtTest', 'pyqtgraph'] + widget_files + pony_deps,
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
          icon='Tribler/Main/Build/Win/tribler.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='tribler')
app = BUNDLE(coll,
             name='tribler.app',
             icon='Tribler/Main/Build/Mac/tribler.icns',
             bundle_identifier='nl.tudelft.tribler',
             info_plist={'NSHighResolutionCapable': 'True', 'CFBundleInfoDictionaryVersion': 1.0, 'CFBundleVersion': version_str, 'CFBundleShortVersionString': version_str},
             console=show_console)

# Remove the test directories in the Tribler source code
shutil.rmtree(os.path.join(DISTPATH, 'tribler', 'tribler_source', 'Tribler', 'Test'))

# Remove the second IPv8 submodule
anydex_ipv8_dir = os.path.join(DISTPATH, 'tribler', 'tribler_source', 'Tribler', 'anydex', 'pyipv8')
if os.path.exists(anydex_ipv8_dir):
    shutil.rmtree(anydex_ipv8_dir)

# Replace the Info.plist file on MacOS
if sys.platform == 'darwin':
    shutil.copy('Tribler/Main/Build/Mac/Info.plist', 'dist/Tribler.app/Contents/Info.plist')

# On Windows 10, we have to make sure that qwindows.dll is in the right path
if sys.platform == 'win32':
    shutil.copytree(os.path.join('dist', 'tribler', 'PyQt5', 'Qt', 'plugins', 'platforms'), os.path.join('dist', 'tribler', 'platforms'))
