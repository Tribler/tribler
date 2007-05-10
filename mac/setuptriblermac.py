# ---------------
# This script builds build/Tribler.app
#
# Meant to be called from mac/Makefile
# ---------------

import bundlebuilder
from distutils.util import get_platform
import sys,os,platform

# modules to include into bundle
includeModules=["M2Crypto","wx","wxPython","encodings.utf_8","encodings.latin_1","argvemulator","_xmlplus.sax"]

# gui panels to include
includePanels=[
     "standardOverview","standardDetails","standardGrid","standardPager","standardFilter",
     "TextButton","btn_DetailsHeader","tribler_List","profileOverviewPanel"]

# ----- some basic checks

if __debug__:
    print "WARNING: Non optimised python bytecode (.pyc) will be produced. Run with -OO instead to produce and bundle .pyo files."

if sys.platform != "darwin":
    print "WARNING: You do not seem to be running Mac OS/X." 

if get_platform().split("-")[2] != "fat":
    if platform.processor() == "i386":
        print "WARNING: You are using an Intel Mac but not a Universal Binary of Python. The produced bundle will not run on PPC Macs."
    else:
        print "WARNING: Not using and thus not shipping a Universal Binary of Python. This leads to a slower Tribler on Intel Macs."

# ----- import and verify wxPython

import wxversion

wxversion.select('2.8-unicode')

import wx

# For now, assume a specific location for the wxPython libraries until
# someone finds a better way of discovering it.

if wx.__version__ < "2.6":
    print "WARNING: You need wxPython 2.6 or higher but are using %s." % wx.__version__

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

# ----- import and verify M2Crypto

import M2Crypto
import M2Crypto.m2
if "ec_init" not in M2Crypto.m2.__dict__:
    print "WARNING: Could not import specialistic M2Crypto (imported %s)" % M2Crypto.__file__

# ----- import Growl
try:
    import Growl

    includeModules += ["Growl"]
except:
    print "WARNING: Not including Growl support."

from plistlib import Plist

################################################################
#
# *** Important note: ***
# Setting Python's optimize flag when building disables
# "assert" statments, which are used throughout the
# BitTornado core for error-handling.
#
################################################################

def includedir( path ):
    """ Recursive directory listing, filtering out svn files. """

    total = []

    for root,dirs,files in os.walk( path ):
        if '.svn' in dirs:
            dirs.remove('.svn')

        for f in files:
            total.append( "%s/%s" % (root,f) )

    return [(x,"Contents/Resources/%s" % x) for x in total]

def filterincludes( l, f ):
    return [(x,y) for (x,y) in l if f(x)]

# ----- ugly hack to be able to use .pyo files

if not __debug__:
    s = bundlebuilder.BOOTSTRAP_SCRIPT.split("\n")
    s.insert(-2,'os.environ["PYTHONOPTIMIZE"] = "2"')
    bundlebuilder.BOOTSTRAP_SCRIPT = "\n".join(s)

# ----- build the app bundle

bundlebuilder.buildapp(
    name='Tribler.app',
    mainprogram='tribler.py',
    iconfile='mac/tribler.icns',
    plist=Plist.fromFile('mac/Info.plist'),
    argv_emulation=1,
    strip=1,
    #semi_standalone=1,
    optimize=3*int(not __debug__),
    standalone=1,
    excludeModules=["Tkinter","Tkconstants","tcl"],
    includeModules=includeModules + ["Tribler.vwxGUI.%s" % x for x in includePanels],
    libs=[wx_lib],
    files = ([("Lang/english.lang","Contents/Resources/Lang/"),
             ("superpeer.txt",    "Contents/Resources/"),
             ("category.conf",    "Contents/Resources/"),
             ("binary-LICENSE.txt",      "Contents/Resources/"),
             ("readme.txt",       "Contents/Resources/"),
             ("tribler.ico",      "Contents/Resources/"),
             ("torrenticon.ico",  "Contents/Resources/"),
             ("mac/TriblerDoc.icns", "Contents/Resources/"),]
           + includedir( "icons" )
           + filterincludes( includedir( "Tribler/vwxGUI" ), lambda x: x.endswith(".xrc") )
           + includedir( "Tribler/vwxGUI/images" )
            )
)

# ----- post-process app bundle

# fix library lookup in wx's *.so to use relative paths
so_dir = "build/Tribler.app/Contents/Resources/ExtensionModules/wx"
so_files = [x for x in os.listdir( so_dir ) if x.endswith(".so")]

for f in so_files:
    os.system("install_name_tool -change %s %s %s/%s" % (wx_lib,os.path.basename(wx_lib),so_dir,f))
