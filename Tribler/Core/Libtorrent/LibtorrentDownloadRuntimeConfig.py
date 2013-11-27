# Written by Egbert Bouman, based on SwiftDownloadRuntimeConfig.py by Arno Bakker
# see LICENSE.txt for license information

import sys

from Tribler.Core.simpledefs import UPLOAD
from Tribler.Core.DownloadConfig import DownloadConfigInterface

DEBUG = False

# 10/02/10 Boudewijn: pylint points out that member variables used in
# DownloadRuntimeConfig do not exist.  This is because they are set in
# Tribler.Core.Download which is a subclass of DownloadRuntimeConfig.
#
# We disable this error
# pylint: disable-msg=E1101


class LibtorrentDownloadRuntimeConfig(DownloadConfigInterface):

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
        if DEBUG:
            print >> sys.stderr, "Download: set_max_speed", repr(self.get_def().get_metainfo()['info']['name']), direct, speed

        self.dllock.acquire()
        try:
            # Don't need to throw an exception when stopped, we then just save the new value and
            # use it at (re)startup.
            if self.handle is not None:
                if direct == UPLOAD:
                    set_max_speed_lambda = lambda: self.handle is not None and self.handle.set_upload_limit(int(speed * 1024))
                else:
                    set_max_speed_lambda = lambda: self.handle is not None and self.handle.set_download_limit(int(speed * 1024))
                self.session.lm.rawserver.add_task(set_max_speed_lambda, 0)

            # At the moment we can't catch any errors in the engine that this
            # causes, so just assume it always works.
            DownloadConfigInterface.set_max_speed(self, direct, speed)
        finally:
            self.dllock.release()
