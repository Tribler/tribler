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
from threading import Lock, Event

from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler

# ============================================================
# This class maintains the tracker infomation cache.
# ============================================================
class TrackerInfoCache(object):

    # ------------------------------------------------------------
    # Initialization.
    # ------------------------------------------------------------
    def __init__(self, max_failures=5, dead_tracker_recheck_interval=60):
        self._torrentdb = TorrentDBHandler.getInstance()
        self._tracker_info_dict = dict()

        self._max_tracker_failures = max_failures
        self._dead_tracker_recheck_Interval = dead_tracker_recheck_interval

        self._lock = Lock()

        self._initial_load_complete_event = Event()

    # ------------------------------------------------------------
    # Destructor.
    # ------------------------------------------------------------
    def __del__(self):
        del self._tracker_info_dict
        del self._lock
        del self._initial_load_complete_event

    # ------------------------------------------------------------
    # Loads and initializes the cache from database.
    # ------------------------------------------------------------
    @forceDBThread
    def loadCacheFromDb(self):
        tracker_info_list = self._torrentdb.getTrackerInfoList()
        # update tracker info
        self._lock.acquire()
        if self._tracker_info_dict:
            for tracker_info in tracker_info_list:
                tracker, alive, last_check, failures = tracker_info
                self._tracker_info_dict[tracker] = dict()
                self._tracker_info_dict[tracker]['last_check'] = last_check
                self._tracker_info_dict[tracker]['failures'] = failures
                self._tracker_info_dict[tracker]['alive'] = alive
            del tracker_info_list
        self._lock.release()

        self._initial_load_complete_event.set()

    # ------------------------------------------------------------
    # Waits for the cache to be initialized.
    # ------------------------------------------------------------
    def waitForCacheInitialization(self, wait_time=30):
        return self._initial_load_complete_event.wait(wait_time)

    # ------------------------------------------------------------
    # Updates the tracker status into the DB.
    # ------------------------------------------------------------
    @forceDBThread
    def _updateTrackerInfoIntoDb(self, tracker, last_check, failures, alive):
        self._torrentdb.updateTrackerInfo(tracker, last_check, failures, alive)

    # ------------------------------------------------------------
    # (Public API)
    # Checks if a tracker is worth checking now.
    # ------------------------------------------------------------
    def toCheckTracker(self, tracker):
        currentTime = int(time.time())

        self._lock.acquire()
        if not tracker in self._tracker_info_dict:
            self._lock.release()
            return True

        alive = self._tracker_info_dict[tracker]['alive']
        if alive:
            self._lock.release()
            return True

        # check the last time we check this 'dead' tracker
        last_check = self._tracker_info_dict[tracker]['last_check']
        interval = currentTime - last_check
        if interval >= self._dead_tracker_recheck_Interval:
            result = True
        else:
            result = False
        self._lock.release()

        return result

    # ------------------------------------------------------------
    # (Public API)
    # Updates or creates a tracker info.
    # ------------------------------------------------------------
    def updateTrackerInfo(self, tracker, success=True):
        currentTime = int(time.time())

        self._lock.acquire()
        # create a new record if doesn't exist
        if not tracker in self._tracker_info_dict:
            self._tracker_info_dict[tracker] = dict()
            self._tracker_info_dict[tracker]['failures'] = 0
            tracker_info = self._tracker_info_dict[tracker]
        else:
            tracker_info = self._tracker_info_dict[tracker]

        tracker_info['last_check'] = currentTime
        # reset the failures count if successful
        if success:
            tracker_info['failures'] = 0
        else:
            tracker_info['failures'] += 1

        # determine if a tracker is alive
        if tracker_info['failures'] >= self._max_tracker_failures:
            alive = 0
        else:
            alive = 1
        tracker_info['alive'] = alive

        # avoid concurrency problem
        last_check = tracker_info['last_check']
        failures   = tracker_info['failures']
        alive      = tracker_info['alive']
        self._lock.release()

        # to avoid the concurrency problem of using the TrackerInfo Dict
        self._updateTrackerInfoIntoDb(tracker, last_check, failures, alive)

    # ========================================
    # Methods for properties.
    # ========================================
    # trackerInfoDict
    @property
    def trackerInfoDict(self):
        return self._tracker_info_dict
    @trackerInfoDict.setter
    def trackerInfoDict(self, tracker_info_dict):
        self._tracker_info_dict = tracker_info_dict
    @trackerInfoDict.deleter
    def trackerInfoDict(self):
        del self._tracker_info_dict
