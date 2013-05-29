# Written by ABC authors and Arno Bakker
# see LICENSE.txt for license information
import sys
import os

from Tribler.__init__ import LIBRARYNAME
from Tribler.Lang.lang import Lang

#
#
# Class: UtilityStub
#
#


class UtilityStub:

    def __init__(self, installdir, statedir):
        self.installdir = installdir
        self.statedir = statedir

        self.config = self

        # Setup language files
        self.lang = Lang(self)

    def getConfigPath(self):
        return self.statedir

    def getPath(self):
        return self.installdir.decode(sys.getfilesystemencoding())

    def Read(self, key):
        if key == 'language_file':
            return os.path.join(self.installdir, LIBRARYNAME, 'Lang', 'english.lang')
        elif key == 'videoplayerpath':
            return 'vlc'
        return None
