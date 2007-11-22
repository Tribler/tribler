# setup.py
import time
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

# gui panels to include
includePanels=[
     "standardOverview","standardDetails","standardGrid","standardPager","standardFilter",
     "TextButton","btn_DetailsHeader","tribler_List","profileOverviewPanel"]

################################################################
#
# Setup script used for py2exe
#
# *** Important note: ***
# Setting Python's optimize flag when building disables
# "assert" statments, which are used throughout the
# BitTornado core for error-handling.
#
################################################################

mainfile = os.path.join('Player','p2player.py')
#manifest = os.path.join('Player','Build','Win32','p2player.exe.manifest')
#nsifile = os.path.join('Player','Build','Win32','triblerplay.nsi')
progicofile = os.path.join('Images','tribler.ico')
#toricofile = os.path.join('Images','torrenticon.ico')

target_p2player = {
    "script": mainfile,
    "icon_resources": [(1, progicofile)],
}


setup(
#    (Disabling bundle_files for now -- apparently causes some issues with Win98)
#    options = {"py2exe": {"bundle_files": 1}},
#    zipfile = None,
    options = {"py2exe": {"packages": ["Core","encodings"] + ["Tribler.Main.vwxGUI.%s" % x for x in includePanels],
                          "optimize": 2}},
    data_files = [("installdir",[])], 
    windows = [target_p2player],
)

#data_files = [("installdir", [manifest, nsifile, progicofile, toricofile, "binary-LICENSE.txt", "readme.txt"])],