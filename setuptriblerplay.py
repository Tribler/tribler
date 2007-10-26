# setup.py
import time
import sys

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

target_triblerplay = {
    "script": "p2player.py",
    "icon_resources": [(1, "tribler.ico")],
}

setup(
#    (Disabling bundle_files for now -- apparently causes some issues with Win98)
#    options = {"py2exe": {"bundle_files": 1}},
#    zipfile = None,
    options = {"py2exe": {"packages": ["tribler","encodings"] + ["Tribler.vwxGUI.%s" % x for x in includePanels],
                          "optimize": 2}},
    data_files = [("tribler", ["tribler.exe.manifest", "tribler.nsi", "tribler.ico", "torrenticon.ico", "binary-LICENSE.txt", "readme.txt"])], 
    windows = [target_triblerplay],
)
