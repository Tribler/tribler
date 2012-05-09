# Copyright (C) 2009-2010 Raul Jimenez, Flutra Osmani
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import ptime as time

VALIDITY_PERIOD = 30 * 60 #30 minutes
CLEANUP_COUNTER = 100

MAX_PEERS = 50 # Avoids way too long get_peers respoonses (longer than UDP

#TODO: avoid tracking several ports from the same IP address!

class Tracker(object):

    def __init__(self, validity_period=VALIDITY_PERIOD,
                 cleanup_counter=CLEANUP_COUNTER):
        self._tracker_dict = {}
        self.validity_period = validity_period
        self.cleanup_counter = cleanup_counter
        self._put_counter = 0
        self.num_keys = 0
        self.num_peers = 0
        
    def put(self, k, peer):
        #Clean up every n puts
        self._put_counter += 1
        if self._put_counter == self.cleanup_counter:
            self._put_counter = 0
            for k_ in self._tracker_dict.keys():
                ts_peers = self._tracker_dict[k_]
                self._cleanup_key(k_)
                if not ts_peers: #empty list. Delete key
                    del self._tracker_dict[k_]
                    self.num_keys -= 1
        
        ts_peers = self._tracker_dict.setdefault(k,[])
        if not ts_peers:
            self.num_keys += 1
        else:
            # let's see whether the peer is already there
            for i in range(len(ts_peers)):
                if ts_peers[i][1] == peer:
                    self.num_peers -= 1
                    del ts_peers[i]
                    break
        ts_peers.append((time.time(), peer))
        self.num_peers += 1

    def get(self, k):
        ts_peers = self._tracker_dict.get(k, [])
        self._cleanup_key(k)
        return [ts_peer[1] for ts_peer in ts_peers[-MAX_PEERS:]]

    def _cleanup_key(self, k):
        '''
        Clean up the list as side effect.
        '''
        ts_peers = self._tracker_dict.get(k, None)
        oldest_valid_ts = time.time() - self.validity_period
        while ts_peers and  ts_peers[0][0] < oldest_valid_ts:
            del ts_peers[0]
            self.num_peers -= 1
