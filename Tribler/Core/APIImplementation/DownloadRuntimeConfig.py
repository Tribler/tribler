# Written by Arno Bakker
# Modified by Egbert Bouman
# see LICENSE.txt for license information

import logging

from Tribler.Core.DownloadConfig import DownloadConfigInterface

# 10/02/10 Boudewijn: pylint points out that member variables used in
# DownloadRuntimeConfig do not exist.  This is because they are set in
# Tribler.Core.Download which is a subclass of DownloadRuntimeConfig.
#
# We disable this error
# pylint: disable-msg=E1101


class DownloadRuntimeConfig(DownloadConfigInterface):

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

    """
    Implements the Tribler.Core.DownloadConfig.DownloadConfigInterface

    Only implement the setter for parameters that are actually runtime
    configurable here. Default behaviour implemented by BaseImpl.

    DownloadConfigInterface: All methods called by any thread
    """

    def set_config_callback(self, callback):
        self.dlconfig.set_callback(callback)

    def _execute_with_dllock(self, f, *args, **kwargs):
        with self.dllock:
            return f(*args, **kwargs)

    def __getattribute__(self, name):
        attr = DownloadConfigInterface.__getattribute__(self, name)
        if name in dir(DownloadConfigInterface):
            if name.startswith('get_') or name.startswith('set_'):
                if hasattr(attr, '__call__'):
                    dllock_func = DownloadConfigInterface.__getattribute__(self, '_execute_with_dllock')
                    return lambda *args, **kwargs: dllock_func(attr, *args, **kwargs)
        return attr
