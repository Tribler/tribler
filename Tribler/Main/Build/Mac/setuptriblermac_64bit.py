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
includeModules = ["xml.sax", "email.iterators",
                  "netifaces", "apsw", "libtorrent", "twisted", "M2Crypto", "pyasn1", "PIL", "feedparser",
                  "urllib3", "requests", "leveldb", "cryptography", "libnacl", "pycparser", "six", "hashlib",
                  "csv", "cherrypy", "decorator",

                  "cryptography",
                  "cryptography._Cryptography_cffi_2a871178xb3816a41",
                  "cryptography._Cryptography_cffi_684bb40axf342507b",
                  "cryptography._Cryptography_cffi_8f86901cxc1767c5a",
                  "cryptography._Cryptography_cffi_f3e4673fx399b1113",
                  "cryptography.__about__",
                  "cryptography.exceptions",
                  "cryptography.fernet",
                  "cryptography.utils",
                  "cryptography.x509",

                  "cryptography.hazmat",

                  "cryptography.hazmat.primitives",
                  "cryptography.hazmat.primitives.cmac",
                  "cryptography.hazmat.primitives.constant_time",
                  "cryptography.hazmat.primitives.hashes",
                  "cryptography.hazmat.primitives.hmac",
                  "cryptography.hazmat.primitives.padding",
                  "cryptography.hazmat.primitives.serialization",

                  "cryptography.hazmat.primitives.asymmetric",
                  "cryptography.hazmat.primitives.asymmetric.dh",
                  "cryptography.hazmat.primitives.asymmetric.dsa",
                  "cryptography.hazmat.primitives.asymmetric.ec",
                  "cryptography.hazmat.primitives.asymmetric.padding",
                  "cryptography.hazmat.primitives.asymmetric.rsa",
                  "cryptography.hazmat.primitives.asymmetric.utils",

                  "cryptography.hazmat.primitives.ciphers",
                  "cryptography.hazmat.primitives.ciphers.algorithms",
                  "cryptography.hazmat.primitives.ciphers.base",
                  "cryptography.hazmat.primitives.ciphers.modes",

                  "cryptography.hazmat.primitives.interfaces",

                  "cryptography.hazmat.primitives.kdf",
                  "cryptography.hazmat.primitives.kdf.hkdf",
                  "cryptography.hazmat.primitives.kdf.pbkdf2",

                  "cryptography.hazmat.primitives.twofactor.hotp",
                  "cryptography.hazmat.primitives.twofactor.totp",

                  "cryptography.hazmat.backends.commoncrypto",
                
                  "cryptography.hazmat.backends.openssl",
                  "cryptography.hazmat.backends.openssl.backend",
                  "cryptography.hazmat.backends.openssl.ciphers",
                  "cryptography.hazmat.backends.openssl.cmac",
                  "cryptography.hazmat.backends.openssl.dsa",
                  "cryptography.hazmat.backends.openssl.ec",
                  "cryptography.hazmat.backends.openssl.hashes",
                  "cryptography.hazmat.backends.openssl.hmac",
                  "cryptography.hazmat.backends.openssl.rsa",
                  "cryptography.hazmat.backends.openssl.utils",
                  "cryptography.hazmat.backends.openssl.x509",
                  
                  "cryptography.hazmat.bindings.commoncrypto",
                  "cryptography.hazmat.bindings.commoncrypto.binding",
                  "cryptography.hazmat.bindings.commoncrypto.cf",
                  "cryptography.hazmat.bindings.commoncrypto.common_cryptor",
                  "cryptography.hazmat.bindings.commoncrypto.common_digest",
                  "cryptography.hazmat.bindings.commoncrypto.common_hmac",
                  "cryptography.hazmat.bindings.commoncrypto.common_key_derivation",
                  "cryptography.hazmat.bindings.commoncrypto.secimport",
                  "cryptography.hazmat.bindings.commoncrypto.secitem",
                  "cryptography.hazmat.bindings.commoncrypto.seckeychain",
                  "cryptography.hazmat.bindings.commoncrypto.seckey",
                  "cryptography.hazmat.bindings.commoncrypto.sectransform",
                  "cryptography.hazmat.bindings.openssl",
                  "cryptography.hazmat.bindings.openssl.binding",
                  "cryptography.hazmat.bindings.openssl._conditional",

                  "pycparser",
                  "pycparser._ast_gen",
                  "pycparser._build_tables",
                  "pycparser.ast_transforms",
                  "pycparser.c_ast",
                  "pycparser.c_generator",
                  "pycparser.c_lexer",
                  "pycparser.c_parser",
                  "pycparser.lextab",
                  "pycparser.plyparser",
                  "pycparser.yacctab",

                  "pycparser.ply",
                  "pycparser.ply.cpp",
                  "pycparser.ply.ctokens",
                  "pycparser.ply.lex",
                  "pycparser.ply.yacc",

                  "cffi",
                  "cffi.api",
                  "cffi.backend_ctypes",
                  "cffi.commontypes",
                  "cffi.cparser",
                  "cffi.ffiplatform",
                  "cffi.gc_weakref",
                  "cffi.lock",
                  "cffi.model",
                  "cffi.vengine_cpy",
                  "cffi.vengine_gen",
                  "cffi.verifier",

                  "Tribler.Core.DecentralizedTracking.pymdht.core.routing_table",
                  ]

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

wxversion.select('3.0-unicode')
"""
import wx

v = wx.__version__

if v < "2.8":
    logger.warn("WARNING: You need wxPython 2.8 or higher but are using %s.", v)

if v < "3.0":
    logger.warn("WARNING: wxPython before 3.0 is not supported anymore. You are using %s.", v)

# ----- import and verify M2Crypto

import M2Crypto
import M2Crypto.m2
if "ec_init" not in M2Crypto.m2.__dict__:
    logger.warn("WARNING: Could not import specialistic M2Crypto (imported %s)", M2Crypto.__file__)

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

# ----- build the app bundle
mainfile = os.path.join(LIBRARYNAME, 'Main', 'tribler.py')
setup(
    setup_requires=['py2app'],
    name='Tribler',
    app=[mainfile],
    options={'py2app': {
        'argv_emulation': True,
        'includes': includeModules,
        'excludes': ["Tkinter", "Tkconstants", "tcl", "PyQt5"],
        'iconfile': LIBRARYNAME + '/Main/Build/Mac/tribler.icns',
        'plist': Plist.fromFile(LIBRARYNAME + '/Main/Build/Mac/Info.plist'),
        'optimize': 0 if __debug__ else 2,
        'resources':
            [(LIBRARYNAME + "/Core/Category", [LIBRARYNAME + "/Core/Category/category.conf"]),
             (LIBRARYNAME + "/Core/DecentralizedTracking/pymdht/core",
              [LIBRARYNAME + "/Core/DecentralizedTracking/pymdht/core/bootstrap_stable"]),
             (LIBRARYNAME + "/Core/DecentralizedTracking/pymdht/core",
              [LIBRARYNAME + "/Core/DecentralizedTracking/pymdht/core/bootstrap_unstable"]),
             LIBRARYNAME + "/Main/Build/Mac/TriblerDoc.icns",
             ]
            + ["/Users/tribler/Documents/workspace/install/libsodium.dylib"]

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
