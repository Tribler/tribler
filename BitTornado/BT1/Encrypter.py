# Written by Bram Cohen and Pawel Garbacki
# see LICENSE.txt for license information

from cStringIO import StringIO
from binascii import b2a_hex
from socket import error as socketerror
from urllib import quote
from struct import unpack
from sha import sha
from time import time

# 2fastbt_
from Tribler.toofastbt.Logger import get_logger
from traceback import print_exc, extract_stack, print_stack
import sys
# _2fastbt

from Tribler.Overlay.SecureOverlay import SecureOverlay

try:
    True
except:
    True = 1
    False = 0

DEBUG = False
MAX_INCOMPLETE = 8

protocol_name = 'BitTorrent protocol'
# Enable Tribler extensions:
# Left-most bit = Azureus Enhanced Messaging Protocol (AEMP)
# Left+42 bit = Tribler Overlay swarm extension
# Left+43 bit = Tribler Simple Merkle Hashes extension
# Right-most bit = BitTorrent DHT extension
#option_pattern = chr(0)*8
option_pattern = '\x00\x00\x00\x00\x00\x30\x00\x00'

def toint(s):
    return long(b2a_hex(s), 16)

def make_readable(s):
    if not s:
        return ''
    if quote(s).find('%') >= 0:
        return b2a_hex(s).upper()
    return '"'+s+'"'

def show(s):
    return b2a_hex(s)

class IncompleteCounter:
    def __init__(self):
        self.c = 0
    def increment(self):
        self.c += 1
    def decrement(self):
        self.c -= 1
    def toomany(self):
        return self.c >= MAX_INCOMPLETE

incompletecounter = IncompleteCounter()


# header, reserved, download id, my id, [length, message]

class Connection:
# 2fastbt_
    def __init__(self, Encoder, connection, id, ext_handshake = False, 
                  locally_initiated = None, dns = None, coord_con = False):
# _2fastbt
        self.Encoder = Encoder
        self.connection = connection    # SocketHandler.SingleSocket
        self.connecter = Encoder.connecter
        self.id = id
        self.readable_id = make_readable(id)
        self.coord_con = coord_con
        if locally_initiated is not None:
            self.locally_initiated = locally_initiated
        elif coord_con:
            self.locally_initiated = True
        else:
            self.locally_initiated = (id != None)
# _2fastbt
        self.complete = False
        self.keepalive = lambda: None
        self.closed = False
        self.buffer = StringIO()
# overlay        
        self.dns = dns
        self.support_overlayswarm = False
        self.connecter_conn = None
# _overlay
        self.support_merklehash= False
        if self.locally_initiated:
            incompletecounter.increment()
# 2fastbt_
        self.create_time = time()
# _2fastbt
        if self.locally_initiated or ext_handshake:
            self.connection.write(chr(len(protocol_name)) + protocol_name + 
                option_pattern + self.Encoder.download_id)
        if ext_handshake:
            self.connection.write(self.Encoder.my_id)
            self.next_len, self.next_func = 20, self.read_peer_id
        else:
            self.next_len, self.next_func = 1, self.read_header_len
        self.Encoder.raw_server.add_task(self._auto_close, 15)

    def get_ip(self, real=False):
        return self.connection.get_ip(real)

    def get_port(self, real=False):
        return self.connection.get_port(real)

    def get_myip(self, real=False):
        return self.connection.get_myip(real)
    
    def get_myport(self, real=False):
        return self.connection.get_myport(real)

    def get_id(self):
        return self.id

    def get_readable_id(self):
        return self.readable_id

    def is_locally_initiated(self):
        return self.locally_initiated

    def is_flushed(self):
        return self.connection.is_flushed()

    def supports_merklehash(self):
        return self.support_merklehash

    def set_options(self, s):
# overlay_
        r = unpack("B", s[5])
        if r[0] & 0x10:    # left + 43 bit
            self.support_overlayswarm = True
            if DEBUG:
                print "Peer supports overlay swarm"
        if r[0] & 0x20:    # left + 42 bit
            self.support_merklehash= True
            if DEBUG:
                print "Peer supports Merkle hashes"
# _overlay

    def read_header_len(self, s):
        if ord(s) != len(protocol_name):
            return None
        return len(protocol_name), self.read_header

    def read_header(self, s):
        if s != protocol_name:
            return None
        return 8, self.read_reserved

    def read_reserved(self, s):
        if DEBUG:
            print "encoder: Reserved bits:", show(s)
        self.set_options(s)
        return 20, self.read_download_id

    def read_download_id(self, s):
        if s != self.Encoder.download_id:
            return None
        if not self.locally_initiated:
            self.Encoder.connecter.external_connection_made += 1
            self.connection.write(chr(len(protocol_name)) + protocol_name + 
                option_pattern + self.Encoder.download_id + self.Encoder.my_id)
        return 20, self.read_peer_id

    def read_peer_id(self, s):
