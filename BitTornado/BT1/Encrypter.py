# Written by Bram Cohen and Pawel Garbacki
# see LICENSE.txt for license information

from cStringIO import StringIO
from binascii import b2a_hex
from socket import error as socketerror
from urllib import quote
from struct import unpack
from sha import sha
from time import time

from MessageID import CurrentVersion, LowestVersion, SupportedVersions
# 2fastbt_
from Tribler.DownloadHelp.toofastbt.Logger import get_logger
from traceback import print_exc, extract_stack
import sys
# _2fastbt

try:
    True
except:
    True = 1
    False = 0

DEBUG = True
MAX_INCOMPLETE = 8

protocol_name = 'BitTorrent protocol'
# Enable I-Share extensions:
# Left-most bit = Azureus Enhanced Messaging Protocol (AEMP)
# Left+42 bit = I-Share Overlay swarm extension
# Left+43 bit = I-Share Simple Merkle Hashes extension
# Right-most bit = BitTorrent DHT extension
#option_pattern = chr(0)*8
option_pattern = '\x00\x00\x00\x00\x00\x30\x00\x00'
# 2fastbt_
control_option_pattern = '\x00\x00\x00\x00\x00\x40\x00\x00' # chr(0) * 6 + chr(1) * 2
# _2fastbt

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

# 2fastbt_
def combine_patterns(p1, p2):
    l = len(p1)
    assert(l == len(p2))
    r = ''
    for i in range(0, l):
        v1 = unpack('B', p1[i])[0]
        v2 = unpack('B', p2[i])[0]
        r += chr(v1 | v2)
    return r
# _2fastbt

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
    def __init__(self, Encoder, connection, id, ext_handshake = False, locally_initiated = None, control_con = False): #, options = None):
# _2fastbt
        self.Encoder = Encoder
        self.connection = connection    # SocketHandler.SingleSocket
        self.connecter = Encoder.connecter
        self.connecter_connection = None    # Connecter.Connection
        self.id = id
        self.readable_id = make_readable(id)
# 2fastbt_
        self.control_con = control_con
#        self.options  = options
        if locally_initiated is not None:
            self.locally_initiated = locally_initiated
        else:
            self.locally_initiated = (id != None)
# _2fastbt
        self.complete = False
        self.keepalive = lambda: None
        self.closed = False
        self.buffer = StringIO()
        self.overlay_swarm = Encoder.overlay_swarm
        self.overlay_version = CurrentVersion
        if self.locally_initiated:
            incompletecounter.increment()
# 2fastbt_
        self.create_time = time()
# TODO: incomplete counter???
        if self.locally_initiated or ext_handshake or self.is_control_con():
            option_to_send = option_pattern
            if self.is_control_con():
                option_to_send = combine_patterns(option_to_send, control_option_pattern)
            self.connection.write(chr(len(protocol_name)) + protocol_name + 
                option_to_send + self.Encoder.download_id)
# _2fastbt
        if ext_handshake:
            self.connection.write(self.Encoder.my_id)
            self.next_len, self.next_func = 20, self.read_peer_id
        else:
            self.next_len, self.next_func = 1, self.read_header_len
        if self.is_overlayswarm() and self.is_locally_initiated():
            self.overlay_swarm.close_conn[self] = time() + \
                                            self.overlay_swarm.alive_interval
            self.Encoder.raw_server.add_task(self._auto_close_overlay, 
                                            self.overlay_swarm.alive_interval+2)
        else:
            self.Encoder.raw_server.add_task(self._auto_close, 15)
        self.support_overlayswarm = False  # does peer support Overlay Swarm?
        self.support_merklehash= False  # does peer support Merkle hashes

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

    def supports_overlayswarm(self):
        return self.support_overlayswarm

    def supports_merklehash(self):
        return self.support_merklehash

    def is_overlayswarm(self):
        return self.Encoder.download_id == OverlaySwarm.infohash

    def set_options(self, s):
        r = unpack("B", s[5])
        if r[0] & 0x10:    # left + 43 bit
            self.support_overlayswarm = True
            if DEBUG:
                print "Peer supports overlay swarm"
        if r[0] & 0x20:    # left + 42 bit
            self.support_merklehash= True
            if DEBUG:
                print "Peer supports Merkle hashes"
