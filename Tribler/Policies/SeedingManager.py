# Written by Boxun Zhang
# see LICENSE.txt for license information

import sys
import time 
from Tribler.Core.simpledefs import *

DEBUG = False

class GlobalSeedingManager:
    def __init__(self, Read):
        self.curr_seedings = []
        self.info_hashes = []
        self.Read = Read
        
    def apply_seeding_policy(self, dslist):
        # Remove stoped seeds
        for curr in self.curr_seedings:
            if not curr.get_status() == DLSTATUS_SEEDING:
                self.info_hahes.remove(curr.get_def().get_infohash())
                self.curr_seedings.remove(curr)
        
        if DEBUG:
            print >>sys.stderr,"GlobalSeedingManager: current seedings: ",len(self.curr_seedings)
        
        for ds in dslist:
            if ds.get_status() == DLSTATUS_SEEDING and ds.get_download().get_def().get_infohash() not in self.info_hashes:
                # apply new seeding manager
                seeding_manager = SeedingManager(ds)
# t4t option_
                t4t_option = self.Read('t4t_option', "int")
            
                if t4t_option == 0:
                    # No Bittorrent bleeching, seeding until sharing ratio = 1.0
                    seeding_manager.set_t4t_policy(TitForTatRatioBasedSeeding(ds))
                elif t4t_option == 1:
                    # Unlimited seeding
                    seeding_manager.set_t4t_policy(UnlimitedSeeding())
                elif t4t_option == 2:
                     # Time based seeding
                    seeding_manager.set_t4t_policy(TitForTatTimeBasedSeeding(self.Read))
                else:
                    # t4t_option == 3, no seeding 
                    seeding_manager.set_t4t_policy(NoSeeding())
# _t4t option

# g2g option_
                g2g_option = self.Read('g2g_option', "int")
                
                if g2g_option == 0:
                    # Seeding to peers with large sharing ratio
                    seeding_manager.set_g2g_policy(GiveToGetRatioBasedSeeding(self.Read, ds))
                elif g2g_option == 1:
                    # Boost your reputation
                    seeding_manager.set_g2g_policy(UnlimitedSeeding())
                elif g2g_option == 2:
                    # Seeding for sometime
                    seeding_manager.set_g2g_policy(GiveToGetTimeBasedSeeding(self.Read))
                else:
                    # g2g_option == 3, no seeding
                    seeding_manager.set_g2g_policy(NoSeeding())
# _g2g option
                
                # Apply seeding manager
                ds.get_download().set_seeding_policy(seeding_manager)
                
                self.curr_seedings.append(ds)
                self.info_hashes.append(ds.get_download().get_def().get_infohash())
        

class SeedingManager:
    def __init__(self, ds):
        self.ds = ds
        self.t4t_policy = None
        self.g2g_policy = None
        
        self.t4t_stop = False
        self.g2g_stop = False
    
    def is_conn_eligible(self, conn):
        if conn.use_g2g:
            g2g_r = self.g2g_policy.apply(conn)
            self.g2g_stop = g2g_r
            
            # If seeding stop both to g2g and t4t
            # then stop seeding 
            if self.t4t_stop and self.g2g_stop:
                self.ds.get_download().stop()
                
                if DEBUG:
                     print >>sys.stderr,"Stop seedings: ",self.ds.get_download().get_dest_files()
            
            return g2g_r
            
        else:
            t4t_r = self.t4t_policy.apply(conn)
            self.t4t_stop = t4t_r
            
            if self.t4t_stop and self.g2g_stop:
                self.ds.get_download().stop()
                
                if DEBUG:
                     print >>sys.stderr,"Stop seedings: ",self.ds.get_download().get_dest_files()
            
            
            return t4t_r
            
    
    def set_t4t_policy(self, policy):
        self.t4t_policy = policy
        
    def set_g2g_policy(self, policy):
        self.g2g_policy = policy

class SeedingPolicy:
    def __init__(self):
        pass
    
    def apply(self, conn):
        pass
    
class UnlimitedSeeding(SeedingPolicy):
    def __init__(self):
        SeedingPolicy.__init__(self)
    
    def apply(self, conn):
        return True


class NoSeeding(SeedingPolicy):
    def __init__(self):
        SeedingPolicy.__init__(self)
    
    def apply(self, conn):
        return False

class TitForTatTimeBasedSeeding(SeedingPolicy):
    def __init__(self, Read):
        SeedingPolicy.__init__(self)
        self.Read = Read
        self.begin = time.time()
    
    def apply(self, conn):
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
    
    def apply(self, conn):
        seeding_secs = 0
        seeding_secs = long(self.Read('g2g_hours', "int"))*3600 + long(self.Read('g2g_mins', "int"))*60
                            
        if time.time() - self.begin <= seeding_secs:
            return True
        else:
            return False

    
class TitForTatRatioBasedSeeding(SeedingPolicy):
    def __init__(self, ds):
        SeedingPolicy.__init__(self)
        self.ds = ds
        
    def apply(self, conn):
        # No Bittorrent leeching
#        ratio = self.ds.stats['utotal']/self.ds.stats['dtotal']
        ratio = 0.0
        stats = self.ds.stats['stats']
        dl = stats.downTotal
        ul = stats.upTotal
        
        if not dl == 0:
            ratio = ul/dl
        
        if ratio <= 1.0:
            return True
        else:
            return False

class GiveToGetRatioBasedSeeding(SeedingPolicy):
    def __init__(self, Read, ds):
        SeedingPolicy.__init__(self)
        self.Read = Read
        self.ds = ds
    
    def apply(self, conn):
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

