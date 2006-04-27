from bundlebuilder import buildapp
from distutils.util import get_platform

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

sys.path=[
  "m2crypto/build/lib.%s-2.3/" % get_platform(),
  "bsddb3/build/lib.%s-2.3/" % get_platform()
  ]+sys.path

import M2Crypto

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
    iconfile='tribler.icns',
    argv_emulation=1,
    #strip=1,
    semi_standalone=1,
    excludeModules=["Tkinter","Tkconstants","tcl"],
    includeModules=["M2Crypto","wx","wxPython"],
    libs=[wx_lib],
    files = [("Lang/english.lang","Contents/Resources/Lang/"),
             ("superpeer.txt",    "Contents/Resources/"),
             ("icons/",           "Contents/Resources/icons"),
             ("LICENSE.txt",      "Contents/Resources/"),
             ("readme.txt",       "Contents/Resources/"),
             ("tribler.ico",      "Contents/Resources/"),
             ("torrenticon.ico",  "Contents/Resources/")]
)

# fix library lookup in wx's *.so
so_dir = "build/Tribler.app/Contents/Resources/ExtensionModules/wx"
so_files = [x for x in os.listdir( so_dir ) if x.endswith(".so")]

for f in so_files:
	os.system("install_name_tool -change %s %s %s/%s" % (wx_lib,os.path.basename(wx_lib),so_dir,f))
