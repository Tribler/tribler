# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import ptime as time
import message

import logging

logger = logging.getLogger('dht')

   
class GetPeersLookup(object):

    def __init__(self, my_id,
                 info_hash, callback_f,
                 bt_port=None):
        pass

    
    def start(self, bootstrap_rnodes):
        queries_to_send = []
        return queries_to_send
        
    def on_response_received(self, response_msg, node_):
        queries_to_send = []
        peers = []
        num_parallel_queries = 0
        lookup_done = True
        return (queries_to_send, peers, num_parallel_queries,
                lookup_done)

    def on_timeout(self, node_):
        queries_to_send = []
        num_parallel_queries = 0
        lookup_done = True        
        return (queries_to_send, num_parallel_queries, lookup_done)
    
    def on_error(self, error_msg, node_): 
        queries_to_send = []
        num_parallel_queries = 0
        lookup_done = True        
        return (queries_to_send, num_parallel_queries, lookup_done)

            
class MaintenanceLookup(GetPeersLookup):

    def __init__(self, my_id, target):
        GetPeersLookup.__init__(self, my_id, target, None)
        self.bootstrap_alpha = 4
        self.normal_alpha = 4
        self.normal_m = 1
        self.slowdown_alpha = 4
        self.slowdown_m = 1
        self._get_peers_msg = message.OutgoingFindNodeQuery(my_id,
                                                            target)
            
        
class LookupManager(object):

    def __init__(self, my_id):
        self.my_id = my_id

    def get_peers(self, info_hash, callback_f, bt_port=None):
        lookup_q = GetPeersLookup(self.my_id, info_hash,
                                  callback_f, bt_port)
        return lookup_q

    def maintenance_lookup(self, target=None):
        target = target or self.my_id
        lookup_q = MaintenanceLookup(self.my_id, target)
        return lookup_q
