# Written by Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information

import sys

from Tribler.Core.simpledefs import *
from Tribler.Core.DownloadConfig import DownloadConfigInterface
from Tribler.Core.APIImplementation.DownloadRuntimeConfigBaseImpl import DownloadRuntimeConfigBaseImpl
from Tribler.Core.exceptions import OperationNotPossibleAtRuntimeException

DEBUG = False

# 10/02/10 Boudewijn: pylint points out that member variables used in
# DownloadRuntimeConfig do not exist.  This is because they are set in
# Tribler.Core.Download which is a subclass of DownloadRuntimeConfig.
#
# We disable this error
# pylint: disable-msg=E1101


class DownloadRuntimeConfig(DownloadRuntimeConfigBaseImpl):

    """
    Implements the Tribler.Core.DownloadConfig.DownloadConfigInterface

    Only implement the setter for parameters that are actually runtime
    configurable here. Default behaviour implemented by BaseImpl.

    DownloadConfigInterface: All methods called by any thread
    """
    def set_max_speed(self, direct, speed):
        if DEBUG:
            print >> sys.stderr, "Download: set_max_speed", repr(self.get_def().get_metainfo()['info']['name']), direct, speed
        # print_stack()

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

    def get_max_speed(self, direct):
        self.dllock.acquire()
        try:
            return DownloadConfigInterface.get_max_speed(self, direct)
        finally:
            self.dllock.release()

    def set_dest_dir(self, path):
        raise OperationNotPossibleAtRuntimeException()

    def set_corrected_filename(self, path):
        raise OperationNotPossibleAtRuntimeException()

    def set_video_event_callback(self, usercallback):
        """ Note: this currently works only when the download is stopped. """
        self.dllock.acquire()
        try:
            DownloadConfigInterface.set_video_event_callback(self, usercallback)
        finally:
            self.dllock.release()

    def set_video_events(self, events):
        """ Note: this currently works only when the download is stopped. """
        self.dllock.acquire()
        try:
            DownloadConfigInterface.set_video_events(self, events)
        finally:
            self.dllock.release()

    def set_mode(self, mode):
        """ Note: this currently works only when the download is stopped. """
        self.dllock.acquire()
        try:
            DownloadConfigInterface.set_mode(self, mode)
        finally:
            self.dllock.release()

    def set_selected_files(self, files):
        """ Note: this currently works only when the download is stopped. """
        self.dllock.acquire()
        try:
            DownloadConfigInterface.set_selected_files(self, files)
            self.set_filepieceranges(self.tdef.get_metainfo())
        finally:
            self.dllock.release()
