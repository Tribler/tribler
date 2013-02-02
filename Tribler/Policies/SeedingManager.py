# Written by Boxun Zhang
# see LICENSE.txt for license information

import binascii
import cPickle
import os
import sys
import time

from Tribler.Core.simpledefs import *
from traceback import print_exc

DEBUG = False

STORAGE_VERSION_ONE = 1
STORAGE_VERSION_CURRENT = STORAGE_VERSION_ONE

class GlobalSeedingManager:
    def __init__(self, Read, storage_dir):
        # directory where all pickled data must be kept
        self.storage_dir = storage_dir

        # seeding managers containing infohash:seeding_manager pairs
        self.seeding_managers = {}

        # information on download progression, is persistent data that can later be used by seeding
        # managers.  infohash:download_statistics pairs
        self.download_statistics = {}

        # callback to read from abc configuration file
        self.Read = Read

        self.prepare_storage()

    def prepare_storage(self):
        if not os.path.exists(self.storage_dir):
            if DEBUG: print >>sys.stderr, "SeedingManager: created storage_dir", self.storage_dir
            os.mkdir(self.storage_dir)

    def write_all_storage(self):
        for infohash, seeding_manager in self.seeding_managers.items():
            self.write_storage(infohash, seeding_manager.get_updated_storage())

        for infohash, download_statistics in self.download_statistics.items():
            self.write_storage(infohash, download_statistics.get_updated_storage())

    def read_storage(self, infohash):
        filename = os.path.join(self.storage_dir, binascii.hexlify(infohash) + ".pickle")
        if os.path.exists(filename):
            if DEBUG: print >>sys.stderr, "SeedingManager: read_storage", filename
            try:
                f = open(filename, "rb")
                storage = cPickle.load(f)
                f.close()
                # Any version upgrading must be done here
    
                if storage["version"] == STORAGE_VERSION_CURRENT:
                    return storage
            except:
                print_exc()

        # return new storage confirming to version
        # STORAGE_VERSION_CURRENT
        return {"version":STORAGE_VERSION_CURRENT,
                "total_up":0L,
                "total_down":0L,
                "time_seeding":0L}

    def write_storage(self, infohash, storage):
        filename = os.path.join(self.storage_dir, binascii.hexlify(infohash) + ".pickle")
        if DEBUG: print >>sys.stderr, "SeedingManager: write_storage", filename
        f = open(filename, "wb")
        cPickle.dump(storage, f)
        f.close()

    def apply_seeding_policy(self, dslist):
        # Remove stoped seeds
        for infohash, seeding_manager in self.seeding_managers.items():
            if not seeding_manager.download_state.get_status() == DLSTATUS_SEEDING:
                if DEBUG: print >>sys.stderr, "SeedingManager: removing seeding manager", infohash.encode("HEX")
                self.write_storage(infohash, seeding_manager.get_updated_storage())
                del self.seeding_managers[infohash]

        for download_state in dslist:
            # Arno, 2012-05-07: ContentDef support
            cdef = download_state.get_download().get_def()
            hash = cdef.get_infohash() if cdef.get_def_type() == 'torrent' else cdef.get_roothash()
            if download_state.get_status() == DLSTATUS_SEEDING:
                if hash in self.seeding_managers:
                    self.seeding_managers[hash].update_download_state(download_state)

                else:
                    # apply new seeding manager
                    if DEBUG: print >>sys.stderr, "SeedingManager: apply seeding manager", hash.encode("HEX")
                    seeding_manager = SeedingManager(download_state, self.read_storage(hash))

                    policy = self.Read('t4t_option', "int") if cdef.get_def_type() == 'torrent' else self.Read('g2g_option', "int")
                    if policy == 0:
                        # No leeching, seeding until sharing ratio is met
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: RatioBasedSeeding"
                        seeding_manager.set_policy(TitForTatRatioBasedSeeding(self.Read) if cdef.get_def_type() == 'torrent' else GiveToGetRatioBasedSeeding(self.Read))

                    elif policy == 1:
                        # Unlimited seeding
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: UnlimitedSeeding"
                        seeding_manager.set_policy(UnlimitedSeeding())

                    elif policy == 2:
                        # Time based seeding
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: TimeBasedSeeding"
                        seeding_manager.set_policy(TitForTatTimeBasedSeeding(self.Read) if cdef.get_def_type() == 'torrent' else GiveToGetTimeBasedSeeding(self.Read))

                    else:
                        # No seeding
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: NoSeeding"
                        seeding_manager.set_policy(NoSeeding())
                        
                    # Apply seeding manager
                    self.seeding_managers[hash] = seeding_manager
                            
            else:
                if DEBUG: print >>sys.stderr, "SeedingManager: updating download statistics (for future use)", hash.encode("HEX")
                if hash in self.download_statistics:
                    self.download_statistics[hash].update_download_state(download_state)
                else:
                    self.download_statistics[hash] = DownloadStatistics(download_state, self.read_storage(hash))

        # if DEBUG: print >>sys.stderr,"GlobalSeedingManager: current seedings: ", len(self.seeding_managers), "out of", len(dslist), "downloads"

