# -*- mode: python -*-
block_cipher = None
import imp
import os
import sys
import shutil

import aiohttp_apispec


root_dir = os.path.abspath(os.path.dirname(__name__))
src_dir = os.path.join(root_dir, "src")

tribler_components = [
    os.path.join(src_dir, "pyipv8"),
    os.path.join(src_dir, "anydex"),
    os.path.join(src_dir, "tribler-common"),
    os.path.join(src_dir, "tribler-core"),
]

for component in tribler_components:
    sys.path.append(str(component))

from tribler_core.version import version_id
version_str = version_id.split('-')[0]

data_to_copy = [
    (os.path.join(src_dir, "tribler-core", "tribler_core"), 'tribler_source/tribler_core'),
    (os.path.join(root_dir, "build", "win", "resources"), 'tribler_source/resources'),
    (os.path.dirname(aiohttp_apispec.__file__), 'aiohttp_apispec')
]

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
    # Create the right version info in the Info.plist file
    with open('build/mac/resources/Info.plist', 'r') as f:
        content = f.read()
        content = content.replace('__VERSION__', version_str)
    os.unlink('build/mac/resources/Info.plist')
    with open('build/mac/resources/Info.plist', 'w') as f:
        f.write(content)

excluded_libs = ['wx', 'bitcoinlib', 'PyQt4', 'FixTk', 'tcl', 'tk', '_tkinter', 'tkinter', 'Tkinter', 'matplotlib']

# Pony dependencies; each packages need to be added separatedly; added as hidden import
pony_deps = ['pony', 'pony.orm', 'pony.orm.dbproviders', 'pony.orm.dbproviders.sqlite', 'pkg_resources.py2_warn']
# Hidden imports
hiddenimports = [
    'csv',
    'ecdsa',
    'pyaes',
    'scrypt', '_scrypt',
    'sqlalchemy', 'sqlalchemy.ext.baked', 'sqlalchemy.ext.declarative',
    'requests',
    ] + pony_deps,


a = Analysis(['src/tribler-core/run_tribler_headless.py'],
             pathex=[''],
             binaries=None,
             datas=data_to_copy,
             hiddenimports=['csv', 'ecdsa', 'pyaes', 'scrypt', '_scrypt', 'sqlalchemy', 'sqlalchemy.ext.baked', 'sqlalchemy.ext.declarative', 'requests'] + pony_deps,
             hookspath=[],
             runtime_hooks=[],
             excludes=excluded_libs,
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

if sys.platform == 'darwin':
    exe = EXE(pyz,
              a.scripts,
              exclude_binaries=True,
              name='triblerd',
              debug=False,
              strip=False,
              upx=True,
              console=show_console,
              icon='build/win/resources/tribler.ico')

    # Add libsodium.dylib on OS X
    a.binaries = a.binaries - TOC([('/usr/local/lib/libsodium.so', None, None),])
    a.binaries = a.binaries + TOC([('libsodium.dylib', '/usr/local/lib/libsodium.dylib', None),])
    coll = COLLECT(exe,
                   a.binaries,
                   a.zipfiles,
                   a.datas,
                   strip=True,
                   upx=True,
                   name='triblerd')
    
    app = BUNDLE(coll,
                 name='triblerd.app',
                 icon='build/mac/resources/tribler.icns',
                 bundle_identifier='nl.tudelft.tribler',
                 info_plist={'NSHighResolutionCapable': 'True', 'CFBundleInfoDictionaryVersion': 1.0, 'CFBundleVersion': version_str, 'CFBundleShortVersionString': version_str},
                 console=True)
    
    # Replace the Info.plist file on MacOS
    if sys.platform == 'darwin':
        shutil.copy('build/mac/resources/Info.plist', 'dist/Tribler.app/Contents/Info.plist')

else:
    exe = EXE(pyz,
              a.scripts,
              a.binaries,
              a.zipfiles,
              a.datas,
              bootloader_ignore_signals=False,
              name='triblerd',
              debug=False,
              strip=True,
              upx=True,
              console=True,
              icon='build/win/resources/tribler.ico')