# 2fastbt_
        """ In the scenario of locally initiating: 
        - I may or may not (normally not) get the remote peerid from a tracker before connecting. 
        - If I've gotten the remote peerid, set it as self.id, otherwise set self.id as 0.
        - I send handshake message without my peerid. 
        - After I received peer's handshake message, if self.id isn't 0 (i.e., I had the remote peerid), 
        check the remote peerid, otherwise set self.id as the remote id. If the check is failed, drop the connection.
        - Then I send self.Encoder.my_id to the remote peer. 
        - The remote peer will record self.Encoder.id as my peerid.
        - Anyway, self.id should be the same with the remote id if handshake is ok.
        
        Note self.Encoder.id is a unique id to each swarm I have. 
        Normally self.id isn't equal to self.Encoder.my_id.
        
        In the scenario of remotely initiating:
        - I don't have remote id
        - I received the handshake message to join a swarm. 
        - Before I read the remote id, I send my handshake with self.Encoder.my_id, my unique id of the swarm.
        - I read the remote id and set it as my.id
        
        before read_peer_id(), self.id = 0 if locally init without remote id
                               self.id = remote id if locally init with remote id
                               self.id = None if remotely init
        after read_peer_id(),  self.id = remote id if locally init
                               self.id = remote id if remotely init
        """
# _2fastbt        
        if not self.id:    # remote init or local init without remote peer's id or remote init
            self.id = s
            self.readable_id = make_readable(s)
        else:    # locat init with remote id
            if s != self.id:
                return None
        self.complete = self.Encoder.got_id(self)
        if not self.complete:
            return None
        if self.locally_initiated:
            self.connection.write(self.Encoder.my_id)
            incompletecounter.decrement()
        c = self.Encoder.connecter.connection_made(self)
        self.keepalive = c.send_keepalive
# overlay_
        self.connect_overlay()
# _overlay
        return 4, self.read_len

# overlay_
    def connect_overlay(self):
        if self.support_overlayswarm and self.dns:
            so = SecureOverlay.getInstance()
            so.addTask(self.dns)
# _overlay

    def read_len(self, s):
        l = toint(s)
        if l > self.Encoder.max_len:
            return None
        return l, self.read_message

    def read_message(self, s):
        if s != '':
            self.connecter.got_message(self, s)
        return 4, self.read_len

    def read_dead(self, s):
        return None

    def _auto_close(self):
        if not self.complete and not self.is_coordinator_con():
            if DEBUG:
                print "encoder: autoclosing ",self.get_myip(),self.get_myport(),"to",self.get_ip(),self.get_port()
            self.close()

    def close(self):
        if DEBUG:
            print "encoder: closing connection",self.get_ip()
        if not self.closed:
            self.connection.close()
            self.sever()
            

    def sever(self):
        self.closed = True
        if self.Encoder.connections.has_key(self.connection):
            del self.Encoder.connections[self.connection]
        
        if self.complete:
            self.connecter.connection_lost(self)
        elif self.locally_initiated:
            incompletecounter.decrement()

    def send_message_raw(self, message):
        if not self.closed:
            self.connection.write(message)    # SingleSocket

    def data_came_in(self, connection, s):
        self.Encoder.measurefunc(len(s))
        while 1:
            if self.closed:
                return
            i = self.next_len - self.buffer.tell()
            if i > len(s):
                self.buffer.write(s)
                return
            self.buffer.write(s[:i])
            s = s[i:]
            m = self.buffer.getvalue()
            self.buffer.reset()
            self.buffer.truncate()
            try:
                x = self.next_func(m)
            except:
                print_exc()
                self.next_len, self.next_func = 1, self.read_dead
                raise
            if x is None:
                self.close()
                return
            self.next_len, self.next_func = x

    def connection_flushed(self, connection):
        if self.complete:
            self.connecter.connection_flushed(self)

    def connection_lost(self, connection):
        if self.Encoder.connections.has_key(connection):
            self.sever()
# 2fastbt_
    def is_coordinator_con(self):
        #if DEBUG:
        #    print "encoder: is_coordinator_con: coordinator is ",self.Encoder.coordinator_ip
        if self.coord_con:
            return True
        elif self.get_ip() == self.Encoder.coordinator_ip:
            return True
        else:
            return False

    def is_helper_con(self):
        coordinator = self.connecter.coordinator
        if coordinator is None:
            return False
        return coordinator.is_helper_ip(self.get_ip())
# _2fastbt

