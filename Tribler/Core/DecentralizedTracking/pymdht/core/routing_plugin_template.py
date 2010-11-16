# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import ptime as time
import logging
import test_const as tc

logger = logging.getLogger('dht')


class RoutingManager(object):
    
    def __init__(self, my_node, bootstrap_nodes):
        self.my_node = my_node
        #Copy the bootstrap list
        self.bootstrap_nodes = iter(bootstrap_nodes)
        
    def do_maintenance(self):
        maintenance_delay = 2
        queries_to_send = []
        maintenance_lookup_target = None
        return (maintenance_delay, queries_to_send,
                maintenance_lookup_target)
        
    def on_query_received(self, node_):
        '''
        Return None when nothing to do
        Return a list of queries when queries need to be sent (the queries
        will be sent out by the caller)
        '''
        queries_to_send = []
        return queries_to_send
            
    def on_response_received(self, node_, rtt, nodes):
        queries_to_send = []
        return queries_to_send
        
    def on_error_received(self, node_):
        queries_to_send = []
        return queries_to_send
    
    def on_timeout(self, node_):
        queries_to_send = []
        return queries_to_send
            
    def get_closest_rnodes(self, log_distance, num_nodes, exclude_myself):
        return tc.NODES[:min(len(tc.NODES), num_nodes)]

    def get_main_rnodes(self):
        return tc.NODES

    def print_stats(self):
        pass
