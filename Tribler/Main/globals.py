# Written by Arno Bakker 
# see LICENSE.txt for license information

import sys
import os

STATEDIR_DLCONFIG = "dlconfig.pickle"

# Global variable containing the DownloadStartupConfig to use for crearing 
# Downloads
from Tribler.Core.DownloadConfig import DownloadStartupConfig

class DefaultDownloadStartupConfig(DownloadStartupConfig):
    __single = None
    
    def __init__(self):
        if DefaultDownloadStartupConfig.__single:
            raise RuntimeError, "DefaultDownloadStartupConfig is singleton"
        DefaultDownloadStartupConfig.__single = self

        DownloadStartupConfig.__init__(self)

    def getInstance(*args, **kw):
        if DefaultDownloadStartupConfig.__single is None:
            DefaultDownloadStartupConfig(*args, **kw)
        return DefaultDownloadStartupConfig.__single
    getInstance = staticmethod(getInstance)


def get_default_dscfg_filename(session):
    return os.path.join(session.get_state_dir(),STATEDIR_DLCONFIG)        
