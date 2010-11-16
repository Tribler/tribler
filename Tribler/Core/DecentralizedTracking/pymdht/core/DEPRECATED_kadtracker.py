# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

"""
This module is the API for the whole package.

You can use the KadTracker class and its methods to interact with
the DHT.

Find usage examples in server_dht.py and interactive_dht.py.

If you want to generate logs. You will have to setup logging_conf
BEFORE importing this module. See the examples above for details.

"""
import time

import controller
import logging, logging_conf

class KadTracker:
    """KadTracker is the interface for the whole package.

    Setting up the DHT is as simple as creating this object.
    The parameters are:
    - dht_addr: a tuple containing IP address and port number.
    - logs_path: a string containing the path to the log files.

    """
    def __init__(self, dht_addr, conf_path,
                 routing_m_mod, lookup_m_mod):
        logging_conf.setup(conf_path, logging.DEBUG)
        self.controller = controller.Controller(dht_addr, conf_path,
                                                routing_m_mod,
                                                lookup_m_mod)
        self.controller.start()

    def stop(self):
        """Stop the DHT."""
        self.controller.stop()
        time.sleep(.1) # Give time for the controller (reactor) to stop
    
    def get_peers(self, info_hash, callback_f, bt_port=None):
        """ Start a get peers lookup. Return a Lookup object.
        
        The info_hash must be an identifier.Id object.
        
        The callback_f must expect one parameter. When peers are
        discovered, the callback is called with a list of peers as paramenter.
        The list of peers is a list of addresses (<IPv4, port> pairs).

        The bt_port parameter is optional. When provided, ANNOUNCE messages
        will be send using the provided port number.

        """
        if not self.controller.get_peers(info_hash, callback_f, bt_port):
            print 'ERROR: the lookup could not start'

    def print_routing_table_stats(self):
        self.controller.print_routing_table_stats()


    #TODO2: Future Work
    #TODO2: def add_bootstrap_node(self, node_addr, node_id=None):
    #TODO2: def lookup.back_off()
