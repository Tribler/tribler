# Written by Arno Bakker
# see LICENSE.txt for license information

import copy
import logging

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Utilities.configparser import CallbackConfigParser


class DefaultDownloadStartupConfig(DownloadStartupConfig):
    __single = None

    def __init__(self, dlconfig=None):

        if DefaultDownloadStartupConfig.__single:
            raise RuntimeError("DefaultDownloadStartupConfig is singleton")
        DefaultDownloadStartupConfig.__single = self

        DownloadStartupConfig.__init__(self, dlconfig=dlconfig)

        self._logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def getInstance(*args, **kw):
        if DefaultDownloadStartupConfig.__single is None:
            DefaultDownloadStartupConfig(*args, **kw)
        return DefaultDownloadStartupConfig.__single

    @staticmethod
    def delInstance(*args, **kw):
        DefaultDownloadStartupConfig.__single = None

    @staticmethod
    def load(filename):
        dlconfig = CallbackConfigParser()
        dlconfig.read_file(filename)
        return DefaultDownloadStartupConfig(dlconfig)

    def copy(self):
        config = CallbackConfigParser()
        config._sections = {'downloadconfig': copy.deepcopy(self.dlconfig._sections['downloadconfig'])}
        return DownloadStartupConfig(config)
