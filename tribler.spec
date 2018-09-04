# -*- mode: python -*-

block_cipher = None

import os
import sys
import shutil

sys.path.insert(0, os.getcwdu())

from Tribler.Core.version import version_id

version_str = version_id.split('-')[0]

widget_files = []
for file in os.listdir("TriblerGUI/widgets"):
    if file.endswith(".py"):
        widget_files.append('TriblerGUI.widgets.%s' % file[:-3])

data_to_copy = [('TriblerGUI/qt_resources', 'qt_resources'), ('TriblerGUI/images', 'images'), ('twisted', 'twisted'), ('Tribler', 'tribler_source/Tribler'), ('logger.conf', '.')]

# For bitcoinlib, we have to copy the data directory to the root directory of the installation dir, otherwise
# the library is unable to find the data files.
import bitcoinlib
bitcoinlib_dir = os.path.dirname(bitcoinlib.__file__)
data_to_copy += [(bitcoinlib_dir, 'bitcoinlib')]

if sys.platform.startswith('darwin'):
    data_to_copy += [('/Applications/VLC.app/Contents/MacOS/lib', 'vlc/lib'), ('/Applications/VLC.app/Contents/MacOS/plugins', 'vlc/plugins')]

    # Create the right version info in the Info.plist file
    with open('Tribler/Main/Build/Mac/Info.plist', 'r') as f:
        content = f.read()
        content = content.replace('__VERSION__', version_str)

    os.unlink('Tribler/Main/Build/Mac/Info.plist')
    with open('Tribler/Main/Build/Mac/Info.plist', 'w') as f:
        f.write(content)

# We use plyvel on Windows since leveldb is unable to deal with unicode paths
excluded_libs = ['wx', 'leveldb', 'bitcoinlib'] if sys.platform == 'win32' else ['wx', 'bitcoinlib', ]

a = Analysis(['run_tribler.py'],
             pathex=['/Users/martijndevos/Documents/tribler'],
             binaries=None,
             datas=data_to_copy,
             hiddenimports=['csv', 'ecdsa', 'pyaes', 'scrypt', '_scrypt', 'sqlalchemy', 'sqlalchemy.ext.baked', 'sqlalchemy.ext.declarative', 'requests'] + widget_files,
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
          console=False,
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
             console=False)

# Remove libvlc - conflicts on Windows
if sys.platform == 'win32':
    os.remove(os.path.join(DISTPATH, 'tribler', 'libvlc.dll'))
    os.remove(os.path.join(DISTPATH, 'tribler', 'libvlccore.dll'))

# Replace the Info.plist file on MacOS
if sys.platform == 'darwin':
    shutil.copy('Tribler/Main/Build/Mac/Info.plist', 'dist/Tribler.app/Contents/Info.plist')
