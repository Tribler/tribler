# -*- mode: python -*-

block_cipher = None

import os

widget_files = []
for file in os.listdir("TriblerGUI/widgets"):
    if file.endswith(".py"):
        widget_files.append('TriblerGUI.widgets.%s' % file[:-3])

a = Analysis(['run_gui.py'],
             pathex=['/Users/martijndevos/Documents/tribler'],
             binaries=None,
datas=[('Tribler/dispersy/libnacl/libnacl', 'libnacl'), ('TriblerGUI/qt_resources', 'qt_resources'), ('TriblerGUI/images', 'images'), ('TriblerGUI/scripts', 'scripts'), ('twisted', 'twisted'), ('Tribler', 'tribler_source/Tribler')],
             hiddenimports=['csv'] + widget_files,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
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
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='tribler')
app = BUNDLE(coll,
             name='tribler.app',
             icon=None,
             bundle_identifier=None)
