# Written by Bram Cohen, Jie Yang
# see LICENSE.txt for license information
import sys
from struct import unpack

from BitTornado.bitfield import Bitfield
from BitTornado.clock import clock
from binascii import b2a_hex
from BitTornado.bencode import bencode,bdecode
from BitTornado.BT1.MessageID import *
from traceback import print_exc

try:
    True
except:
    True = 1
    False = 0

DEBUG = False

def toint(s):
    return long(b2a_hex(s), 16)

def tobinary(i):
    return (chr(i >> 24) + chr((i >> 16) & 0xFF) + 
        chr((i >> 8) & 0xFF) + chr(i & 0xFF))

class Connection:
    def __init__(self, connection, connecter, dns=None):
        self.connection = connection # OverlayEncoder.connection
        self.connecter = connecter
        self.dns = dns
        self.permid = None
        self.got_anything = False
        self.closed = False
        self.auth_listen_port = -1

    def get_ip(self, real=False):
        return self.connection.get_ip(real)

    def get_port(self, real=False):
        return self.connection.get_port(real)
    
    def get_dns(self):
        if not self.dns:
            self.dns = (self.get_ip(True), self.get_port(True))
        return self.dns

    def get_myip(self, real=False):
        return self.connection.get_myip(real)

    def get_myport(self, real=False):
        return self.connection.get_myport(real)

    def get_id(self):
        return self.connection.get_id()

    def get_readable_id(self):
        return self.connection.get_readable_id()
    
    def set_permid(self, permid):
        self.permid = str(permid)

    def set_auth_peer_id(self,peer_id):
        # See OverlaySwarm.register()
        bin = peer_id[14:16]
        tuple = unpack('H', bin)
        self.auth_listen_port = tuple[0]

    def get_auth_listen_port(self):
        return self.auth_listen_port

    def close(self):
        if not self.closed:
            if DEBUG:
                print 'olconnctr: closing connection',self.dns
            self.closed = True
            self.connection.close()

    def is_locally_initiated(self):
        return self.connection.is_locally_initiated()

    def send_cancel(self, index, begin, length):
        self.send_message(CANCEL + tobinary(index) + 
            tobinary(begin) + tobinary(length))
        if DEBUG:
            print 'sent cancel: '+str(index)+': '+str(begin)+'-'+str(begin+length)

    def send_keepalive(self):
        self.send_message('')
        
    def send_message(self, s):
        s = tobinary(len(s))+s
        self.connection.send_message_raw(s)

    def backlogged(self):
        return not self.connection.is_flushed()


class OverlayConnecter:
    def __init__(self, overlayswarm, config, ratelimiter = None):
        self.config = config
        self.ratelimiter = ratelimiter
        self.overlayswarm = overlayswarm
        self.connections = {}
        self.external_connection_made = 0

    def how_many_connections(self):
        return len(self.connections)

    def connection_made(self, connection, dns=None):
        c = Connection(connection, self, dns)
        self.connections[connection] = c
        if DEBUG:
            print >> sys.stderr,"olconnctr: connection_made", connection, dns, self.connections
        return c
    
    def connection_lost(self, connection):
        if DEBUG:
            print >> sys.stderr,"olconnctr: connection_lost"
        try:
            #if self.connections.has_key(connection)
            del self.connections[connection]
        except:
            print_exc()

    def connection_flushed(self, connection):
        if DEBUG:
            print >> sys.stderr,"olconnctr: connection flushed!!!!"
        pass    
            
    def got_piece(self, i):
        for co in self.connections.values():
            co.send_have(i)

    def got_message(self, connection, message):
        # connection: Encrypter.Connection; 
        # c: Connecter.Connection
        c = self.connections[connection]
        self.overlayswarm.got_message(c, message)

