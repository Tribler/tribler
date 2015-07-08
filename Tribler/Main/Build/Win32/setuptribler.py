# Written by ABC authors and Arno Bakker
# see LICENSE.txt for license information
import sys
import os

try:
    import py2exe.mf as modulefinder
    import win32com
    for p in win32com.__path__[1:]:
        modulefinder.AddPackagePath("win32com", p)
    for extra in ["win32com.shell"]:
        __import__(extra)
        m = sys.modules[extra]
        for p in m.__path__[1:]:
            modulefinder.AddPackagePath(extra, p)
except ImportError:
    pass


from distutils.core import setup
import py2exe

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../dispersy/libnacl'))

#
#
# Setup script used for py2exe
#
# *** Important note: ***
# Setting Python's optimize flag when building disables
# "assert" statements, which are used throughout the
# BitTornado core for error-handling.
#
#

mainfile = os.path.join('Tribler', 'Main', 'tribler.py')
progicofile = os.path.join('Tribler', 'Main', 'vwxGUI', 'images', 'tribler.ico')

target = {
    "script": mainfile,
    "icon_resources": [(1, progicofile)],
}

# gui panels to include (=those not found by py2exe from imports)
includePanels = [
    "TopSearchPanel", "home", "list", "settingsDialog"
]

# packages = ["Tribler.Core","encodings"] + ["Tribler.Main.vwxGUI.%s" % x for x in includePanels]
packages = ["encodings"] + ["Tribler.Main.vwxGUI.%s" % x for x in includePanels] +\
    ["Tribler.Core.DecentralizedTracking.pymdht.core",
     "Tribler.Main.tribler_main",
     "netifaces", "csv", "cherrypy", "feedparser",
     "twisted", "apsw", "libtorrent", "M2Crypto", "cryptography", "libnacl", "six", "cffi", "pycparser",
     "zope.interface", "pyasn1", "gmpy", "Image", "requests", "leveldb", "decorator"]

setup(
    # (Disabling bundle_files for now -- apparently causes some issues with Win98)
    # options = {"py2exe": {"bundle_files": 1}},
    # zipfile = None,
    options={"py2exe": {"packages": packages,
                        "optimize": 2,
                        "skip_archive": True,
                        "dist_dir": os.path.join("dist", "installdir"),
                        "dll_excludes": ["mswsock.dll"]}},
    data_files=[(".", [r"C:\build\libsodium.dll"])],
    windows=[target],
)
