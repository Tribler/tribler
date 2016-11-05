# -*- mode: python -*-

block_cipher = None

import os
import sys

sys.path.insert(0, os.getcwdu())

from Tribler.Core.version import version_id

version_str = version_id.split('-')[0]

widget_files = []
for file in os.listdir("TriblerGUI/widgets"):
    if file.endswith(".py"):
        widget_files.append('TriblerGUI.widgets.%s' % file[:-3])

data_to_copy = [('Tribler/dispersy/libnacl/libnacl', 'libnacl'), ('TriblerGUI/qt_resources', 'qt_resources'), ('TriblerGUI/images', 'images'), ('TriblerGUI/scripts', 'scripts'), ('twisted', 'twisted'), ('Tribler', 'tribler_source/Tribler')]
if sys.platform.startswith('darwin'):
    data_to_copy += [('/Applications/VLC.app/Contents/MacOS/lib', 'vlc/lib'), ('/Applications/VLC.app/Contents/MacOS/plugins', 'vlc/plugins')]

a = Analysis(['run_tribler.py'],
             pathex=['/Users/martijndevos/Documents/tribler'],
             binaries=None,
             datas=data_to_copy,
             hiddenimports=['csv'] + widget_files,
             hookspath=[],
             runtime_hooks=[],
             excludes=['wx'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='tribler',
          debug=False,
          strip=False,
          upx=True,
          console=True,
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
             console=True)

# Remove libvlc - conflicts on Windows
if sys.platform == 'win32':
    os.remove(os.path.join(DISTPATH, 'tribler', 'libvlc.dll'))
    os.remove(os.path.join(DISTPATH, 'tribler', 'libvlccore.dll'))
