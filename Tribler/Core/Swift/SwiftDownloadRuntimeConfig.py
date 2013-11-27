# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import logging

from Tribler.Core.DownloadConfig import DownloadConfigInterface

# 10/02/10 Boudewijn: pylint points out that member variables used in
# DownloadRuntimeConfig do not exist.  This is because they are set in
# Tribler.Core.Download which is a subclass of DownloadRuntimeConfig.
#
# We disable this error
# pylint: disable-msg=E1101


class SwiftDownloadRuntimeConfig(DownloadConfigInterface):

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

    def set_max_speed(self, direct, speed):
        self._logger.debug("SwiftDownload: set_max_speed %s %s %s", self.get_def().get_name(), direct, speed)
        # print_stack()

        self.dllock.acquire()
        try:
            # Don't need to throw an exception when stopped, we then just
            # save the new value and use it at (re)startup.
            if self.sp is not None:

                cur = self.get_max_speed(direct)
                # Arno, 2012-07-31: Don't send message when no change, i2i comm
                # non-zero cost.
                if cur != speed:
                    self.sp.set_max_speed(self, direct, speed)

            # At the moment we can't catch any errors in the engine that this
            # causes, so just assume it always works.
            DownloadConfigInterface.set_max_speed(self, direct, speed)
        finally:
            self.dllock.release()
