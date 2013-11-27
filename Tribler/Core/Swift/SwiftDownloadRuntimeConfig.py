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

    def set_mode(self, mode):
        """ Note: this has no effect, swift currently doesn't have DL modes """
        self.dllock.acquire()
        try:
            DownloadConfigInterface.set_mode(self, mode)
        finally:
            self.dllock.release()
