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


def _on_peers_found(lookup_id, peers):
    if peers:
        print '[%.4f] %d peer(s)' % (time.time() - start_ts, len(peers))
    else:
        print '[%.4f] END OF LOOKUP' % (time.time() - start_ts)
        print 'Type an info_hash (in hex digits): ',

def main(options, args):
    my_addr = (options.ip, int(options.port))
    logs_path = options.path
    logging_conf.setup(logs_path, logs_level)
    print 'Using the following plug-ins:'
    print '*', options.routing_m_file
    print '*', options.lookup_m_file
    routing_m_name = '.'.join(os.path.split(options.routing_m_file))[:-3]
    routing_m_mod = __import__(routing_m_name, fromlist=[''])
    lookup_m_name = '.'.join(os.path.split(options.lookup_m_file))[:-3]
    lookup_m_mod = __import__(lookup_m_name, fromlist=[''])

    dht = pymdht.Pymdht(my_addr, logs_path,
                        routing_m_mod,
                        lookup_m_mod)
    
    print '\nType "exit" to stop the DHT and exit'
    print 'Type an info_hash (in hex digits): ',
    while (1):
        input = sys.stdin.readline().strip()
        if input == 'exit':
            dht.stop()
            break
        elif input == 'm':
            import guppy
            h = guppy.hpy()
            print h.heap()
            continue
        try:
            info_hash = identifier.Id(input)
        except (identifier.IdError):
            print 'Invalid input (%s)' % input
            continue
        print 'Getting peers for info_hash %r' % info_hash
        global start_ts
        start_ts = time.time()
        dht.get_peers(None, info_hash, _on_peers_found)
        
if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-a", "--address", dest="ip",
                      metavar='IP', default='127.0.0.1',
                      help="IP address to be used")
    parser.add_option("-p", "--port", dest="port",
                      metavar='INT', default=7000,
                      help="port to be used")
    parser.add_option("-x", "--path", dest="path",
                      metavar='PATH', default='interactive_logs/',
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

    (options, args) = parser.parse_args()
    
    main(options, args)


