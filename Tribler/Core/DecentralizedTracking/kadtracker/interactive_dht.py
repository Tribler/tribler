# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import time
import sys

import logging, logging_conf
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
    print 'Type an info_hash (in hex digits): ',

def lookup_done():
    print 'Lookup DONE'
    print 'Type an info_hash (in hex digits): ',

if len(sys.argv) == 4 and sys.argv[0] == 'interactive_dht.py':
    RUN_DHT = True
    my_addr = (sys.argv[1], int(sys.argv[2])) #('192.16.125.242', 7000)
    logs_path = sys.argv[3]
    dht = kadtracker.KadTracker(my_addr, logs_path)
else:
    RUN_DHT = False
    print 'usage: python interactive_dht.py dht_ip dht_port log_path'
    
print 'Type "exit" to stop the DHT and exit'
while (RUN_DHT):
    print 'Type an info_hash (in hex digits): ',
    input = sys.stdin.readline()[:-1]
    if input == 'exit':
        dht.stop()
        break
    try:
        info_hash = identifier.Id(input)
    except (identifier.IdError):
        print 'Invalid input (%s)' % input
        continue
    print 'Getting peers for info_hash %r' % info_hash
    dht.get_peers(info_hash, peers_found)


