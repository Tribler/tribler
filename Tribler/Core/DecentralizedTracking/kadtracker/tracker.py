# Copyright (C) 2009 Raul Jimenez, Flutra Osmani
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import time

VALIDITY_PERIOD = 30 * 60 #30 minutes
CLEANUP_COUNTER = 100

class Tracker(object):

    def __init__(self, validity_period=VALIDITY_PERIOD,
                 cleanup_counter=CLEANUP_COUNTER):
        self.tracker_dict = {}
        self.validity_period = validity_period
        self.cleanup_counter = cleanup_counter
        self.put_counter = 0

        
    def _cleanup_list(self, ts_peers):
        '''
        Clean up the list as side effect.
        '''
        oldest_valid_ts = time.time() - self.validity_period
        for i in range(len(ts_peers)):
            if ts_peers[i][0] < oldest_valid_ts:
                del ts_peers[i]
                break
        
    
    def put(self, k, peer):
        #Clean up every n puts
        self.put_counter += 1
        if self.put_counter == self.cleanup_counter:
            self.put_counter = 0
            for k_ in self.tracker_dict.keys():
                ts_peers = self.tracker_dict[k_]
                self._cleanup_list(ts_peers)
                if not ts_peers: #empty list. Delete key
                    del self.tracker_dict[k_]
        
        ts_peers = self.tracker_dict.setdefault(k,[])
        if ts_peers:
            # let's see whether the peer is already there
            for i in range(len(ts_peers)):
                if ts_peers[i] == peer:
                    del ts_peers[i]
                    break
        ts_peers.append((time.time(), peer))

    def get(self, k):
        ts_peers = self.tracker_dict.get(k, [])
        self._cleanup_list(ts_peers)
        return [ts_peer[1] for ts_peer in ts_peers]
                               
    def debug_view(self):
        return self.tracker_dict
            

class TrackerMock(object):

    def get(self, k):
        import test_const
        return test_const.PEERS
