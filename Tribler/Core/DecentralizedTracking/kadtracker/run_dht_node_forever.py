# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import time
import sys

import logging, logging_conf
from utils import log

import identifier
import kadtracker

def peers_found(peers):
    for peer in peers:
        print peer
    print 'Type "EXIT" to stop the DHT and exit'
    print 'Type an info_hash (in hex digits):'

def lookup_done():
    print 'No peers found'
    print 'Type "EXIT" to stop the DHT and exit'
    print 'Type an info_hash (in hex digits):'

if len(sys.argv) == 5 and sys.argv[1] == 'interactive_dht':
    log.critical('argv %r' % sys.argv)
    assert 0
    RUN_DHT = True
    my_addr = (sys.argv[1], sys.argv[2]) #('192.16.125.242', 7000)
    logs_path = sys.argv[3]
    dht = kadtracker.KadTracker(my_addr, logs_path)
else:
    RUN_DHT = False
    print 'usage: python interactive_dht ip port paht'
    
while (RUN_DHT):
    input = sys.stdin.readline()[-1]
    if input == 'EXIT':
        dht.stop()
        break
    try:
        info_hash = identifier.Id(hex_id)
    except (IdError):
        print 'Invalid info_hash (%s)' % hex_id
        continue
    dht.get_peers(info_hash, do_nothing)


