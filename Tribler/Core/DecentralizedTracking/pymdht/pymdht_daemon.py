#! /usr/bin/env python

# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import SocketServer
import random
import sys, os
from optparse import OptionParser

import core.ptime as time
import logging
import core.logging_conf as logging_conf

logs_level = logging.DEBUG # This generates HUGE (and useful) logs
#logs_level = logging.INFO # This generates some (useful) logs
#logs_level = logging.WARNING # This generates warning and error logs

import core.identifier as identifier
import core.pymdht as pymdht

MAX_PORT = 2**16 - 1

dht = None

class SanitizeError(Exception):
    pass

class Channel(object):

    def __init__(self, send, recv):
        self.send = send
        self.recv = recv
        self.peers = set()
        self.open = True

class Channels(object):

    def __init__(self):
        self.channels = []
        self.next_recv = 1

    def create(self, send):
        recv = self.next_recv
        self.next_recv += 1
        channel = Channel(send, recv)
        self.channels.append(channel)
        return channel
        
    def get(self, recv):
        for channel in self.channels:
            if channel.recv == recv:
                return channel

    def remove(self, channel):
        recv = channel.recv
        for i in range(len(self.channels)):
            if self.channels[i].recv == recv:
                del self.channels[i]

                
class SessionHandler(SocketServer.StreamRequestHandler):

    def __init__(self, *args, **kwargs):
        self.open_channels = Channels()
        SocketServer.StreamRequestHandler.__init__(self, *args, **kwargs)
        todo_msgs = ['TODO:',
                'Announce when the port is non-zero',
                'Enable SLOW lookup',
            ]
        for msg in todo_msgs:
            self.wfile.write('%s\r\n' % (msg))
        
    def _on_peers_found(self, channel, peers):
        if not channel.open:
            print 'Got peers but channel is CLOSED'
            return
        if not peers:
            print "end of lookup"
            self.open_channels.remove(channel)
            self.wfile.write('%d CLOSE\r\n' % (channel.send))
            return
        print 'got %d peer' % len(peers)
        for peer in peers:
            if peer not in channel.peers:
                channel.peers.add(peer)
                self.wfile.write('%d PEER %s:%d\r\n' % (channel.send,
                                                        peer[0], peer[1]))
        return

    def _on_new_channel(self, splitted_line):
        if (len(splitted_line) != 7 or
            splitted_line[1] != 'OPEN' or
            splitted_line[3] != 'HASH'):
            raise SanitizeError, '? Invalid OPEN message'
        try:
            send = int(splitted_line[2])
        except (ValueError):
            raise SanitizeError, '? Channel must be integer'
        key, lookup_mode, port_str = splitted_line[4:]
        try:
            info_hash = identifier.Id(key)
        except (identifier.IdError):
            raise SanitizeError, '? Invalid key (must be 40 HEX characters)'
        if lookup_mode != 'FAST':
            raise SanitizeError, '? Only FAST lookup supported'
        try:
            port = int(port_str)
        except (ValueError):
            raise SanitizeError, '? Port must be integer'
        if port > MAX_PORT:
            raise SanitizeError, '? Invalid port number'

        channel = self.open_channels.create(send)
        dht.get_peers(channel, info_hash, self._on_peers_found, port)
        return '%d OPEN %d' % (channel.send, channel.recv)
        

    def _on_existing_channel(self, recv, splitted_line):
        channel = self.open_channels.get(recv)
        if not channel:
            raise SanitizeError, '? Wrong channel'
        if (len(splitted_line) != 2 or
            splitted_line[1] != 'CLOSE'):
            raise SanitizeError, '%d Only CLOSE is accepted' % (
                channel.send)
        channel.open = False
        self.open_channels.remove(channel)
        return '%d CLOSE' % (channel.send)

    def _get_recv(self, splitted_line):
        if not splitted_line: 
            raise SanitizeError, "? I don't like empty lines"
        try:
            return int(splitted_line[0])
        except (ValueError):
            raise SanitizeError, '? Channel must be a number'
    
    def handle(self):
        while (1):
            
            # Profile memory usage
            '''
            import objgraph
            objgraph.show_most_common_types(limit=20)
            '''
            import guppy
            h = guppy.hpy()
            print h.heap()
            print '=================================='
            

            
            line = self.rfile.readline().strip()
            splitted_line = line.split()
            try:
                recv = self._get_recv(splitted_line)
                if recv:
                    response = self._on_existing_channel(recv, splitted_line)
                else:
                    response = self._on_new_channel(splitted_line)
            except (SanitizeError), error_msg:
                self.wfile.write('%s\r\n' % (error_msg))
            else:
                self.wfile.write('%s\r\n' % (response))

                
def main(options, args):
    port = int(options.port)
    my_addr = (options.ip, port)
    logs_path = options.path
    logging_conf.setup(logs_path, logs_level)
    print 'Using the following plug-ins:'
    print '*', options.routing_m_file
    print '*', options.lookup_m_file
    routing_m_name = '.'.join(os.path.split(options.routing_m_file))[:-3]
    routing_m_mod = __import__(routing_m_name, fromlist=[''])
    lookup_m_name = '.'.join(os.path.split(options.lookup_m_file))[:-3]
    lookup_m_mod = __import__(lookup_m_name, fromlist=[''])

    global dht
    dht = pymdht.Pymdht(my_addr, logs_path,
                        routing_m_mod,
                        lookup_m_mod)

    server = SocketServer.TCPServer(('', port), SessionHandler)
    server.serve_forever()
    
        
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
                      metavar='FILE', default='plugins/lookup_m2_a4.py',
                      help="file containing the lookup_manager code")
    parser.add_option("-z", "--logs-level", dest="logs_level",
                      metavar='INT',
                      help="logging level")

    (options, args) = parser.parse_args()
    
    '''
    # Trace memory leaks
    import cherrypy
    import dowser
    cherrypy.config.update({'server.socket_port': 8080})
    cherrypy.tree.mount(dowser.Root())
    cherrypy.engine.start()
    '''
    main(options, args)


