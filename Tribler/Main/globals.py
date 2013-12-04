# Written by Arno Bakker
# see LICENSE.txt for license information

import os
import logging
import copy

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.SessionConfig import CallbackConfigParser

STATEDIR_DLCONFIG = "tribler.conf"


class DefaultDownloadStartupConfig(DownloadStartupConfig):
    __single = None

    def __init__(self, dlconfig=None):

        if DefaultDownloadStartupConfig.__single:
            raise RuntimeError("DefaultDownloadStartupConfig is singleton")
        DefaultDownloadStartupConfig.__single = self

        DownloadStartupConfig.__init__(self, dlconfig=dlconfig)

        self._logger = logging.getLogger(self.__class__.__name__)

    def getInstance(*args, **kw):
        if DefaultDownloadStartupConfig.__single is None:
            DefaultDownloadStartupConfig(*args, **kw)
        return DefaultDownloadStartupConfig.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        DefaultDownloadStartupConfig.__single = None
    delInstance = staticmethod(delInstance)

    def copy(self):
        config = CallbackConfigParser()
        config._sections = {'downloadconfig': copy.deepcopy(self.dlconfig._sections['downloadconfig'])}
        return DownloadStartupConfig(config)

def get_default_dscfg_filename(state_dir):
    return os.path.join(state_dir, STATEDIR_DLCONFIG)
