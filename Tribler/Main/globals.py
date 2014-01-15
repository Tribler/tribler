# Written by Arno Bakker
# see LICENSE.txt for license information

import os
import copy

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Utilities.configparser import CallbackConfigParser

STATEDIR_DLCONFIG = "tribler.conf"


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

    def load(filename):
        dlconfig = CallbackConfigParser()
        if not dlconfig.read(filename):
            raise IOError, "Failed to open download config file"
        return DefaultDownloadStartupConfig(dlconfig)
    load = staticmethod(load)

    def copy(self):
        config = CallbackConfigParser()
        config._sections = {'downloadconfig': copy.deepcopy(self.dlconfig._sections['downloadconfig'])}
        return DownloadStartupConfig(config)

def get_default_dscfg_filename(state_dir):
    return os.path.join(state_dir, STATEDIR_DLCONFIG)