class DownloadStatistics:
    def __init__(self, download_state, storage):
        self.storage = storage
        self.download_state = download_state
        self.time_start = time.time()

    def get_updated_storage(self):
        """
        Returns a new storage object that is updated with the last
        information from the download_state
        """
        return {"version":STORAGE_VERSION_ONE,
                "total_up":self.storage["total_up"] + self.download_state.get_total_transferred(UPLOAD),
                "total_down":self.storage["total_down"] + self.download_state.get_total_transferred(DOWNLOAD),
                "time_seeding":self.storage["time_seeding"] + time.time() - self.time_start}

    def update_download_state(self, download_state):
        self.download_state = download_state
        self.download_state.set_seeding_statistics(self.get_updated_storage())

class SeedingManager:
    def __init__(self, download_state, storage):
        self.storage = storage
        self.download_state = download_state
        self.policy = None
        self.time_start = time.time()

    def get_updated_storage(self):
        """
        Returns a new storage object that is updated with the last
        information from the download_state
        """
        return {"version":STORAGE_VERSION_ONE,
                "total_up":self.storage["total_up"] + self.download_state.get_total_transferred(UPLOAD),
                "total_down":self.storage["total_down"] + self.download_state.get_total_transferred(DOWNLOAD),
                "time_seeding":self.storage["time_seeding"] + time.time() - self.time_start}

    def update_download_state(self, download_state):
        self.download_state = download_state
        self.download_state.set_seeding_statistics(self.get_updated_storage())
        
        download = self.download_state.get_download()
        if download.get_def().get_def_type() == 'torrent':
            if not self.policy.apply(None, self.download_state, self.storage):
                if DEBUG: print >>sys.stderr,"Stop seeding: ",self.download_state.get_download().get_dest_files()
                self.download_state.get_download().stop()
        # No swift, for now
        
    def set_policy(self, policy):
        self.policy = policy

class SeedingPolicy:
    def __init__(self):
        pass

    def apply(self, _, __, ___):
        pass

class UnlimitedSeeding(SeedingPolicy):
    def __init__(self):
        SeedingPolicy.__init__(self)

    def apply(self, _, __, ___):
        return True


class NoSeeding(SeedingPolicy):
    def __init__(self):
        SeedingPolicy.__init__(self)

    def apply(self, _, __, ___):
        return False

class TitForTatTimeBasedSeeding(SeedingPolicy):
    def __init__(self, Read):
        SeedingPolicy.__init__(self)
        self.Read = Read
        self.begin = time.time()

    def apply(self, _, __, storage):
        current = storage["time_seeding"] + time.time() - self.begin
        limit = long(self.Read('t4t_hours', "int"))*3600 + long(self.Read('t4t_mins', "int"))*60
        if DEBUG: print >>sys.stderr, "TitForTatTimeBasedSeeding: apply:", current, "/", limit
        return current <= limit

class GiveToGetTimeBasedSeeding(SeedingPolicy):
    def __init__(self, Read):
        SeedingPolicy.__init__(self)
        self.Read = Read
        self.begin = time.time()

    def apply(self, _, __, storage):
        current = storage["time_seeding"] + time.time() - self.begin
        limit = long(self.Read('g2g_hours', "int"))*3600 + long(self.Read('g2g_mins', "int"))*60
        if DEBUG: print >>sys.stderr, "GiveToGetTimeBasedSeeding: apply:", current, "/", limit
        return current <= limit

class TitForTatRatioBasedSeeding(SeedingPolicy):
    def __init__(self, Read):
        SeedingPolicy.__init__(self)
        self.Read = Read

    def apply(self, _, download_state, storage):
        # No Bittorrent leeching (minimal ratio of 1.0)
        ul = storage["total_up"] + download_state.get_total_transferred(UPLOAD)

        # 03/01/2011 boudewijn: if the ratio used the number of bytes
        # that were downloaded up till now, it would result is chokes
        # when still downloading.  This can severely reduce download
        # speed aswell.
        # dl = storage["total_down"] + download_state.get_total_transferred(DOWNLOAD)
        dl = download_state.get_download().get_def().get_length()

        if dl == 0L:
            # no download will result in no-upload to anyone
            ratio = 1.0
        else:
            ratio = 1.0*ul/dl

        if DEBUG: print >>sys.stderr, "TitForTatRatioBasedSeeding: apply:", dl, ul, ratio

        return ratio < self.Read('t4t_ratio', "int")/100.0

class GiveToGetRatioBasedSeeding(SeedingPolicy):
    def __init__(self, Read):
        SeedingPolicy.__init__(self)
        self.Read = Read

    def apply(self, conn, _, __):
        # Seeding to peers with large sharing ratio
        dl = conn.download.measure.get_total()
        ul = conn.upload.measure.get_total()

        if dl == 0L:
            # no download will result in no-upload to anyone
            ratio = 1.0
        else:
            ratio = 1.0*ul/dl

        if True or DEBUG: print >>sys.stderr, "GiveToGetRatioBasedSeedingapply:", dl, ul, ratio, self.Read('g2g_ratio', "int")/100.0
        return ratio < self.Read('g2g_ratio', "int")/100.0

