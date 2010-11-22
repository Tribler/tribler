#! /usr/bin/env python

# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import core.ptime as time
import sys, os
from optparse import OptionParser

import logging
import core.logging_conf as logging_conf

logs_level = logging.DEBUG # This generates HUGE (and useful) logs
#logs_level = logging.INFO # This generates some (useful) logs
#logs_level = logging.WARNING # This generates warning and error logs

import core.identifier as identifier
import core.pymdht as pymdht


def _on_peers_found(start_ts, peers):
    if peers:
        print '[%.4f] %d peer(s)' % (time.time() - start_ts, len(peers))
        print peers
    else:
        print '[%.4f] END OF LOOKUP' % (time.time() - start_ts)

def main(options, args):
    my_addr = (options.ip, int(options.port))
    logs_path = options.path
    print 'Using the following plug-ins:'
    print '*', options.routing_m_file
    print '*', options.lookup_m_file
    print 'Private DHT name:', options.private_dht_name
    routing_m_name = '.'.join(os.path.split(options.routing_m_file))[:-3]
    routing_m_mod = __import__(routing_m_name, fromlist=[''])
    lookup_m_name = '.'.join(os.path.split(options.lookup_m_file))[:-3]
    lookup_m_mod = __import__(lookup_m_name, fromlist=[''])

    dht = pymdht.Pymdht(my_addr, logs_path,
                        routing_m_mod,
                        lookup_m_mod,
                        options.private_dht_name,
                        logs_level)
    
    print '\nType "exit" to stop the DHT and exit'
    print 'Type "help" if you need'
    while (1):
        input = sys.stdin.readline().strip().split()
        if not input:
            continue
        command = input[0]
        if command == 'help':
            print '''
Available commands are:
- help
- fast info_hash bt_port
- exit
- m                  Memory information
'''
        elif command == 'exit':
            dht.stop()
            break
        elif command == 'm':
            import guppy
            h = guppy.hpy()
            print h.heap()
        elif command == 'fast':
            if len(input) != 3:
                print 'usage: fast info_hash bt_port'
                continue
            try:
                info_hash = identifier.Id(input[1])
            except (identifier.IdError):
                print 'Invalid info_hash (%s)' % input[1]
            try:
                bt_port = int(input[2])
            except:
                print 'Invalid bt_port (%r)' % input[2]
                continue
            success, peers = dht.get_peers(time.time(), info_hash,
                                           _on_peers_found, bt_port)
            if not success:
                print 'Lookup failed'
            if peers:
                print '[local] %d peer(s)' % (len(peers))
                print peers
                
        
if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-a", "--address", dest="ip",
                      metavar='IP', default='127.0.0.1',
                      help="IP address to be used")
    parser.add_option("-p", "--port", dest="port",
                      metavar='INT', default=7000,
                      help="port to be used")
    parser.add_option("-x", "--path", dest="path",
                      metavar='PATH', default='.',
                      help="state.dat and logs location")
    parser.add_option("-r", "--routing-plug-in", dest="routing_m_file",
                      metavar='FILE', default='plugins/routing_nice_rtt.py',
                      help="file containing the routing_manager code")
    parser.add_option("-l", "--lookup-plug-in", dest="lookup_m_file",
                      metavar='FILE', default='plugins/lookup_a16.py',
                      help="file containing the lookup_manager code")
    parser.add_option("-z", "--logs-level", dest="logs_level",
                      metavar='INT',
                      help="logging level")
    parser.add_option("-d", "--private-dht", dest="private_dht_name",
                      metavar='STRING', default=None,
                      help="private DHT name")

    (options, args) = parser.parse_args()
    
    main(options, args)


