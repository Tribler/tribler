# ---------------
# This script builds build/Tribler.app
#
# Meant to be called from mac/Makefile
# ---------------

import sys
import os
import logging
from setuptools import setup
from Tribler import LIBRARYNAME

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../dispersy/libnacl'))

logger = logging.getLogger(__name__)

# modules to include into bundle
includeModules = ["encodings.hex_codec", "encodings.utf_8", "encodings.latin_1", "xml.sax", "email.iterators",
                  "netifaces", "apsw", "libtorrent", "twisted", "M2Crypto", "pycrypto", "pyasn1", "Image", "feedparser",
                  "urllib3", "requests", "leveldb", "cryptography", "libnacl", "pycparser", "six", "hashlib",
                  "csv", "cherrypy",
                  "cryptography.hazmat.backends.commoncrypto",
                  "cryptography.hazmat.backends.openssl",
                  "cryptography.hazmat.bindings.commoncrypto",
                  "cryptography.hazmat.bindings.openssl"]

# gui panels to include
includePanels = [
    "list", "list_header", "list_body", "list_footer", "list_details",
    "home", "settingsDialog", "TopSearchPanel", "SearchGridManager", "SRstatusbar"]
    # ,"btn_DetailsHeader","tribler_List","TopSearchPanel","settingsOverviewPanel"] # TextButton


includeModules += ["Tribler.Main.vwxGUI.%s" % x for x in includePanels]

# ----- some basic checks

if __debug__:
    logger.warn(
        "WARNING: Non optimised python bytecode (.pyc) will be produced. Run with -OO instead to produce and bundle .pyo files.")

if sys.platform != "darwin":
    logger.warn("WARNING: You do not seem to be running Mac OS/X.")

# ----- import and verify wxPython

"""
import wxversion

wxversion.select('2.8-unicode')
"""
import wx

v = wx.__version__

if v < "2.6":
    logger.warn("WARNING: You need wxPython 2.6 or higher but are using %s.", v)

if v < "2.8.4.2":
    logger.warn("WARNING: wxPython before 2.8.4.2 could crash when loading non-present fonts. You are using %s.", v)

# ----- import and verify M2Crypto

import M2Crypto
import M2Crypto.m2
if "ec_init" not in M2Crypto.m2.__dict__:
    logger.warn("WARNING: Could not import specialistic M2Crypto (imported %s)", M2Crypto.__file__)

# ----- import Growl
try:
    import Growl

    includeModules += ["Growl"]
except:
    logger.warn("WARNING: Not including Growl support.")


# =================
# build Tribler.app
# =================

from plistlib import Plist


def includedir(srcpath, dstpath=None):
    """ Recursive directory listing, filtering out svn files. """

    total = []

    cwd = os.getcwd()
    os.chdir(srcpath)

    if dstpath is None:
        dstpath = srcpath

    for root, dirs, files in os.walk("."):
        if '.svn' in dirs:
            dirs.remove('.svn')

        for f in files:
            total.append((root, f))

    os.chdir(cwd)

    # format: (targetdir,[file])
    # so for us, (dstpath/filedir,[srcpath/filedir/filename])
    return [("%s/%s" % (dstpath, root), ["%s/%s/%s" % (srcpath, root, f)]) for root, f in total]


def filterincludes(l, f):
    """ Return includes which pass filter f. """

    return [(x, y) for (x, y) in l if f(y[0])]

PYTHON_CRYPTOGRAPHY_PATH = "/Users/tribler/Workspace/install/python-libs/lib/python2.7/site-packages/cryptography-0.7.2-py2.7-macosx-10.6-intel.egg"

# ----- build the app bundle
mainfile = os.path.join(LIBRARYNAME, 'Main', 'tribler.py')
setup(
    setup_requires=['py2app'],
    name='Tribler',
    app=[mainfile],
    options={'py2app': {
        'argv_emulation': True,
        'includes': includeModules,
        'excludes': ["Tkinter", "Tkconstants", "tcl"],
        'iconfile': LIBRARYNAME + '/Main/Build/Mac/tribler.icns',
        'plist': Plist.fromFile(LIBRARYNAME + '/Main/Build/Mac/Info.plist'),
        'optimize': 0 if __debug__ else 2,
        'resources':
            [(LIBRARYNAME + "/Category", [LIBRARYNAME + "/Category/category.conf"]),
             (LIBRARYNAME + "/Core/DecentralizedTracking/pymdht/core",
              [LIBRARYNAME + "/Core/DecentralizedTracking/pymdht/core/bootstrap_stable"]),
             (LIBRARYNAME + "/Core/DecentralizedTracking/pymdht/core",
              [LIBRARYNAME + "/Core/DecentralizedTracking/pymdht/core/bootstrap_unstable"]),
             LIBRARYNAME + "/readme.txt",
             LIBRARYNAME + "/Main/Build/Mac/TriblerDoc.icns",
             ]
            + ["/Users/tribler/Workspace/install/python-libs/lib/libsodium.dylib",
               "/Users/tribler/Workspace/install/python-libs/lib/libsodium.13.dylib"]

            # add images
            + includedir(LIBRARYNAME + "/Main/vwxGUI/images")
            + includedir(LIBRARYNAME + "/Main/webUI/static")

            # add GUI elements
            + filterincludes(includedir(LIBRARYNAME + "/Main/vwxGUI"), lambda x: x.endswith(".xrc"))

            # add crawler info and SQL statements
            + filterincludes(includedir(LIBRARYNAME + "/"), lambda x: x.endswith(".sql"))

            # add VLC plugins
            + includedir("vlc")

            # add ffmpeg binary
            + [("vlc", ["vlc/ffmpeg"])],
    }}
)