# 2fastbt_
        if r[0] & 0x40:
            self.control_con = True
            if DEBUG:
                print "Control connection"
# _2fastbt


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
            print "Reserved bits:", show(s)
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
        if not self.id:    # remote init or local init without remote peer's id or remote init
            self.id = s
            self.readable_id = make_readable(s)
        else:    # locat init with remote id
            if s != self.id:
                print "NONE self.id not s"
                return None
        self.complete = self.Encoder.got_id(self)
        if not self.complete:
            print "NONE incomplete"
            return None
        if self.is_overlayswarm():
            if not self.check_overlay_version(s[16:18], s[18:20]):    # versioning protocol
                print "NONE overlay version"
                return None
        if self.locally_initiated:
            self.connection.write(self.Encoder.my_id)
            incompletecounter.decrement()
        c = self.Encoder.connecter.connection_made(self)    
        self.keepalive = c.send_keepalive

# 2fastbt_
        if self.is_control_con() and self.Encoder.connecter.coordinator is None:
            self.Encoder.connecter.helper.coordinator_con = c
        if self.locally_initiated and self.is_control_con():
            # start normal (data-exchange) connection with coordinator
            self.Encoder.start_connection((self.connection.socket.getpeername()), self.id)
        if self.Encoder.connecter.helper is not None and self.Encoder.connecter.helper.coordinator_data_con is None and self.is_coordinator_con():
            if not self.is_control_con():
                get_logger().log(3, "encrypter.connection control_data_con created")
                self.Encoder.connecter.helper.coordinator_data_con = c
            else:
                for c in self.Encoder.connecter.connections.values():
                    if not c.connection.is_control_con() and (c.get_id() == self.get_id()):
                        get_logger().log(3, "encrypter.connection control_data_con created")
                        self.Encoder.connecter.helper.coordinator_data_con = c
                        break

        if not self.is_overlayswarm() and not self.is_control_con():
# _2fastbt
            ip = self.get_ip(True)
            port = self.get_port(True)
            self.overlay_swarm.add_peer(ip, port, c)
# 2fastbt_
        if self.locally_initiated and not self.is_control_con():
# _2fastbt
            self.post_connection_made(c)    # Make overlay swarm connection
        return 4, self.read_len

    def check_overlay_version(self, low_ver_str, cur_ver_str):
        """ overlay swarm versioning solution: use last 4 bytes in PeerID """
        
        if self.is_overlayswarm():
            low_ver = unpack('H', low_ver_str)[0]
            cur_ver = unpack('H', cur_ver_str)[0]
            print "VERSIONS ARE",low_ver,cur_ver
            if cur_ver != CurrentVersion:
                if low_ver > CurrentVersion:    # the other's version is too high
                    return False
                if cur_ver < LowestVersion:     # the other's version is too low
                    return False           
                if cur_ver < CurrentVersion and \
                   cur_ver not in SupportedVersions:   # the other's version is not supported
                    return False
                if cur_ver < CurretVersion:     # set low version as our version
                    self.overlay_version = cur_ver
            return True
        else:
            return False

    def post_connection_made(self, conn):
        """ Initailize overlay swarm connection; exchange permid if overlay conncetion is established """
        
        if not self.is_overlayswarm():
            if self.supports_overlayswarm():    # attempt to connect overlay swarm
                # only connection initiator makes overlay connection to avoid being blocked by firewall
                self.overlay_swarm.connection_made(self)
#                ip, port = self.get_ip(True), self.get_port(True)
                #self.overlay_swarm.add_os_task2(ip, port, 'PREFERENCE_EXCHANGE')
