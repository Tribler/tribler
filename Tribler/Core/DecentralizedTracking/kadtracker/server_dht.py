# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import time
import sys
import pdb
#import guppy

import logging, logging_conf
logs_path = '.'
logs_level = logging.DEBUG # This generates HUGE (and useful) logs
#logs_level = logging.INFO # This generates some (useful) logs
#logs_level = logging.WARNING # This generates warning and error logs
#logs_level = logging.CRITICAL

import identifier
import kadtracker


#hp = guppy.hpy()

def peers_found(peers):
    print 'Peers found:', time.time()
    return
    for peer in peers:
        print peer
    print '-'*20

def lookup_done():
    print 'Lookup DONE'


info_hashes = (
    identifier.RandomId(),
    identifier.Id('28f2e5ea2bf87eae4bcd5e3fc9021844c01a4df9'),
    identifier.RandomId(),
    identifier.Id('dd5c25b4b8230e108fbf9d07f87a86c6b05c9b6d'),
    identifier.RandomId(),
    identifier.Id('bcbdb9c2e7b49c65c9057431b492cb7957c8a330'),
    identifier.RandomId(),
    identifier.Id('d93df7a507f3c9d2ebfbe49762a217ab318825bd'),
    identifier.RandomId(),
    identifier.Id('6807e5d151e2ac7ae92eabb76ddaf4237e4abb60'),
    identifier.RandomId(),
    identifier.Id('83c7b3b7d36da4df289670592be68f9dc7c7096e'),
    identifier.RandomId(),
    identifier.Id('9b16aecf952597f9bb051fecb7a0d8475d060fa0'),
    identifier.RandomId(),
    identifier.Id('24f2446365d3ef782ec16ad63aea1206df4b8d21'),
    identifier.RandomId(),
    identifier.Id('a91af3cde492e29530754591b862b1beecab10ff'),
    identifier.RandomId(),
    identifier.Id('3119baecadea3f31bed00de5e7e76db5cfea7ca1'),
    )
    
if len(sys.argv) == 4 and sys.argv[0] == 'server_dht.py':
    logging.critical('argv %r' % sys.argv)
    RUN_DHT = True
    my_addr = (sys.argv[1], int(sys.argv[2])) #('192.16.125.242', 7000)
    logs_path = sys.argv[3]
    print 'logs_path:', logs_path
    logging_conf.setup(logs_path, logs_level)
    dht = kadtracker.KadTracker(my_addr, logs_path)
else:
    RUN_DHT = False
    print 'usage: python server_dht.py dht_ip dht_port path'
    
try:
    print 'Type Control-C to exit.'
    i = 0
    while (RUN_DHT):
        for info_hash in info_hashes:
            #splitted_heap_str = str(hp.heap()).split()
            #print i, splitted_heap_str[10]
            dht.print_routing_table_stats()
            time.sleep(2 * 60)
            print 'Getting peers:', time.time()
            dht.get_peers(info_hash, peers_found)
            #time.sleep(1.5)
            #dht.stop()
            #pdb.set_trace()
            i = i + 1
except (KeyboardInterrupt):
    dht.stop()
    

