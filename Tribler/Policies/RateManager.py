# Written by Arno Bakker and ABC authors
# see LICENSE.txt for license information

import logging
from sets import Set
from threading import RLock

from Tribler.Core.simpledefs import (UPLOAD, DOWNLOAD, DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_WAITING4HASHCHECK,
                                     DLSTATUS_HASHCHECKING, DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED,
                                     DLSTATUS_STOPPED_ON_ERROR)
from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr


class RateManager(object):

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.lock = RLock()
        self.statusmap = {}
        self.currenttotal = {}
        self.dset = Set()
        self.clear_downloadstates()

    def add_downloadstate(self, ds):
        """ Returns the number of unique states currently stored """
        self._logger.debug("RateManager: add_downloadstate %s", repr(ds.get_download().get_def().get_roothash()))

        self.lock.acquire()
        try:
            d = ds.get_download()
            if d not in self.dset:
                self.statusmap[ds.get_status()].append(ds)
                for dir in [UPLOAD, DOWNLOAD]:
                    self.currenttotal[dir] += ds.get_current_speed(dir)
                self.dset.add(d)
            return len(self.dset)
        finally:
            self.lock.release()

    def add_downloadstatelist(self, download_state):
        self.add_downloadstate(download_state)

    def adjust_speeds(self):
        """ Adjust speeds for the specified set of downloads and clears the set """
        self.lock.acquire()
        try:
            self.calc_and_set_speed_limits(DOWNLOAD)
            self.calc_and_set_speed_limits(UPLOAD)
            self.clear_downloadstates()
        finally:
            self.lock.release()

    def clear_downloadstates(self):
        self.statusmap[DLSTATUS_ALLOCATING_DISKSPACE] = []
        self.statusmap[DLSTATUS_WAITING4HASHCHECK] = []
        self.statusmap[DLSTATUS_HASHCHECKING] = []
        self.statusmap[DLSTATUS_DOWNLOADING] = []
        self.statusmap[DLSTATUS_SEEDING] = []
        self.statusmap[DLSTATUS_STOPPED] = []
        self.statusmap[DLSTATUS_STOPPED_ON_ERROR] = []
        for dir in [UPLOAD, DOWNLOAD]:
            self.currenttotal[dir] = 0
        self.dset.clear()

    #
    # Internal methods
    #
    #
    # The following methods are all called with the lock held
    #

    def calc_and_set_speed_limits(self, direct):
        """ Override this method to write you own speed management policy. """
        pass


class UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager(RateManager):

    """ This class implements a simple rate management policy that:
    1. If the API user set a desired speed for a particular download,
       the speed limit for this download is set to the desired value.
    2. For all torrents for which no desired speeds have been set,
       the global limit is equally divided amongst all downloads.
       (however small the piece of the pie may be).
    3. There are separate global limits for download speed, upload speed
       and upload speed when all torrents are seeding.
    """

    def __init__(self):
        RateManager.__init__(self)
        self.global_max_speed = {UPLOAD: 0.0, DOWNLOAD: 0.0}
        self.ltmgr = None

    def set_global_max_speed(self, direct, speed):
        self.lock.acquire()
        self.global_max_speed[direct] = speed
        self.lock.release()

    def calc_and_set_speed_limits(self, dir=UPLOAD):
        self._logger.debug("RateManager: calc_and_set_speed_limits %s", dir)

        if dir == UPLOAD:
            workingset = self.statusmap[DLSTATUS_DOWNLOADING] + self.statusmap[DLSTATUS_SEEDING]
        else:
            workingset = self.statusmap[DLSTATUS_DOWNLOADING]

        self._logger.debug("RateManager: calc_and_set_speed_limits: len workingset %s", len(workingset))

        # Limit working set to active torrents with connections:
        newws = []
        for ds in workingset:
            if ds.get_num_peers() > 0:
                newws.append(ds)
        workingset = newws

        self._logger.debug("RateManager: calc_and_set_speed_limits: len active workingset %s", len(workingset))

        # No active file, not need to calculate
        if not workingset:
            return

        globalmaxspeed = self.get_global_max_speed(dir)
        # See if global speed settings are set to unlimited
        if globalmaxspeed == 0:
            # Unlimited speed
            for ds in workingset:
                d = ds.get_download()
                d.set_max_speed(dir, d.get_max_desired_speed(dir))

        else:
            self._logger.debug("RateManager: calc_and_set_speed_limits: globalmaxspeed is %s %s", globalmaxspeed, dir)

            # User set priority is always granted, ignoring global limit
            todoset = []
            for ds in workingset:
                d = ds.get_download()
                maxdesiredspeed = d.get_max_desired_speed(dir)
                if maxdesiredspeed > 0.0:
                    d.set_max_speed(dir, maxdesiredspeed)
                else:
                    todoset.append(ds)

            if len(todoset) > 0:
                # Rest divides globalmaxspeed equally
                localmaxspeed = globalmaxspeed / float(len(todoset)) if globalmaxspeed > 0 else 0.00001
                # if too small than user's problem

                self._logger.debug("RateManager: calc_and_set_speed_limits: localmaxspeed is %s %s", localmaxspeed, dir)

                for ds in todoset:
                    d = ds.get_download()
                    d.set_max_speed(dir, localmaxspeed)

        if self.ltmgr is None and LibtorrentMgr.hasInstance():
            self.ltmgr = LibtorrentMgr.getInstance()

        if self.ltmgr:
            rate = self.global_max_speed[dir]  # unlimited == 0, stop == -1, else rate in kbytes
            libtorrent_rate = -1 if rate == 0 else (1 if rate == -1 else rate * 1024)
            if dir == UPLOAD:
                self.ltmgr.set_upload_rate_limit(libtorrent_rate)
            else:
                self.ltmgr.set_download_rate_limit(libtorrent_rate)

    def get_global_max_speed(self, dir=UPLOAD):
        return self.global_max_speed[dir]


