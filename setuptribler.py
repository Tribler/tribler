# setup.py
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

target_abc = {
    "script": "abc_vwx.py",
    "icon_resources": [(1, "tribler.ico")],
}

setup(
#    (Disabling bundle_files for now -- apparently causes some issues with Win98)
#    options = {"py2exe": {"bundle_files": 1}},
#    zipfile = None,
    options = {"py2exe": {"packages": ["abc_vwx","encodings"] + ["Tribler.vwxGUI.%s" % x for x in includePanels],
                          "optimize": 2}},
    data_files = [("tribler", ["tribler.exe.manifest", "tribler.nsi", "tribler.ico", "torrenticon.ico", "binary-LICENSE.txt", "readme.txt"])], 
    windows = [target_abc],
)
