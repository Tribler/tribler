# Written by Arno Bakker
# see LICENSE.txt for license information

import os

STATEDIR_DLCONFIG = "dlconfig.conf"

# Global variable containing the DownloadStartupConfig to use for creating downloads
from Tribler.Core.DownloadConfig import DownloadStartupConfig

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

    def delInstance(*args, **kw):
        DefaultDownloadStartupConfig.__single = None
    delInstance = staticmethod(delInstance)


def get_default_dscfg_filename(state_dir):
    return os.path.join(state_dir, STATEDIR_DLCONFIG)
