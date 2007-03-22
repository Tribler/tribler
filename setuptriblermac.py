from bundlebuilder import buildapp
from distutils.util import get_platform

import wxversion

wxversion.select('2.8-unicode')

import os,sys
import wx

# For now, assume a specific location for the wxPython libraries until
# someone finds a better way of discovering it.

assert wx.__version__ > "2.6", "You need wxPython 2.6 or higher."
wx_major,wx_minor = wx.__version__.split(".")[0:2]
if "unicode" in wx.PlatformInfo:
    u1,u2 = "unicode", "u"
else:
    u1,u2 = "ansi", ""

wx_lib="/usr/local/lib/wxPython-%s-%s/lib/libwx_mac%sd-%s.%s.0.dylib" % (
  u1,
  wx.__version__,
  u2,
  wx_major,
  wx_minor )

def libdirs( path ):
        return ["%s/%s" % (path,p)
                for p in os.listdir(path)
                if p.startswith("lib.")]

sys.path = libdirs("m2crypto/build") + sys.path

import M2Crypto
import M2Crypto.m2
assert "ec_init" in M2Crypto.m2.__dict__, "Could not import specialistic M2Crypto (imported %s)" % M2Crypto.__file__

from plistlib import Plist

################################################################
#
# *** Important note: ***
# Setting Python's optimize flag when building disables
# "assert" statments, which are used throughout the
# BitTornado core for error-handling.
#
################################################################

buildapp(
    name='Tribler.app',
    mainprogram='abc.py',
    iconfile='mac/tribler.icns',
    plist=Plist.fromFile('mac/Info.plist'),
    argv_emulation=1,
    strip=1,
    #semi_standalone=1,
    standalone=1,
    excludeModules=["Tkinter","Tkconstants","tcl"],
    includeModules=["M2Crypto","wx","wxPython","encodings.utf_8","encodings.latin_1","argvemulator","_xmlplus.sax"],
    libs=[wx_lib],
    files = [("Lang/english.lang","Contents/Resources/Lang/"),
             ("superpeer.txt",    "Contents/Resources/"),
             ("category.conf",    "Contents/Resources/"),
             ("icons/",           "Contents/Resources/icons"),
             ("binary-LICENSE.txt",      "Contents/Resources/"),
             ("readme.txt",       "Contents/Resources/"),
             ("tribler.ico",      "Contents/Resources/"),
             ("torrenticon.ico",  "Contents/Resources/"),
             ("mac/TriblerDoc.icns", "Contents/Resources/"),]
)

# fix library lookup in wx's *.so
so_dir = "build/Tribler.app/Contents/Resources/ExtensionModules/wx"
so_files = [x for x in os.listdir( so_dir ) if x.endswith(".so")]

for f in so_files:
        os.system("install_name_tool -change %s %s %s/%s" % (wx_lib,os.path.basename(wx_lib),so_dir,f))

try:
   os.remove("Tribler.dmg")
except:
   pass

try:
    os.mkdir("build/Sample Friend Icons")
except:
    pass

os.system("cp icons/mugshots/*.bmp 'build/Sample Friend Icons'")
os.system("hdiutil create -srcfolder build -format UDZO -fs HFS+ -volname Tribler Tribler.dmg")
