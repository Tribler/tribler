# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import time
import sys

import logging, logging_conf
from utils import log
logs_path = '.'
logs_level = logging.DEBUG # This generates HUGE (and useful) logs
#logs_level = logging.INFO # This generates some (useful) logs
#logs_level = logging.WARNING # This generates warning and error logs
logging_conf.setup(logs_path, logs_level)

import identifier
import kadtracker

def peers_found(peers):
    print 'Peers found:'
    for peer in peers:
        print peer
    print '-'*20

def lookup_done():
    print 'Lookup DONE'

if len(sys.argv) == 4 and sys.argv[0] == 'server_dht.py':
    log.critical('argv %r' % sys.argv)
    RUN_DHT = True
    my_addr = (sys.argv[1], int(sys.argv[2])) #('192.16.125.242', 7000)
    logs_path = sys.argv[3]
    dht = kadtracker.KadTracker(my_addr, logs_path)
else:
    RUN_DHT = False
    print 'usage: python server_dht.py dht_ip dht_port path'
    
try:
    print 'Type Control-C to exit.'
    while (RUN_DHT):
        time.sleep(10 * 60)
        info_hash = identifier.RandomId()
        dht.get_peers(info_hash, peers_found)
except (KeyboardInterrupt):
    dht.stop()
    

