# ---------------
# This script builds build/Tribler.app
#
# Meant to be called from mac/Makefile
# ---------------

import py2app
from distutils.util import get_platform
import sys,os,platform,shutil
from setuptools import setup

# modules to include into bundle
includeModules=["encodings.hex_codec","encodings.utf_8","encodings.latin_1","xml.sax", "email.iterators"]

# gui panels to include
includePanels=[
     "standardOverview","standardDetails","standardGrid","standardPager","standardFilter",
     "TextButton","btn_DetailsHeader","tribler_List","profileOverviewPanel"]

includeModules += ["Tribler.vwxGUI.%s" % x for x in includePanels]

# ----- some basic checks

if __debug__:
    print "WARNING: Non optimised python bytecode (.pyc) will be produced. Run with -OO instead to produce and bundle .pyo files."

if sys.platform != "darwin":
    print "WARNING: You do not seem to be running Mac OS/X." 

# ----- import and verify wxPython

import wxversion

wxversion.select('2.8-unicode')

import wx

v = wx.__version__

if v < "2.6":
    print "WARNING: You need wxPython 2.6 or higher but are using %s." % v

if v < "2.8.4.2":
    print "WARNING: wxPython before 2.8.4.2 could crash when loading non-present fonts. You are using %s." % v

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

# ----- import VLC

import vlc

vlc = vlc.MediaControl(["--plugin-path","lib/vlc"])

# =================
# build Tribler.app
# =================

from plistlib import Plist

def includedir( srcpath, dstpath = None ):
    """ Recursive directory listing, filtering out svn files. """

    total = []

    cwd = os.getcwd()
    os.chdir( srcpath )

    if dstpath is None:
        dstpath = srcpath

    for root,dirs,files in os.walk( "." ):
        if '.svn' in dirs:
            dirs.remove('.svn')

        for f in files:
            total.append( (root,f) )

    os.chdir( cwd )

    # format: (targetdir,[file])
    # so for us, (dstpath/filedir,[srcpath/filedir/filename])
    return [("%s/%s" % (dstpath,root),["%s/%s/%s" % (srcpath,root,f)]) for root,f in total]

def filterincludes( l, f ):
    """ Return includes which pass filter f. """

    return [(x,y) for (x,y) in l if f(y[0])]

# ----- update .xrc files

from Tribler.Main.vwxGUI.updateXRC import main as updateXRC

updateXRC( [os.path.abspath(os.path.dirname(sys.argv[0]))+"/vwxGUI"] )

# ----- build the app bundle

setup(
    setup_requires=['py2app'],
    name='Tribler',
    app=['tribler.py'],
    options={ 'py2app': {
        'argv_emulation': True,
        'includes': includeModules,
        'excludes': ["Tkinter","Tkconstants","tcl"],
        'iconfile': 'mac/tribler.icns',
        'plist': Plist.fromFile('mac/Info.plist'),
        'optimize': 2*int(not __debug__),
        'resources':
            [("Lang", ["Lang/english.lang"]),
             "superpeer.txt",
             "category.conf",
             "binary-LICENSE.txt", 
             "readme.txt",
             "tribler.ico",
             "torrenticon.ico",
             "mac/TriblerDoc.icns",
             ("lib", ["mac/build/lib/ffmpeg"],
           )]
           # add images
           + includedir( "icons" )
           + includedir( "Tribler/vwxGUI/images" )

           # add GUI elements
           + filterincludes( includedir( "Tribler/vwxGUI" ), lambda x: x.endswith(".xrc") )

           # add VLC plugins
           + filterincludes( includedir( "mac/build/lib/vlc", "lib/vlc" ), lambda x: x.endswith(".dylib") )
            ,
    } }
)
