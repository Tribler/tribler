# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import os
import shutil
import binascii
from threading import currentThread
from traceback import print_exc

from Tribler.Core.simpledefs import *
from Tribler.Core.APIImplementation.ThreadPool import ThreadNoPool
from Tribler.Core.CacheDB.Notifier import Notifier

DEBUG = False


class UserCallbackHandler:

    def __init__(self, session):
        self.session = session
        self.sesslock = session.sesslock

        # Notifier for callbacks to API user
        self.threadpool = ThreadNoPool()

        self.notifier = Notifier.getInstance(self.threadpool)

    def shutdown(self):
        # stop threadpool
        Notifier.delInstance()
        self.threadpool.joinAll()

    def perform_vod_usercallback(self, d, usercallback, event, params):
        """ Called by network thread """
        if DEBUG:
            print >> sys.stderr, "Session: perform_vod_usercallback()", repr(d.get_def().get_name())

        def session_vod_usercallback_target():
            try:
                usercallback(d, event, params)
            except:
                print_exc()
        self.perform_usercallback(session_vod_usercallback_target)

    def perform_getstate_usercallback(self, usercallback, data, returncallback):
        """ Called by network thread """
        if DEBUG:
            print >> sys.stderr, "Session: perform_getstate_usercallback()"

        def session_getstate_usercallback_target():
            try:
                (when, getpeerlist) = usercallback(data)
                returncallback(usercallback, when, getpeerlist)
            except:
                print_exc()
        self.perform_usercallback(session_getstate_usercallback_target)

    def perform_removestate_callback(self, infohash, contentdests, removecontent):
        """ Called by network thread """
        if DEBUG:
            print >> sys.stderr, "Session: perform_removestate_callback()"

        def session_removestate_callback_target():
            if DEBUG:
                print >> sys.stderr, "Session: session_removestate_callback_target called", currentThread().getName()
            try:
                self.sesscb_removestate(infohash, contentdests, removecontent)
            except:
                print_exc()
        self.perform_usercallback(session_removestate_callback_target)

    def perform_usercallback(self, target):
        # TODO: thread pool, etc.
        self.threadpool.queueTask(target)

    def sesscb_removestate(self, infohash, contentdests, removecontent):
        """  See DownloadImpl.setup().
        Called by SessionCallbackThread """
        if DEBUG:
            print >> sys.stderr, "Session: sesscb_removestate called", repr(infohash), contentdests, removecontent
        self.sesslock.acquire()
        try:
            if self.session.lm.download_exists(infohash):
                print >> sys.stderr, "Session: sesscb_removestate: Download is back, restarted? Canceling removal!", repr(infohash)
                return

            dlpstatedir = os.path.join(self.session.get_state_dir(), STATEDIR_DLPSTATE_DIR)
        finally:
            self.sesslock.release()

        # Remove checkpoint
        hexinfohash = binascii.hexlify(infohash)
        try:
            basename = hexinfohash + '.state'
            filename = os.path.join(dlpstatedir, basename)
            if DEBUG:
                print >> sys.stderr, "Session: sesscb_removestate: removing dlcheckpoint entry", filename
            if os.access(filename, os.F_OK):
                os.remove(filename)
        except:
            # Show must go on
            print_exc()

        # Remove downloaded content from disk
        if removecontent:
            if DEBUG:
                print >> sys.stderr, "Session: sesscb_removestate: removing saved content", contentdests

            contentdirs = set()
            for filename in contentdests:
                if os.path.isfile(filename):
                    os.remove(filename)
                contentdirs.add(os.path.dirname(filename))

            # multifile, see if we need to remove any empty dirs
            if len(contentdests) > 1:
                def remove_if_empty(basedir):
                    # first try to remove sub-dirs
                    if os.path.isdir(basedir):
                        files = os.listdir(basedir)
                        for filename in files:
                            absfilename = os.path.join(basedir, filename)
                            if os.path.isdir(absfilename) and absfilename in contentdirs:
                                remove_if_empty(absfilename)

                        # see if we are empty
                        files = os.listdir(basedir)
                        # ignore thumbs.db files
                        files = [file for file in files if not file.lower().endswith('thumbs.db')]

                        if len(files) == 0:
                            os.rmdir(basedir)

                basedir = os.path.commonprefix(contentdests)
                remove_if_empty(basedir)

    def notify(self, subject, changeType, obj_id, *args):
        """
        Notify all interested observers about an event with threads from the pool
        """
        if DEBUG:
            print >> sys.stderr, "ucb: notify called:", subject, changeType, repr(obj_id), args
        self.notifier.notify(subject, changeType, obj_id, *args)