#                torrent_hash = '\xfbpB6\x88}\xd6\x81\x89\x00\xd5\x01(\x88\x08\xda\x16\xf5\xbe\xc9'
#                self.overlay_swarm.add_os_task2(ip, port, ('DOWNLOAD_HELP', torrent_hash))
                
                #self.overlay_swarm.start_prefxchg(ip, port)
                #self.overlay_swarm.request_download_help(ip, port, '')
                
        else:    # couple overlay swarm connection with normal swarm connection
            # permid exchange is always the first message in overlay swarm connection
            self.overlay_swarm.add_os_task(conn, 'CHALLENGE')
            self.overlay_swarm.check_os_task(conn)

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
        if not self.complete:
            self.close()

    def _auto_close_overlay(self):
        if not self.overlay_swarm.close_conn.has_key(self):
            return
        if time() > self.overlay_swarm.close_conn[self]:
            self.close()
        else:
            self.raw_server.add_task(self._auto_close_overlay, 
                                     self.overlay_swarm.alive_interval+5)
                    
    def close(self):
        if not self.closed:
            self.connection.close()
            self.sever()
            

    def sever(self):
        self.closed = True
        if self.is_overlayswarm():
            if self.overlay_swarm.close_conn.has_key(self):
                del self.overlay_swarm.close_conn[self]
            if self.connecter_connection and self.connecter_connection.permid:
                self.overlay_swarm.remove_connection(self.connecter_connection.permid)    # delete it or set is as None?
            self.overlay_swarm.remove_peer(self)
        del self.connecter_connection
        del self.Encoder.connections[self.connection]
        
        if self.complete:
            self.connecter.connection_lost(self)
        elif self.locally_initiated:
            incompletecounter.decrement()

    def send_message_raw(self, message):
        if not self.closed:
            self.connection.write(message)    # SingleSocket

    def data_came_in(self, connection, s):
        #if DEBUG and self.is_overlayswarm():
        #    print ">>>>>>>>Encrypter.Conection data came in", show(s), self.next_func
        self.Encoder.measurefunc(len(s))  #TODO: add rate limiter for overlay 
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
#            get_logger().log(3, "encrypter.connection data came in m: '" +
#                    str(m) + "' next_func: '" + str(self.next_func) + "'")
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
    def is_control_con(self):
        return self.control_con

    def is_coordinator_con(self):
        helper = self.Encoder.connecter.helper
        if helper is None:
            return False
        coordinator_id = helper.get_coordinator_id()
        if coordinator_id is None:
            return False
        return coordinator_id == self.get_id()

    def is_helper_con(self):
        coordinator = self.Encoder.connecter.coordinator
        if coordinator is None:
            return False
        return coordinator.is_helper(self.get_id())
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
        self.overlay_swarm = OverlaySwarm.getInstance()
        if self.config['max_connections'] == 0:
            self.max_connections = 2 ** 30
        else:
            self.max_connections = self.config['max_connections']
# 2fastbt_
        self.toofast_banned = {}
# _2fastbt        
        schedulefunc(self.send_keepalives, keepalive_delay)
        if DEBUG:
            self.raw_server.add_task(self.check_connections, 2)
        
    def check_connections(self):
#        if not self.is_overlayswarm():
#            return
        self.raw_server.add_task(self.check_connections, 2)
        ##print '------------- ' + str(len(self.connections)) + ' - ' + show(self.download_id) + ' -------------'
        for conn in self.connections.values():
            if conn.connecter_connection and conn.connecter_connection.permid:
                permid = sha(conn.connecter_connection.permid).hexdigest()
            else:
                permid = 'no perm id'
            ##print 'Overlay Swarm:', str(conn.is_overlayswarm()), ' - ', conn.connecter_connection, permid
##        if self.is_overlayswarm():
##            print 'Peers:', self.overlay_swarm.peers
##            print 'Connections:', self.overlay_swarm.connections
        
    def is_overlayswarm(self):
        return self.download_id == OverlaySwarm.infohash

    def send_keepalives(self):
#        print "!!!!!!!!!!!!!!!!!!!!send keepalives"
        self.schedulefunc(self.send_keepalives, self.keepalive_delay)
        if self.paused:
            return
        for c in self.connections.values():
            c.keepalive()
# 2fastbt_
        helper = self.connecter.helper
        coordinator = self.connecter.coordinator
        if helper is not None and coordinator is None and helper.coordinator_con is not None:
            try:
                helper.coordinator_con.connection.keepalive()
            except:
                print_exc()
#            if not c.control_con:
#            c.keepalive()
# _2fastbt

    def start_connections(self, list):
        if DEBUG:
            print "Encrypter: connecting to",len(list),"peers"
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

    def start_connection(self, dns, id):
        """ Locally initiated connection """
        
        if ( self.paused
             or len(self.connections) >= self.max_connections
             or id == self.my_id
             or self.banned.has_key(dns[0]) ):
            print "Encoder start_connection paused RETURN"
            return True
