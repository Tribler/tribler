# setup.py
from distutils.core import setup
import py2exe


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
    "script": "abc.py",
    "icon_resources": [(1, "tribler.ico")],
}

setup(
#    (Disabling bundle_files for now -- apparently causes some issues with Win98)
#    options = {"py2exe": {"bundle_files": 1}},
#    zipfile = None,
    data_files = [("ABC", ["abc.exe.manifest", "abc.nsi", "tribler.ico", "torrenticon.ico", "LICENSE.txt", "readme.txt"])], 
    windows = [target_abc],
)