class UserDefinedMaxAlwaysOtherwiseDividedOnDemandRateManager(UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager):

    """ This class implements a simple rate management policy that:
    1. If the API user set a desired speed for a particular download,
       the speed limit for this download is set to the desired value.
    2. For all torrents for which no desired speeds have been set,
       the global limit is divided on demand amongst all downloads.
    3. There are separate global limits for download speed, upload speed
       and upload speed when all torrents are seeding.

    TODO: if vod: give all of global limit? Do this at higher level: stop
    all dls when going to VOD
    """

    def __init__(self):
        UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager.__init__(self)

        self.ROOM = 5.0  # the amount of room in speed underutilizing downloads get

    def calc_and_set_speed_limits(self, dir=UPLOAD):
        self._logger.debug("RateManager: calc_and_set_speed_limits %s", dir)

        if dir == UPLOAD:
            workingset = self.statusmap[DLSTATUS_DOWNLOADING] + self.statusmap[DLSTATUS_SEEDING]
        else:
            workingset = self.statusmap[DLSTATUS_DOWNLOADING]

        self._logger.debug("RateManager: calc_and_set_speed_limits: len workingset %s", len(workingset))

        # Limit working set to active torrents with connections:
        newws = []
        for ds in workingset:
            if ds.get_num_peers() > 0:
                newws.append(ds)
        workingset = newws

        self._logger.debug("RateManager: calc_and_set_speed_limits: len new workingset %s", len(workingset))
        for ds in workingset:
            d = ds.get_download()
            self._logger.debug("RateManager: calc_and_set_speed_limits: working is %s", d.get_def().get_name())

        # No active file, not need to calculate
        if not workingset:
            return

        globalmaxspeed = self.get_global_max_speed(dir)
        # See if global speed settings are set to unlimited
        if globalmaxspeed == 0:
            # Unlimited speed
            for ds in workingset:
                d = ds.get_download()
                d.set_max_speed(dir, d.get_max_desired_speed(dir))

        else:
            self._logger.debug("RateManager: calc_and_set_speed_limits: globalmaxspeed is %s %s", globalmaxspeed, dir)

            # User set priority is always granted, ignoring global limit
            todoset = []
            for ds in workingset:
                d = ds.get_download()
                maxdesiredspeed = d.get_max_desired_speed(dir)
                if maxdesiredspeed > 0.0:
                    d.set_max_speed(dir, maxdesiredspeed)
                else:
                    todoset.append(ds)

            if len(todoset) > 0:
                # Rest divides globalmaxspeed based on their demand
                localmaxspeed = globalmaxspeed / float(len(todoset)) if globalmaxspeed > 0 else 0.00001
                # if too small than user's problem

                self._logger.debug("RateManager: calc_and_set_speed_limits: localmaxspeed is %s %s", localmaxspeed, dir)

                # See if underutilizers and overutilizers. If not, just divide equally
                downloadsatmax = False
                downloadsunderutil = False
                for ds in todoset:
                    d = ds.get_download()
                    currspeed = ds.get_current_speed(dir)
                    currmaxspeed = d.get_max_speed(dir)

                    newmaxspeed = currspeed + self.ROOM
                    if currspeed >= (currmaxspeed - 3.0):  # dl needs more
                        downloadsatmax = True
                    elif newmaxspeed < localmaxspeed:  # dl got quota to spare
                        downloadsunderutil = True

                if downloadsatmax and downloadsunderutil:
                    totalunused = 0.0
                    todoset2 = []
                    for ds in todoset:
                        d = ds.get_download()
                        currspeed = ds.get_current_speed(dir)

                        newmaxspeed = currspeed + self.ROOM
                        if newmaxspeed < localmaxspeed:
                            # If unterutilizing:
                            totalunused += (localmaxspeed - newmaxspeed)
                            # Give current speed + 5.0 KB/s extra so it can grow
                            self._logger.info(
                                "RateManager: calc_and_set_speed_limits: Underutil set to %s", newmaxspeed)
                            d.set_max_speed(dir, newmaxspeed)
                        else:
                            todoset2.append(ds)

                    # Divide the unused bandwidth equally amongst others
                    if len(todoset2) > 0:
                        pie = float(len(todoset2)) * localmaxspeed + totalunused
                        piece = pie / float(len(todoset2))
                        for ds in todoset:
                            d = ds.get_download()
                            self._logger.info("RateManager: calc_and_set_speed_limits: Overutil set to %s", piece)
                            d.set_max_speed(dir, piece)
                    else:
                        # what the f? No overutilizers now?
                        self._logger.info(
                            "UserDefinedMaxAlwaysOtherwiseDividedOnDemandRateManager: "
                            "Internal error: No overutilizers anymore?")
                else:
                    # No over and under utilizers, just divide equally
                    for ds in todoset:
                        d = ds.get_download()
                        self._logger.info("RateManager: calc_and_set_speed_limits: Normal set to %s", piece)
                        d.set_max_speed(dir, localmaxspeed)

        if self.ltmgr is None and LibtorrentMgr.hasInstance():
            self.ltmgr = LibtorrentMgr.getInstance()

        if self.ltmgr:
            rate = self.global_max_speed[dir]  # unlimited == 0, stop == -1, else rate in kbytes
            libtorrent_rate = -1 if rate == 0 else (1 if rate == -1 else rate * 1024)
            if dir == UPLOAD:
                self.ltmgr.set_upload_rate_limit(libtorrent_rate)
            else:
                self.ltmgr.set_download_rate_limit(libtorrent_rate)


