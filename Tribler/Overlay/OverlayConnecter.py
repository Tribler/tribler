# Written by Bram Cohen
# see LICENSE.txt for license information

from BitTornado.bitfield import Bitfield
from BitTornado.clock import clock
from binascii import b2a_hex
from BitTornado.bencode import bencode,bdecode
from BitTornado.BT1.MessageID import *

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
    def __init__(self, connection, connecter, dns=None, permid=None):
        self.connection = connection
        self.connecter = connecter
        self.dns = dns
        self.permid = permid
        self.got_anything = False
        self.closed = False

    def get_ip(self, real=False):
        return self.connection.get_ip(real)

    def get_id(self):
        return self.connection.get_id()

    def get_readable_id(self):
        return self.connection.get_readable_id()

    def close(self):
        if DEBUG:
            print 'connection closed'
        self.closed = True
        self.connection.close()

    def is_locally_initiated(self):
        return self.connection.is_locally_initiated()

    def send_cancel(self, index, begin, length):
        self._send_message(CANCEL + tobinary(index) + 
            tobinary(begin) + tobinary(length))
        if DEBUG:
            print 'sent cancel: '+str(index)+': '+str(begin)+'-'+str(begin+length)

    def send_keepalive(self):
        self._send_message('')
        
    def _send_message(self, s):
        s = tobinary(len(s))+s
        if self.partial_message:
            self.outqueue.append(s)
        else:
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

    def connection_made(self, connection, dns=None, permid=None):
        c = Connection(connection, self, dns, permid)
        self.connections[connection] = c
        self.overlayswarm.connectionMade(c)    # notify overlay a new connection is made
        return c

    def connection_lost(self, connection):
        c = self.connections[connection]
        del self.connections[connection]

    def got_piece(self, i):
        for co in self.connections.values():
            co.send_have(i)

    def got_message(self, connection, message):
        # connection: Encrypter.Connection; 
        # c: Connecter.Connection
        c = self.connections[connection]
        self.overlay_swarm.got_message(c, c.permid, message)

