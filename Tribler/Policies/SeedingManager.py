# Written by Boxun Zhang
# see LICENSE.txt for license information

import binascii
import cPickle
import os
import sys
import time 

from Tribler.Core.simpledefs import *

DEBUG = False

STORAGE_VERSION_ONE = 1
STORAGE_VERSION_CURRENT = STORAGE_VERSION_ONE

class GlobalSeedingManager:
    def __init__(self, Read, storage_dir):
        # directory where all pickled data must be kept
        self.storage_dir = storage_dir

        # seeding managers containing infohash:seeding_manager pairs
        self.seeding_managers = {}

        # callback to read from abc configuration file
        self.Read = Read

        self.prepare_storage()

    def prepare_storage(self):
        if not os.path.exists(self.storage_dir):
            if DEBUG: print >>sys.stderr, "SeedingManager: created storage_dir", self.storage_dir
            os.mkdir(self.storage_dir)

    def write_all_storage(self):
        for infohash, seeding_manager in self.seeding_managers.iteritems():
            self.write_storage(infohash, seeding_manager.get_updated_storage())

    def read_storage(self, infohash):
        filename = os.path.join(self.storage_dir, binascii.hexlify(infohash) + ".pickle")
        if os.path.exists(filename):
            if DEBUG: print >>sys.stderr, "SeedingManager: read_storage", filename
            storage = cPickle.load(open(filename, "rb"))
            # Any version upgrading must be done here

            if storage["version"] == STORAGE_VERSION_CURRENT:
                return storage

        # return new storage confirming to version
        # STORAGE_VERSION_CURRENT
        return {"version":STORAGE_VERSION_CURRENT,
                "total_up":0L,
                "total_down":0L,
                "time_seeding":0L}

    def write_storage(self, infohash, storage):
        filename = os.path.join(self.storage_dir, binascii.hexlify(infohash) + ".pickle")
        if DEBUG: print >>sys.stderr, "SeedingManager: write_storage", filename
        cPickle.dump(storage, open(filename, "wb"))
    
    def apply_seeding_policy(self, dslist):
        # Remove stoped seeds
        for infohash, seeding_manager in self.seeding_managers.items():
            if not seeding_manager.download_state.get_status() == DLSTATUS_SEEDING:
                self.write_storage(infohash, seeding_manager.get_updated_storage())
                del self.seeding_managers[infohash]

        for download_state in dslist:

            if download_state.get_status() == DLSTATUS_SEEDING:
                infohash = download_state.get_download().get_def().get_infohash()
                if infohash in self.seeding_managers:
                    self.seeding_managers[infohash].update_download_state(download_state)

                else:
                    # apply new seeding manager
                    seeding_manager = SeedingManager(download_state, self.read_storage(infohash))

                    t4t_option = self.Read('t4t_option', "int")
                    if t4t_option == 0:
                        # No Bittorrent leeching, seeding until sharing ratio = 1.0
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: TitForTatRatioBasedSeeding"
                        seeding_manager.set_t4t_policy(TitForTatRatioBasedSeeding())

                    elif t4t_option == 1:
                        # Unlimited seeding
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: UnlimitedSeeding (for t4t)"
                        seeding_manager.set_t4t_policy(UnlimitedSeeding())

                    elif t4t_option == 2:
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: TitForTatTimeBasedSeeding"
                            # Time based seeding
                        seeding_manager.set_t4t_policy(TitForTatTimeBasedSeeding(self.Read))

                    else:
                        # t4t_option == 3, no seeding 
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: NoSeeding (for t4t)"
                        seeding_manager.set_t4t_policy(NoSeeding())

                    g2g_option = self.Read('g2g_option', "int")
                    if g2g_option == 0:
                        # Seeding to peers with large sharing ratio
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: GiveToGetRatioBasedSeeding"
                        seeding_manager.set_g2g_policy(GiveToGetRatioBasedSeeding(self.Read))

                    elif g2g_option == 1:
                        # Boost your reputation
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: UnlimitedSeeding (for g2g)"
                        seeding_manager.set_g2g_policy(UnlimitedSeeding())

                    elif g2g_option == 2:
                        # Seeding for sometime
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: GiveToGetTimeBasedSeeding"
                        seeding_manager.set_g2g_policy(GiveToGetTimeBasedSeeding(self.Read))

                    else:
                        # g2g_option == 3, no seeding
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: NoSeeding (for g2g)"
                        seeding_manager.set_g2g_policy(NoSeeding())
                
                    # Apply seeding manager
                    download_state.get_download().set_seeding_policy(seeding_manager)
                    self.seeding_managers[infohash] = seeding_manager
        
        # if DEBUG: print >>sys.stderr,"GlobalSeedingManager: current seedings: ", len(self.seeding_managers), "out of", len(dslist), "downloads"

class SeedingManager:
    def __init__(self, download_state, storage):
        self.storage = storage
        self.download_state = download_state
        self.t4t_policy = None
        self.g2g_policy = None
        
        self.t4t_eligible = True
        self.g2g_eligible = True

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
    
    def is_conn_eligible(self, conn):
        if conn.use_g2g:
            self.g2g_eligible = self.g2g_policy.apply(conn, self.download_state, self.storage)
            if DEBUG:
                if self.g2g_eligible:
                    print >>sys.stderr,"AllowSeeding to g2g peer: ",self.download_state.get_download().get_dest_files()
                else:
                    print >>sys.stderr,"DenySeeding to g2g peer: ",self.download_state.get_download().get_dest_files()

            # stop download when neither t4t_eligible nor g2g_eligible
            if not (self.t4t_eligible or self.g2g_eligible):
                if DEBUG: print >>sys.stderr,"Stop seedings: ",self.download_state.get_download().get_dest_files()
                self.download_state.get_download().stop()
            
            return self.g2g_eligible
            
        else:
            self.t4t_eligible = self.t4t_policy.apply(conn, self.download_state, self.storage)
            
            if DEBUG:
                if self.t4t_eligible:
                    print >>sys.stderr,"AllowSeeding to t4t peer: ",self.download_state.get_download().get_dest_files()
                else:
                    print >>sys.stderr,"DenySeeding to t4t peer: ",self.download_state.get_download().get_dest_files()
            # stop download when neither t4t_eligible nor g2g_eligible
            if not (self.t4t_eligible or self.g2g_eligible):
                if DEBUG: print >>sys.stderr,"Stop seedings: ",self.download_state.get_download().get_dest_files()
                self.download_state.get_download().stop()
            
            return self.t4t_eligible
            
    
    def set_t4t_policy(self, policy):
        self.t4t_policy = policy
        
    def set_g2g_policy(self, policy):
        self.g2g_policy = policy

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
    def __init__(self):
        SeedingPolicy.__init__(self)
        
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

        return ratio < 1.0

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
    
        if DEBUG: print >>sys.stderr, "GiveToGetRatioBasedSeedingapply:", dl, ul, ratio, self.Read('g2g_ratio', "int")/100.0
        return ratio < self.Read('g2g_ratio', "int")/100.0