class UserDefinedMaxAlwaysOtherwiseDividedOverActiveSwarmsRateManager(UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager):

    """ This class implements a simple rate management policy that:
    1. If the API user set a desired speed for a particular download,
       the speed limit for this download is set to the desired value.
    2. For all torrents for which no desired speeds have been set,
       the global limit is divided amongst all downloads that have peers.
       Torrents without user-prefs or peers get a max equal to the global max.
       They'll get throttled again to an equal share in the next iteration
       after peers connect.
    3. There are separate global limits for download speed, upload speed
       and upload speed when all torrents are seeding.
    """

    def __init__(self):
        UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager.__init__(self)

        self.ROOM = 5.0  # the amount of room in speed underutilizing downloads get

    def calc_and_set_speed_limits(self, dir=UPLOAD):
        self._logger.debug("RateManager: calc_and_set_speed_limits %s", dir)

        if dir == UPLOAD:
            workingset = self.statusmap[DLSTATUS_DOWNLOADING] + self.statusmap[DLSTATUS_SEEDING]
        else:
            workingset = self.statusmap[DLSTATUS_DOWNLOADING]

        self._logger.debug("RateManager: set_lim: len workingset %s", len(workingset))

        # Limit working set to active torrents with connections:
        newws = []
        inactiveset = []
        for ds in workingset:
            # Arno, 2010-09-16: Don't count any HTTP seeders as leechers.
            if ds.get_num_nonseeds() > 0:
                newws.append(ds)
            else:
                inactiveset.append(ds)
        workingset = newws

        self._logger.debug("RateManager: set_lim: len new workingset %s", len(workingset))
        for ds in workingset:
            d = ds.get_download()
            self._logger.debug("RateManager: set_lim: working is %s", d.get_def().get_name())

        globalmaxspeed = self.get_global_max_speed(dir)

        # TEST globalmaxspeed = 1.0
        self._logger.debug("RateManager: set_lim: globalmaxspeed is %s %s", globalmaxspeed, dir)

        # See if global speed settings are set to unlimited
        if globalmaxspeed == 0:
            # Unlimited speed
            for ds in workingset:
                d = ds.get_download()
                d.set_max_speed(dir, d.get_max_desired_speed(dir))
            for ds in inactiveset:
                d = ds.get_download()
                d.set_max_speed(dir, d.get_max_desired_speed(dir))  # 0 is default

        else:
            self._logger.debug("RateManager: set_lim: globalmaxspeed is %s %s", globalmaxspeed, dir)

            # User set priority is always granted, ignoring global limit
            todoset = []
            for ds in workingset:
                d = ds.get_download()
                maxdesiredspeed = d.get_max_desired_speed(dir)
                if maxdesiredspeed > 0.0:
                    d.set_max_speed(dir, maxdesiredspeed)
                else:
                    todoset.append(ds)

            if len(todoset) > 0:
                # Rest divides globalmaxspeed based on their demand
                localmaxspeed = globalmaxspeed / float(len(todoset)) if globalmaxspeed > 0 else 0.00001
                # if too small than user's problem

                self._logger.debug("RateManager: set_lim: localmaxspeed is %s %s", localmaxspeed, dir)

                for ds in todoset:
                    d = ds.get_download()
                    self._logger.debug("RateManager: set_lim: %s WorkQ %s", d.get_def().get_name(), localmaxspeed)
                    d.set_max_speed(dir, localmaxspeed)

            # For inactives set limit to user desired, with max of globalmaxspeed
            # or to globalmaxspeed. This way the peers have a limit already set
            # when the first peers arrive. The height of the limit will be corrected
            # here a few seconds later (see BaseApp ratelimiter).
            #
            for ds in inactiveset:
                d = ds.get_download()
                desspeed = d.get_max_desired_speed(dir)
                if desspeed == 0:
                    setspeed = globalmaxspeed
                else:
                    setspeed = min(desspeed, globalmaxspeed)
                self._logger.debug("RateManager: set_lim: %s InactQ %s", d.get_def().get_name(), setspeed)
                d.set_max_speed(dir, setspeed)

        if self.ltmgr is None and LibtorrentMgr.hasInstance():
            self.ltmgr = LibtorrentMgr.getInstance()

        if self.ltmgr:
            rate = self.global_max_speed[dir]  # unlimited == 0, stop == -1, else rate in kbytes
            libtorrent_rate = -1 if rate == 0 else (1 if rate == -1 else rate * 1024)
            if dir == UPLOAD:
                self.ltmgr.set_upload_rate_limit(libtorrent_rate)
            else:
                self.ltmgr.set_download_rate_limit(libtorrent_rate)
