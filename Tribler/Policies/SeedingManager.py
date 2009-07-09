# Written by Boxun Zhang
# see LICENSE.txt for license information

import sys
import time 
from Tribler.Core.simpledefs import *

DEBUG = False

class GlobalSeedingManager:
    def __init__(self, Read):
        self.seeding_managers = {}
        self.Read = Read
        
    def apply_seeding_policy(self, dslist):
        # Remove stoped seeds
        for infohash, seeding_manager in self.seeding_managers.items():
            if not seeding_manager.ds.get_status() == DLSTATUS_SEEDING:
                del self.seeding_managers[infohash]

        for download_state in dslist:

            if download_state.get_status() == DLSTATUS_SEEDING:
                infohash = download_state.get_download().get_def().get_infohash()
                if infohash in self.seeding_managers:
                    self.seeding_managers[infohash].update_download_state(download_state)

                else:
                    # apply new seeding manager
                    seeding_manager = SeedingManager(download_state)

                    t4t_option = self.Read('t4t_option', "int")
                    if t4t_option == 0:
                        # No Bittorrent leeching, seeding until sharing ratio = 1.0
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: TitForTatRatioBasedSeeding"
                        seeding_manager.set_t4t_policy(TitForTatRatioBasedSeeding())

                    elif t4t_option == 1:
                        # Unlimited seeding
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: UnlimitedSeeding"
                        seeding_manager.set_t4t_policy(UnlimitedSeeding())

                    elif t4t_option == 2:
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: TitForTatTimeBasedSeeding"
                            # Time based seeding
                        seeding_manager.set_t4t_policy(TitForTatTimeBasedSeeding(self.Read))

                    else:
                        # t4t_option == 3, no seeding 
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: NoSeeding"
                        seeding_manager.set_t4t_policy(NoSeeding())

                    g2g_option = self.Read('g2g_option', "int")
                    if g2g_option == 0:
                        # Seeding to peers with large sharing ratio
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: GiveToGetRatioBasedSeeding"
                        seeding_manager.set_g2g_policy(GiveToGetRatioBasedSeeding(self.Read))

                    elif g2g_option == 1:
                        # Boost your reputation
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: UnlimitedSeeding"
                        seeding_manager.set_g2g_policy(UnlimitedSeeding())

                    elif g2g_option == 2:
                        # Seeding for sometime
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: GiveToGetTimeBasedSeeding"
                        seeding_manager.set_g2g_policy(GiveToGetTimeBasedSeeding(self.Read))

                    else:
                        # g2g_option == 3, no seeding
                        if DEBUG: print >>sys.stderr, "GlobalSeedingManager: NoSeeding"
                        seeding_manager.set_g2g_policy(NoSeeding())
                
                    # Apply seeding manager
                    download_state.get_download().set_seeding_policy(seeding_manager)
                    self.seeding_managers[infohash] = seeding_manager
        
        if DEBUG: print >>sys.stderr,"GlobalSeedingManager: current seedings: ", len(self.seeding_managers), "out of", len(dslist), "downloads"

class SeedingManager:
    def __init__(self, download_state):
        self.download_state = download_state
        self.t4t_policy = None
        self.g2g_policy = None
        
        self.t4t_stop = False
        self.g2g_stop = False

    def update_download_state(self, download_state):
        self.download_state = download_state
    
    def is_conn_eligible(self, conn):
        if conn.use_g2g:
            g2g_r = self.g2g_policy.apply(conn, self.download_state)
            self.g2g_stop = g2g_r
            
            # If seeding stop both to g2g and t4t
            # then stop seeding 
            if self.t4t_stop and self.g2g_stop:
                self.download_state.get_download().stop()
                
                if DEBUG:
                     print >>sys.stderr,"Stop seedings: ",self.download_state.get_download().get_dest_files()
            
            return g2g_r
            
        else:
            t4t_r = self.t4t_policy.apply(conn, self.download_state)
            self.t4t_stop = t4t_r
            
            if self.t4t_stop and self.g2g_stop:
                self.download_state.get_download().stop()
                
                if DEBUG:
                     print >>sys.stderr,"Stop seedings: ",self.download_state.get_download().get_dest_files()
            
            return t4t_r
            
    
    def set_t4t_policy(self, policy):
        self.t4t_policy = policy
        
    def set_g2g_policy(self, policy):
        self.g2g_policy = policy

class SeedingPolicy:
    def __init__(self):
        pass
    
    def apply(self, conn, download_state):
        pass
    
class UnlimitedSeeding(SeedingPolicy):
    def __init__(self):
        SeedingPolicy.__init__(self)
    
    def apply(self, conn, download_state):
        return True


class NoSeeding(SeedingPolicy):
    def __init__(self):
        SeedingPolicy.__init__(self)
    
    def apply(self, conn, download_state):
        return False

class TitForTatTimeBasedSeeding(SeedingPolicy):
    def __init__(self, Read):
        SeedingPolicy.__init__(self)
        self.Read = Read
        self.begin = time.time()
    
    def apply(self, conn, download_state):
        seeding_secs = 0
        seeding_secs = long(self.Read('t4t_hours', "int"))*3600 + long(self.Read('t4t_mins', "int"))*60
                            
        if time.time() - self.begin <= seeding_secs:
            return True
        else:
            return False

class GiveToGetTimeBasedSeeding(SeedingPolicy):
    def __init__(self, Read):
        SeedingPolicy.__init__(self)
        self.Read = Read
        self.begin = time.time()
    
    def apply(self, conn, download_state):
        seeding_secs = 0
        seeding_secs = long(self.Read('g2g_hours', "int"))*3600 + long(self.Read('g2g_mins', "int"))*60
                            
        if time.time() - self.begin <= seeding_secs:
            return True
        else:
            return False

    
class TitForTatRatioBasedSeeding(SeedingPolicy):
    def __init__(self):
        SeedingPolicy.__init__(self)
        
    def apply(self, conn, download_state):
        # No Bittorrent leeching
#        ratio = self.download_state.stats['utotal']/self.download_state.stats['dtotal']
        ratio = 0.0
        stats = download_state.stats['stats']
        dl = stats.downTotal
        ul = stats.upTotal

        print >>sys.stderr, "TitForTatRatioBasedSeeding: apply:", dl, ul
        
        if not dl == 0:
            ratio = ul/dl
        
        if ratio <= 1.0:
            return True
        else:
            return False

class GiveToGetRatioBasedSeeding(SeedingPolicy):
    def __init__(self, Read):
        SeedingPolicy.__init__(self)
        self.Read = Read
    
    def apply(self, conn, download_state):
        # Seeding to peers with large sharing ratio
        ratio = 0.0
        
        dl = conn.download.measure.get_total()
        ul = conn.upload.measure.get_total()
        
        if not dl == 0:
            ratio = ul/dl
    
        if ratio <= Read('g2g_ratio', "int")/100.0:
            return False
        else:
            return True

