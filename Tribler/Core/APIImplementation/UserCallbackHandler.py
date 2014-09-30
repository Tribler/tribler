# Written by Arno Bakker
# see LICENSE.txt for license information

import os
import binascii
from threading import currentThread
import logging

from Tribler.Core.simpledefs import STATEDIR_DLPSTATE_DIR
from Tribler.Core.APIImplementation.ThreadPool import ThreadNoPool
from Tribler.Core.CacheDB.Notifier import Notifier


class UserCallbackHandler(object):

    def __init__(self, session):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session = session
        self.session_lock = session.sesslock

        # Notifier for callbacks to API user
        self.threadpool = ThreadNoPool()

        self.notifier = Notifier(self.threadpool)

    def shutdown(self):
        # stop threadpool
        self.notifier.remove_observers()
        self.notifier = None

        self.threadpool.joinAll()
        self.threadpool = None

    def perform_getstate_usercallback(self, usercallback, data, returncallback):
        """ Called by network thread """
        self._logger.debug("Session: perform_getstate_usercallback()")

        def session_getstate_usercallback_target():
            try:
                (when, getpeerlist) = usercallback(data)
                returncallback(usercallback, when, getpeerlist)
            except:
                self._logger.exception('Could not perform usercallback')
        self.perform_usercallback(session_getstate_usercallback_target)

    def perform_removestate_callback(self, infohash, contentdests):
        """ Called by network thread """
        self._logger.debug("Session: perform_removestate_callback()")

        def session_removestate_callback_target():
            self._logger.debug("Session: session_removestate_callback_target called %s", currentThread().getName())
            try:
                self.sesscb_removestate(infohash, contentdests)
            except:
                self._logger.exception("Could not remove state")
        self.perform_usercallback(session_removestate_callback_target)

    def perform_usercallback(self, target):
        # TODO: thread pool, etc.
        self.threadpool.queueTask(target)

    def sesscb_removestate(self, infohash, contentdests):
        """  See DownloadImpl.setup().
        Called by SessionCallbackThread """
        self._logger.debug("Session: sesscb_removestate called %s %s", repr(infohash), contentdests)
        self.session_lock.acquire()
        try:
            if self.session.lm.download_exists(infohash):
                self._logger.info("Session: sesscb_removestate: Download is back, restarted? Canceling removal! %s",
                                  repr(infohash))
                return

            dlpstatedir = os.path.join(self.session.get_state_dir(), STATEDIR_DLPSTATE_DIR)
        finally:
            self.session_lock.release()

        # Remove checkpoint
        hexinfohash = binascii.hexlify(infohash)
        try:
            basename = hexinfohash + '.state'
            filename = os.path.join(dlpstatedir, basename)
            self._logger.debug("Session: sesscb_removestate: removing dlcheckpoint entry %s", filename)
            if os.access(filename, os.F_OK):
                os.remove(filename)
        except:
            # Show must go on
            self._logger.exception("Could not remove state")

    def notify(self, subject, change_type, obj_id, *args):
        """
        Notify all interested observers about an event with threads from the pool
        """
        self._logger.debug("ucb: notify called: %s %s %s %s", subject, change_type, repr(obj_id), args)
        self.notifier.notify(subject, change_type, obj_id, *args)