#--- 2fastbt_
#        if self.banned.has_key(dns[0]) and not self.connection.is_helper_con() and \
#            not self.connections.is_coordinator_con()):
#            return True
# _2fastbt
        for v in self.connections.values():    # avoid duplicated connectiion from a single ip
            if v is None:
                continue
            if id and v.id == id:
                return True
            ip = v.get_ip(True)
            if self.config['security'] and ip != 'unknown' and ip == dns[0]:
                print "Encoder start_connection values RETURN"
                return True
        try:
            if DEBUG:
                print "Encoder.start_connection to peer", dns
            c = self.raw_server.start_connection(dns)
            con = Connection(self, c, id)
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
#--- 2fastbt_
#        if self.config['security'] and self.banned.has_key(ip):
        if self.banned.has_key(ip) and (self.config['security'] or \
            (not connection.is_helper_con() and not connection.is_coordinator_con())):
            print "is_helper_con: '" + str(connection.is_helper_con()) + \
                "' is_coordinator_con: '" + str(connection.is_coordinator_con()) + "'"
# _2fastbt
            return False
        for v in self.connections.values():
            if connection is not v:
# 2fastbt_
                if connection.id == v.id and not connection.is_control_con() and \
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
        if not self.is_overlayswarm() and \
               (self.paused or len(self.connections) >= self.max_connections):
# _2fastbt
            connection.close()
            return False
#        con = Connection(self, connection, None, True, options = options)
        con = Connection(self, connection, None, True)
        con.set_options(options)
# 2fastbt_
        if not con.is_control_con():
            self.connections[connection] = con
# _2fastbt
        # before: connection.handler = Encoder
        connection.set_handler(con)
        # after: connection.handler = Encrypter.Connecter
        if already_read:
            con.data_came_in(con, already_read)
        return True

    def close_all(self):
        for c in self.connections.values():
            c.close()
        self.connections = {}

    def ban(self, ip):
        self.banned[ip] = 1

    def pause(self, flag):
        self.paused = flag

# 2fastbt_
    def scan_connections(self):
        self.raw_server.add_task(self.scan_connections, 2)
        n_helper_con = 0
        n_helper_choked_con = 0
        n_helper_not_interested_con = 0
        n_coordinator_con = 0
        n_coordinator_choked_con = 0
        n_coordinator_not_interested_con = 0
        n_control_con = 0
        helper_cons = []
        coordinator_cons = []
        try:
            for c in self.connections.values():
                if c.is_control_con():
                    n_control_con += 1
                if c.is_helper_con():
                    n_helper_con += 1
                    helper_cons.append(c.connection.socket.fileno())
                    try:
                        con = self.connecter.connections[c]
                        if con.download is not None:
                            if con.download.is_choked():
                                n_helper_choked_con += 1
                            if not con.download.is_interested():
                                n_helper_not_interested_con += 1
                    except:
                        get_logger().log(2, "encrypter.scan_connections EXCEPTION")
                if c.is_coordinator_con():
                    n_coordinator_con += 1
                    coordinator_cons.append(c.connection.socket.fileno())
                    try:
                        con = self.connecter.connections[c]
                        if con.upload is not None:
                            if con.upload.is_choked():
                                n_coordinator_choked_con += 1
                            if not con.upload.is_interested():
                                n_coordinator_not_interested_con += 1
                    except:
                        get_logger().log(2, "encrypter.scan_connections EXCEPTION")
                    
            get_logger().log(2, "encrypter.scan_connections n_control_con: '" + 
                str(n_control_con) + " n_helper_con: '" + str(n_helper_con) + 
                "' n_helper_choked_con: '" + str(n_helper_choked_con) + 
                "' n_helper_not_interested_con: '" + str(n_helper_not_interested_con) + 
                "' n_coordinator_con: '" + str(n_coordinator_con) + 
                "' n_coordinator_choked_con: '" + str(n_coordinator_choked_con) +
                "' n_coordinator_not_interested_con: '" + str(n_coordinator_not_interested_con) +
                "' n_all_con: '" + str(len(self.connections)) + 
                "' helper_cons: '" + str(helper_cons) +
                "' coordinator_cons: '" + str(coordinator_cons) + "'")
        except:
            pass
# _2fastbt