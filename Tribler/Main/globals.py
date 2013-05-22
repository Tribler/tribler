# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import os
import pickle

STATEDIR_DLCONFIG = "dlconfig.pickle"

# Global variable containing the DownloadStartupConfig to use for crearing
# Downloads
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.defaults import DLDEFAULTS_VERSION, dldefaults


class DefaultDownloadStartupConfig(DownloadStartupConfig):
    __single = None

    def __init__(self, dlconfig=None):

        if DefaultDownloadStartupConfig.__single:
            raise RuntimeError("DefaultDownloadStartupConfig is singleton")
        DefaultDownloadStartupConfig.__single = self

        DownloadStartupConfig.__init__(self, dlconfig=dlconfig)

    def getInstance(*args, **kw):
        if DefaultDownloadStartupConfig.__single is None:
            DefaultDownloadStartupConfig(*args, **kw)
        return DefaultDownloadStartupConfig.__single
    getInstance = staticmethod(getInstance)

    def updateToCurrentVersion(self):
        newKeys = DownloadStartupConfig.updateToCurrentVersion(self)
        if newKeys:
            for key in newKeys:
                print >>sys.stderr, "DefaultDownloadStartupConfig: Adding field", key
    #
    # Class method
    #

    def load(filename):
        """
        Load a saved DownloadStartupConfig from disk.

        @param filename  An absolute Unicode filename
        @return DefaultDownloadStartupConfig object
        """
        # Class method, no locking required
        f = open(filename, "rb")
        dlconfig = pickle.load(f)
        dscfg = DefaultDownloadStartupConfig(dlconfig)
        f.close()

        dscfg.updateToCurrentVersion()

        return dscfg
    load = staticmethod(load)


def get_default_dscfg_filename(state_dir):
    return os.path.join(state_dir, STATEDIR_DLCONFIG)
