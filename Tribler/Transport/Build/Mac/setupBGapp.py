# Written by Riccardo Petrocco
# see LICENSE.txt for license information
#
# This script builds SwarmPlayer FF plugin
#
#

import os
from distutils.util import get_platform
import sys
import os
import platform
import shutil

from plistlib import Plist

from setuptools import setup
import py2app  # Not a superfluous import!

from Tribler.__init__ import LIBRARYNAME


def includedir(srcpath, dstpath= None):
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


# modules to include into bundle
includeModules = ["encodings.hex_codec", "encodings.utf_8", "encodings.latin_1", "xml.sax", "email.iterators"]

# ----- build the app bundle
mainfile = os.path.join(LIBRARYNAME, 'Transport', 'SwarmEngine.py')

setup(
    setup_requires=['py2app'],
    name='SwarmPlayer',
    app=[mainfile],
    options={'py2app': {
        'argv_emulation': True,
        'includes': includeModules,
        'excludes': ["Tkinter", "Tkconstants", "tcl"],
        'iconfile': LIBRARYNAME + '/Player/Build/Mac/tribler.icns',
        'plist': Plist.fromFile(LIBRARYNAME + '/Transport/Build/Mac/Info.plist'),
        'resources':
            [LIBRARYNAME + "/readme.txt",
             LIBRARYNAME + "/Images/SwarmPlayerIcon.ico",
             LIBRARYNAME + "/Player/Build/Mac/TriblerDoc.icns",
             ]
        # add images
        + includedir(LIBRARYNAME +"/Images")

        # add Web UI files
        + includedir(LIBRARYNAME +"/WebUI")
    }}
)
