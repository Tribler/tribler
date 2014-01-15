# ============================================================
# written by Lipu Fei
#
# This module maintains a list of trackers and their info. These information
# is also stored in the database.
#
# It provides two APIs: one is to update a tracker's info, the other is to
# check if a tracker is worth checking now. Because some trackers are gone
# or unreachable by some reason, it wastes a lot of time to check those
# "dead" trackers over and over again.
# ============================================================

import sys
import time
import logging
from threading import RLock

from Tribler.Core.Session import Session
from Tribler.Core.CacheDB.Notifier import NTFY_TRACKERINFO, NTFY_INSERT
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread, forceAndReturnDBThread
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.Core import NoDispersyRLock

# some default configurations
DEFAULT_MAX_TRACKER_FAILURES = 5  # A tracker that have failed for this
                                        # times will be regarded as "dead"
DEFAULT_DEAD_TRACKER_RETRY_INTERVAL = 60  # A "dead" tracker will be retired
                                         # every 60 seconds

# ============================================================
# This class maintains the tracker infomation cache.
# ============================================================
class TrackerInfoCache(object):

    # ------------------------------------------------------------
    # Initialization.
    # ------------------------------------------------------------
    def __init__(self, \
            max_failures=DEFAULT_MAX_TRACKER_FAILURES, \
            dead_tracker_recheck_interval=60):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._torrentdb = TorrentDBHandler.getInstance()
        self._tracker_info_dict = dict()

        self._tracker_update_request_dict = dict()

        self._max_tracker_failures = max_failures
        self._dead_tracker_recheck_Interval = dead_tracker_recheck_interval

        self._lock = NoDispersyRLock()

        session = Session.get_instance()
        session.add_observer(self.newTrackerCallback, NTFY_TRACKERINFO, [NTFY_INSERT, ])

    # ------------------------------------------------------------
    # Loads and initializes the cache from database.
    # ------------------------------------------------------------
    def loadCacheFromDb(self):
        @forceAndReturnDBThread
        def do_db():
            return self._torrentdb.getTrackerInfoList()

        tracker_info_list = do_db()

        # no need to use the lock when reloading
        self._lock.acquire()
        # update tracker info
        for tracker_info in tracker_info_list:
            tracker, alive, last_check, failures = tracker_info
            self._tracker_info_dict[tracker] = {'last_check':last_check, 'failures':failures, 'alive':alive, 'updated':False}

        self._lock.release()

    # ------------------------------------------------------------
    # The callback function when a new tracker has been inserted.
    # ------------------------------------------------------------
    def newTrackerCallback(self, subject, changeType, objectID, *args):
        # DB upgrade complete, reload everthing from DB
        if not objectID:
            self.loadCacheFromDb()
            return

        # create new trackers
        with self._lock:
            # new tracker insertion callback
            for tracker in objectID:
                self._logger.debug('New tracker[%s].', tracker)
                self._tracker_info_dict[tracker] = {'last_check':0, 'failures':0, 'alive':True, 'updated':False}

                # check all the pending update requests
                if tracker not in self._tracker_update_request_dict:
                    continue

                for request in self._tracker_update_request_dict[tracker]:
                    self._logger.debug('Handling new tracker[%s] request: %s', tracker, request)
                    self.updateTrackerInfo(tracker, request)
                del self._tracker_update_request_dict[tracker]

    # ------------------------------------------------------------
    # (Public API)
    # Checks if a tracker is worth checking now.
    # ------------------------------------------------------------
    def toCheckTracker(self, tracker):
        currentTime = int(time.time())

        tracker_dict = self._tracker_info_dict.get(tracker, {'alive': True, 'last_check':0})
        if tracker_dict['alive']:
            return True

        interval = currentTime - tracker_dict['last_check']
        return interval >= self._dead_tracker_recheck_Interval

    # ------------------------------------------------------------
    # (Public API)
    # Updates or a tracker's information. If the tracker does not
    # exist, it will be created.
    # ------------------------------------------------------------
    def updateTrackerInfo(self, tracker, success):
        currentTime = int(time.time())

        with self._lock:
            if tracker in self._tracker_info_dict:
                tracker_info = self._tracker_info_dict[tracker]
            else:
                # put into a request queue and update after the tracker has been
                # added by the DB thread.
                if tracker not in self._tracker_update_request_dict:
                    self._tracker_update_request_dict[tracker] = list()
                self._tracker_update_request_dict[tracker].append(success)
                return

            tracker_info['last_check'] = currentTime
            # reset the failures count if successful
            if success:
                tracker_info['failures'] = 0
            else:
                tracker_info['failures'] += 1

            # determine if a tracker is alive
            if tracker_info['failures'] >= self._max_tracker_failures:
                alive = False
            else:
                alive = True
            tracker_info['alive'] = alive

            self._tracker_info_dict[tracker]['updated'] = True

    # ------------------------------------------------------------
    # (Public API)
    # Updates the tracker status into the DB in batch.
    # ------------------------------------------------------------
    def updateTrackerInfoIntoDb(self):
        self._lock.acquire()

        # store all recently updated tracker info into DB
        update_list = list()
        for tracker, info in self._tracker_info_dict.items():
            if not info['updated']:
                continue

            data = (info['last_check'], info['failures'], info['alive'], tracker)
            update_list.append(data)

            info['updated'] = False
        self._lock.release()

        @forceDBThread
        def do_db():
            self._torrentdb.updateTrackerInfo(update_list)

        if update_list:
            do_db()

    # ------------------------------------------------------------
    # Gets the size of the tracker info list.
    # ------------------------------------------------------------
    def getTrackerInfoListSize(self):
        return len(self._tracker_info_dict.keys())

    # ------------------------------------------------------------
    # Gets the a specific tracker info.
    # ------------------------------------------------------------
    def getTrackerInfo(self, index):
        return self._tracker_info_dict.items()[index]
