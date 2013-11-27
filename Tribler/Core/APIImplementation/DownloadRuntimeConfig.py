# Written by Arno Bakker
# Updated by Egbert Bouman
# see LICENSE.txt for license information

from Tribler.Core.DownloadConfig import DownloadConfigInterface

# 10/02/10 Boudewijn: pylint points out that member variables used in
# DownloadRuntimeConfig do not exist.  This is because they are set in
# Tribler.Core.Download which is a subclass of DownloadRuntimeConfig.
#
# We disable this error
# pylint: disable-msg=E1101


class DownloadRuntimeConfig(DownloadConfigInterface):

    """
    Implements the Tribler.Core.DownloadConfig.DownloadConfigInterface

    Only implement the setter for parameters that are actually runtime
    configurable here. Default behaviour implemented by BaseImpl.

    DownloadConfigInterface: All methods called by any thread
    """

    def set_config_callback(self, callback):
        self.dlconfig.set_callback(callback)

    def _execute_with_sesslock(self, f, *args, **kwargs):
        with self.dllock:
            return f(*args, **kwargs)

    def __getattribute__(self, name):
        attr = DownloadConfigInterface.__getattribute__(self, name)
        if name in dir(DownloadConfigInterface):
            if name.startswith('get_') or name.startswith('set_'):
                if hasattr(attr, '__call__'):
                    return lambda *args, **kwargs: self._execute_with_sesslock(attr, *args, **kwargs)
        return attr
