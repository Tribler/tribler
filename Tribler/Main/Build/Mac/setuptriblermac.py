# ---------------
# This script builds build/Tribler.app
#
# Meant to be called from mac/Makefile
# ---------------

import py2app
from distutils.util import get_platform
import sys,os,platform,shutil
from setuptools import setup
from Tribler.__init__ import LIBRARYNAME

# modules to include into bundle
includeModules=["encodings.hex_codec","encodings.utf_8","encodings.latin_1","xml.sax", "email.iterators"]

# gui panels to include
includePanels=[
     "list","list_header","list_body","list_footer","list_details",
     "home","settingsDialog","TopSearchPanel","SearchGridManager","SRstatusbar"]# ,"btn_DetailsHeader","tribler_List","TopSearchPanel","settingsOverviewPanel"] # TextButton


includeModules += ["Tribler.Main.vwxGUI.%s" % x for x in includePanels]

# ----- some basic checks

if __debug__:
    print "WARNING: Non optimised python bytecode (.pyc) will be produced. Run with -OO instead to produce and bundle .pyo files."

if sys.platform != "darwin":
    print "WARNING: You do not seem to be running Mac OS/X." 

# ----- import and verify wxPython

"""
import wxversion

wxversion.select('2.8-unicode')
"""
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

# ----- build the app bundle
mainfile = os.path.join(LIBRARYNAME,'Main','tribler.py')
setup(
    setup_requires=['py2app'],
    name='Tribler',
    app=[mainfile],
    options={ 'py2app': {
        'argv_emulation': True,
        'includes': includeModules,
        'excludes': ["Tkinter","Tkconstants","tcl"],
        'iconfile': LIBRARYNAME+'/Main/Build/Mac/tribler.icns',
        'plist': Plist.fromFile(LIBRARYNAME+'/Main/Build/Mac/Info.plist'),
        'optimize': 0 if __debug__ else 2,
        'resources':
            [(LIBRARYNAME+"/Lang", [LIBRARYNAME+"/Lang/english.lang"]),
             (LIBRARYNAME+"/Core", [LIBRARYNAME+"/Core/superpeer.txt"]),
             (LIBRARYNAME+"/Category", [LIBRARYNAME+"/Category/category.conf"]),
             (LIBRARYNAME+"/Core/Tag", [LIBRARYNAME+"/Core/Tag/stop_snowball.filter"]),
             LIBRARYNAME+"/readme.txt",
             LIBRARYNAME+"/Main/Build/Mac/TriblerDoc.icns",
           ]
           # add images
           + includedir( LIBRARYNAME+"/Images" )
           + includedir( LIBRARYNAME+"/Video/Images" )
           + includedir( LIBRARYNAME+"/Main/vwxGUI/images" )

           # add GUI elements
           + filterincludes( includedir( LIBRARYNAME+"/Main/vwxGUI" ), lambda x: x.endswith(".xrc") )

           # add crawler info and SQL statements
           + filterincludes( includedir( LIBRARYNAME+"/Core/Statistics" ), lambda x: x.endswith(".txt") )
           + filterincludes( includedir( LIBRARYNAME+"/Core/Statistics" ), lambda x: x.endswith(".sql") )
           + filterincludes( includedir( LIBRARYNAME+"/" ), lambda x: x.endswith(".sql") )

           # add VLC plugins
           + includedir( "vlc" )

           # add ffmpeg binary
           + [("vlc",["vlc/ffmpeg"])]
            ,
    } }
)

