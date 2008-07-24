# Written by Arno Bakker 
# see LICENSE.txt for license information

import sys
import os
import pickle

STATEDIR_DLCONFIG = "dlconfig.pickle"

# Global variable containing the DownloadStartupConfig to use for crearing 
# Downloads
from Tribler.Core.DownloadConfig import DownloadStartupConfig

class DefaultDownloadStartupConfig(DownloadStartupConfig):
    __single = None
    
    def __init__(self,dlconfig=None):
        
        if DefaultDownloadStartupConfig.__single:
            raise RuntimeError, "DefaultDownloadStartupConfig is singleton"
        DefaultDownloadStartupConfig.__single = self

        DownloadStartupConfig.__init__(self,dlconfig=dlconfig)

    def getInstance(*args, **kw):
        if DefaultDownloadStartupConfig.__single is None:
            DefaultDownloadStartupConfig(*args, **kw)
        return DefaultDownloadStartupConfig.__single
    getInstance = staticmethod(getInstance)

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
        f = open(filename,"rb")
        dlconfig = pickle.load(f)
        dscfg = DefaultDownloadStartupConfig(dlconfig)
        f.close()
        return dscfg
    load = staticmethod(load)


def get_default_dscfg_filename(session):
    return os.path.join(session.get_state_dir(),STATEDIR_DLCONFIG)        