class Encoder:
    def __init__(self, connecter, raw_server, my_id, max_len,
            schedulefunc, keepalive_delay, download_id, 
            measurefunc, config):
        self.raw_server = raw_server
        self.connecter = connecter
        self.my_id = my_id
        self.max_len = max_len
        self.schedulefunc = schedulefunc
        self.keepalive_delay = keepalive_delay
        self.download_id = download_id
        self.measurefunc = measurefunc
        self.config = config
        self.connections = {}
        self.banned = {}
        self.to_connect = []
        self.paused = False
        if self.config['max_connections'] == 0:
            self.max_connections = 2 ** 30
        else:
            self.max_connections = self.config['max_connections']
# 2fastbt_
        self.toofast_banned = {}
        self.coordinator_ip = None
# _2fastbt        
        schedulefunc(self.send_keepalives, keepalive_delay)
        
    def send_keepalives(self):
        self.schedulefunc(self.send_keepalives, self.keepalive_delay)
        if self.paused:
            return
        for c in self.connections.values():
            c.keepalive()

    def start_connections(self, list):
        if DEBUG:
            print "encoder: connecting to",len(list),"peers"
        if not self.to_connect:
            self.raw_server.add_task(self._start_connection_from_queue)
        self.to_connect = list

    def _start_connection_from_queue(self):
        if self.connecter.external_connection_made:
            max_initiate = self.config['max_initiate']
        else:
            max_initiate = int(self.config['max_initiate']*1.5)
        cons = len(self.connections)
        if cons >= self.max_connections or cons >= max_initiate:
            delay = 60
        elif self.paused or incompletecounter.toomany():
            delay = 1
        else:
            delay = 0
            dns, id = self.to_connect.pop(0)
            self.start_connection(dns, id)
        if self.to_connect:
            self.raw_server.add_task(self._start_connection_from_queue, delay)

    def start_connection(self, dns, id, coord_con = False):
        """ Locally initiated connection """
        
        if ( self.paused
             or len(self.connections) >= self.max_connections
             or id == self.my_id
             or self.banned.has_key(dns[0]) ):
            if DEBUG:
                print "encoder: start_connection: we're paused or too busy"
            return True
        for v in self.connections.values():    # avoid duplicated connectiion from a single ip
            if v is None:
                continue
            if id and v.id == id:
                return True
            ip = v.get_ip(True)
            if self.config['security'] and ip != 'unknown' and ip == dns[0]:
                if DEBUG:
                    print "encoder: start_connection: using existing"
                return True
        try:
            if DEBUG:
                print "encoder: start_connection: Setting up new to peer", dns
            c = self.raw_server.start_connection(dns)
            con = Connection(self, c, id, dns = dns, coord_con = coord_con)
            self.connections[c] = con
            c.set_handler(con)
        except socketerror:
            if DEBUG:
                print "Encoder.connection failed"
            return False
        return True

    def _start_connection(self, dns, id):
        def foo(self=self, dns=dns, id=id):
            self.start_connection(dns, id)
       
        self.schedulefunc(foo, 0)

    def got_id(self, connection):
        """ check if the connection can be accepted """
        
        if connection.id == self.my_id:
            self.connecter.external_connection_made -= 1
            return False
        ip = connection.get_ip(True)
        if self.config['security'] and self.banned.has_key(ip):
            return False
        for v in self.connections.values():
            if connection is not v:
# 2fastbt_
                if connection.id == v.id and \
                    v.create_time < connection.create_time:
# _2fastbt
                    return False
                # don't allow multiple connections from the same ip if security is set.
                if self.config['security'] and ip != 'unknown' and ip == v.get_ip(True):
                    v.close()
        return True

    def external_connection_made(self, connection):
        """ Remotely initiated connection """
        if self.paused or len(self.connections) >= self.max_connections:
            connection.close()
            return False
        con = Connection(self, connection, None)
        self.connections[connection] = con
        connection.set_handler(con)
        return True

    def externally_handshaked_connection_made(self, connection, options, already_read):
# 2fastbt_
        if self.paused or len(self.connections) >= self.max_connections:
# _2fastbt
            connection.close()
            return False
#        con = Connection(self, connection, None, True, options = options)
        con = Connection(self, connection, None, True)
        con.set_options(options)
        # before: connection.handler = Encoder
# 2fastbt_
        # Don't forget to count the external conns!
        self.connections[connection] = con
# _2fastbt
        connection.set_handler(con)
        # after: connection.handler = Encrypter.Connecter
        if already_read:
            con.data_came_in(con, already_read)
        return True

    def close_all(self):
        if DEBUG:
            print "encoder: closing all connections"
        copy = self.connections.values()[:]
        for c in copy:
            c.close()
        self.connections = {}

    def ban(self, ip):
        self.banned[ip] = 1

    def pause(self, flag):
        self.paused = flag

# 2fastbt_
    def set_coordinator_ip(self,ip):
        self.coordinator_ip = ip
# _2fastbt    
