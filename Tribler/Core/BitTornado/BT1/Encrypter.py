# Written by Bram Cohen, Pawel Garbacki
# Updated by George Milescu
# see LICENSE.txt for license information

import sys
from base64 import b64encode
from cStringIO import StringIO
from binascii import b2a_hex
from socket import error as socketerror
from urllib import quote
from struct import unpack
from time import time
from traceback import print_exc

from Tribler.Core.BitTornado.BT1.MessageID import protocol_name,option_pattern
from Tribler.Core.BitTornado.BT1.convert import toint
from Tribler.Core.Statistics.Status.Status import get_status_holder
from threading import Lock

try:
    True
except:
    True = 1
    False = 0

DEBUG = False

if sys.platform == 'win32':
    # Arno: On windows XP SP2 there is a limit on "the number of concurrent, 
    # incomplete outbound TCP connection attempts. When the limit is reached, 
    # subsequent connection attempts are put in a queue and resolved at a fixed 
    # rate so that there are only a limited number of connections in the 
    # incomplete state. During normal operation, when programs are connecting 
    # to available hosts at valid IP addresses, no limit is imposed on the 
    # number of connections in the incomplete state. When the number of 
    # incomplete connections exceeds the limit, for example, as a result of 
    # programs connecting to IP addresses that are not valid, connection-rate 
    # limitations are invoked, and this event is logged." 
    # Source: http://go.microsoft.com/fwlink/events.asp and fill in 
    # Product: "Windos Operating System"
    # Event: 4226
    # Which directs to:
    # http://www.microsoft.com/technet/support/ee/transform.aspx?ProdName=Windows%20Operating%20System&ProdVer=5.2&EvtID=4226&EvtSrc=Tcpip&LCID=1033
    #
    # The ABC/BitTornado people felt the need to therefore impose a rate limit
    # themselves. Normally, I would be against this, because the kernel usually
    # does a better job at this than some app programmers. But here it makes 
    # somewhat sense because it appears that when the Win32 "connection-rate 
    # limitations" are triggered, this causes socket timeout
    # errors. For ABC/BitTornado this should not be a big problem, as none of 
    # the TCP connections it initiates are really vital that they proceed 
    # quickly.
    #
    # For Tribler, we have one very important TCP connection at the moment,
    # that is when the VideoPlayer/VLC tries to connect to our HTTP-based
    # VideoServer on 127.0.0.1 to play the video. We have actually seen these
    # connections timeout when we set MAX_INCOMPLETE to > 10.
    #
    # So we keep this app-level rate limit mechanism FOR NOW and add a security
    # margin. To support our SwarmPlayer that wants quick startup of many
    # connections we decrease the autoclosing timeout, such that bad conns
    # get removed from this rate-limit admin faster. 
    #
    # Windows die die die.
    #
    # Update, 2009-10-21:
    # This limiting has been disabled starting Vista SP2 and beyond:
    # http://support.microsoft.com/kb/969710
    #
    # Go Vista?! 
    #

    # [E1101] Module 'sys' has no 'getwindowsversion' member
    # pylint: disable-msg=E1101
    winvertuple = sys.getwindowsversion()
    # pylint: enable-msg=E1101
    spstr = winvertuple[4]
    
    #Niels: Windows 7 is 6.1, should also not impose socket limit
    if winvertuple[0] == 5 or (winvertuple[0] == 6 and winvertuple[1] == 0 and spstr < "Service Pack 2"):
        MAX_INCOMPLETE = 8 # safety margin. Even 9 gives video socket timeout, 10 is official limit
    else:
        #Niels: Opening 1024 connections will cause problems with all kinds of firewalls etc, reducing to 48
        MAX_INCOMPLETE = 12
else:
    MAX_INCOMPLETE = 12
MAX_HISTORY_INCOMPLETE = max(MAX_INCOMPLETE*10, 320)  # allow X connections to be initiated every 60s

AUTOCLOSE_TIMEOUT = 15 # secs. Setting this to e.g. 7 causes Video HTTP timeouts

def make_readable(s):
    if not s:
        return ''
    if quote(s).find('%') >= 0:
        return b2a_hex(s).upper()
    return '"'+s+'"'

def show(s):
    return b2a_hex(s)

class IncompleteCounter:
    __single = None
    
    def __init__(self):
        if IncompleteCounter.__single:
            raise RuntimeError, "IncompleteCounter is singleton"
        IncompleteCounter.__single = self
        
        self.lock = Lock()
        
        self.c = 0
        self.historyc = 0
        self.taskQueue = None
        
    def getInstance(*args, **kw):
        if IncompleteCounter.__single is None:
            IncompleteCounter(*args, **kw)
        return IncompleteCounter.__single
    getInstance = staticmethod(getInstance)
        
    def increment(self):
        try:
            self.lock.acquire()
        
            self.c += 1
            self.historyc += 1
            
        finally:
            self.lock.release()
        
    def decrement(self):
        try:
            self.lock.acquire()
            self.c -= 1
        
            if self.taskQueue:
                self.taskQueue.add_task(self.__decrementHistory, 60)
            else:
                self.historyc -= 1
        finally:
            self.lock.release()
    
    def __decrementHistory(self):
        try:
            self.lock.acquire()
            self.historyc -= 1
            
        finally:
            self.lock.release()
        
    def toomany(self, history = True):
        #print >>sys.stderr,"IncompleteCounter: c",self.c
        return self.c >= MAX_INCOMPLETE or (history and self.historyc >= MAX_HISTORY_INCOMPLETE)
    
    def getstats(self):
        return self.c, MAX_INCOMPLETE, self.historyc, MAX_HISTORY_INCOMPLETE

# Arno: This is a global counter!!!!
incompletecounter = IncompleteCounter.getInstance()

# header, reserved, download id, my id, [length, message]

class Connection:
    def __init__(self, Encoder, connection, id, ext_handshake = False, 
                  locally_initiated = None, dns = None):
        self.Encoder = Encoder
        self.connection = connection    # SocketHandler.SingleSocket
        self.connecter = Encoder.connecter
        self.id = id
        self.readable_id = make_readable(id)
        if locally_initiated is not None:
            self.locally_initiated = locally_initiated
        else:
            self.locally_initiated = (id != None)
        self.complete = False
        self.keepalive = lambda: None
        self.closed = False
        self.buffer = StringIO()
# overlay        
        self.dns = dns
        self.support_extend_messages = False
        self.connecter_conn = None
# _overlay
        self.support_merklehash= False
        self.na_want_internal_conn_from = None
        self.na_address_distance = None
        
        if self.Encoder.raw_server and not incompletecounter.taskQueue:
            incompletecounter.taskQueue = self.Encoder.raw_server  
        
        if self.locally_initiated:
            incompletecounter.increment()
# 2fastbt_
        self.create_time = time()
# _2fastbt
        
        if self.locally_initiated or ext_handshake:
            if DEBUG:
                print >>sys.stderr,"Encoder.Connection: writing protname + options + infohash"
            self.connection.write(chr(len(protocol_name)) + protocol_name + 
                option_pattern + self.Encoder.download_id)
        if ext_handshake:
            if DEBUG:
                print >>sys.stderr,"Encoder.Connection: writing my peer-ID"
            self.connection.write(self.Encoder.my_id)
            self.next_len, self.next_func = 20, self.read_peer_id
        else:
            self.next_len, self.next_func = 1, self.read_header_len
        self.Encoder.raw_server.add_task(self._auto_close, AUTOCLOSE_TIMEOUT)
        
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

    def supports_extend_messages(self):
        return self.support_extend_messages

    def set_options(self, s):
# overlay_
        r = unpack("B", s[5])
        if r[0] & 0x10:    # left + 43 bit
            self.support_extend_messages = True
            if DEBUG:
                print >>sys.stderr,"encoder: Peer supports EXTEND"
        if r[0] & 0x20:    # left + 42 bit
            self.support_merklehash= True
            if DEBUG:
                print >>sys.stderr,"encoder: Peer supports Merkle hashes"
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
            print >>sys.stderr,"encoder: Reserved bits:", show(s)
            print >>sys.stderr,"encoder: Reserved bits=", show(option_pattern)
        self.set_options(s)
        return 20, self.read_download_id

    def read_download_id(self, s):
        if s != self.Encoder.download_id:
            return None
        if not self.locally_initiated:
            self.Encoder.connecter.external_connection_made += 1
            self.connection.write(chr(len(protocol_name)) + protocol_name + option_pattern + self.Encoder.download_id + self.Encoder.my_id)

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
        if DEBUG:
            print >>sys.stderr,"Encoder.Connection: read_peer_id"

        if not self.id:    # remote init or local init without remote peer's id or remote init
            self.id = s
            self.readable_id = make_readable(s)
        
        else:    # local init with remote id
            if s != self.id:
                if DEBUG:
                    print >>sys.stderr,"Encoder.Connection: read_peer_id: s != self.id, returning None"
                return None
        self.complete = self.Encoder.got_id(self)
        
        if DEBUG:
            print >>sys.stderr,"Encoder.Connection: read_peer_id: complete is",self.complete
        
        
        if not self.complete:
            if DEBUG:
                print >>sys.stderr,"Encoder.Connection: read_peer_id: self not complete!!!, returning None"
            return None
        if self.locally_initiated:
            self.connection.write(self.Encoder.my_id)
            
            hittingLimit = incompletecounter.toomany()
            incompletecounter.decrement()
            
            # Arno: open new conn from queue if at limit. Faster than RawServer task
            # Niels: in order to maintain fairness between 'threads' use rawserver if incompletecounter was hitting the limit
            if hittingLimit:
                self.Encoder.raw_server.add_task(lambda: self.Encoder._start_connection_from_queue(sched=False), 1.0)
            else:
                self.Encoder._start_connection_from_queue(sched=False)
            
        c = self.Encoder.connecter.connection_made(self)
        self.keepalive = c.send_keepalive
        return 4, self.read_len

    def read_len(self, s):
        l = toint(s)
        if l > self.Encoder.max_len:
            return None
        return l, self.read_message

    def read_message(self, s):
        if s != '':
            self.connecter.got_message(self, s)
        #else:
        #    print >>sys.stderr,"encoder: got keepalive from",s.getpeername()
        return 4, self.read_len

    def read_dead(self, s):
        return None

    def _auto_close(self):
        if not self.complete:
            if DEBUG:
                print >>sys.stderr,"encoder: autoclosing ",self.get_myip(),self.get_myport(),"to",self.get_ip(),self.get_port()

            self.Encoder._event_reporter.create_and_add_event("connection-timeout", [b64encode(self.Encoder.connecter.infohash), self.get_ip(), self.get_port()])

            # RePEX: inform repexer of timeout
            repexer = self.Encoder.repexer
            if repexer and not self.closed:
                try:
                    repexer.connection_timeout(self)
                except:
                    print_exc()
            self.close()

    def close(self,closeall=False):
        if DEBUG:
            print >>sys.stderr,"encoder: closing connection",self.get_ip()
            #print_stack()
        
        if not self.closed:
            self.connection.close()
            self.sever(closeall=closeall)
            

    def sever(self,closeall=False):
        self.closed = True
        if self.Encoder.connections.has_key(self.connection):
            self.Encoder.admin_close(self.connection)
        
        # RePEX: inform repexer of closed connection
        repexer = self.Encoder.repexer
        if repexer and not self.complete:
            try:
                repexer.connection_closed(self)
            except:
                print_exc()
            
        if self.complete:
            self.connecter.connection_lost(self)
            
        elif self.locally_initiated:
            hittingLimit = incompletecounter.toomany()
            incompletecounter.decrement()
            
            # Arno: open new conn from queue if at limit. Faster than RawServer task
            # Niels: in order to maintain fairness between 'threads' use rawserver if incompletecounter was hitting the limit
            if not closeall:
                if hittingLimit:
                    self.Encoder.raw_server.add_task(lambda: self.Encoder._start_connection_from_queue(sched=False), 1.0)
                else:
                    self.Encoder._start_connection_from_queue(sched=False)
            
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
                if DEBUG:
                    print >>sys.stderr,"encoder: function failed",self.next_func
                # Arno, 2011-05-10: Clean up function pointer refs
                self.next_len, self.next_func = 1, self.read_dead
                self.close()
                return
            self.next_len, self.next_func = x

    def connection_flushed(self, connection):
        if self.complete:
            self.connecter.connection_flushed(self)

    def connection_lost(self, connection):
        if self.Encoder.connections.has_key(connection):
            self.sever()

    # NETWORK AWARE
    def na_set_address_distance(self):
        """ Calc address distance. Currently simple: if same /24 then 0
        else 1. TODO: IPv6
        """
        hisip = self.get_ip(real=True)
        myip = self.get_myip(real=True)
        
        a = hisip.split(".")
        b = myip.split(".")
        if a[0] == b[0] and a[1] == b[1] and a[2] == b[2]:
            if DEBUG:
                print >>sys.stderr,"encoder.connection: na: Found peer on local LAN",self.get_ip()
            self.na_address_distance = 0
        else:
            self.na_address_distance = 1
        
    def na_get_address_distance(self):
        return self.na_address_distance
    




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
        self.to_connect = set()
        self.trackertime = None
        self.scheduled_request_new_peers = False
        
        self.paused = False
        if self.config['max_connections'] == 0:
            self.max_connections = 100
        else:
            self.max_connections = self.config['max_connections']
        """
        In r529 there was a problem when a single Windows client 
        would connect to our text-based seeder (i.e. btlaunchmany) 
        with no other clients present. Apparently both the seeder 
        and client would connect to eachother simultaneously, but 
        not end up with a good connection, halting the client.

        Arno, 2006-03-10: Reappears in ~r890, fixed in r892. It 
        appears to be a problem of writing to a nonblocking socket 
        before it signalled it is ready for writing, although the 
        evidence is inconclusive. 

        Arno: 2006-12-15: Reappears in r2319. There is some weird
        socket problem here. Using Python 2.4.4 doesn't solve it.
        The problem I see here is that as soon as we register
        at the tracker, the single seeder tries to connect to
        us. He succeeds, but after a short while the connection
        appears to be closed by him. We then wind up with no
        connection at all and have to wait until we recontact
        the tracker.

        My workaround is to refuse these initial connections from
        the seeder and wait until I've started connecting to peers
        based on the info I got from the tracker before accepting
        remote connections.
        
        Arno: 2007-02-16: I think I finally found it. The Tribler 
        tracker (BitTornado/BT1/track.py) will do a NAT check
        (BitTornado/BT1/NATCheck) by default, which consists of
        initiating a connection and then closing it after a good 
        BT handshake was received.
        
        The solution now is to make sure we check IP and port to
        identify existing connections. I already added that 2006-12-15,
        so I just removed the restriction on initial connections, 
        which are superfluous.
        """
        self.rerequest = None
        # ProxyService_
        #
        self.proxy = None
        #
        # _ProxyService        

        # hack: we should not import this since it is not part of the
        # core nor should we import here, but otherwise we will get
        # import errors
        #
        # _event_reporter stores events that are logged somewhere...
        # from Tribler.Core.Statistics.StatusReporter import get_reporter_instance
        self._event_reporter = get_status_holder("LivingLab")

        # the addresses that have already been reported
        self._known_addresses = {}

        schedulefunc(self.send_keepalives, keepalive_delay)
        
        # RePEX: added repexer field.
        # Note: perhaps call it observer in the future and make the 
        # download engine more observable?
        self.repexer = None
        
    def send_keepalives(self):
        self.schedulefunc(self.send_keepalives, self.keepalive_delay)
        if self.paused:
            return
        for c in self.connections.values():
            c.keepalive()

    def start_connections(self, dnsidlist):
        """ Arno: dnsidlist is a list of tuples (dns,id) where dns is a (ip,port) tuple
        and id is apparently always 0. It must be unequal to None at least,
        because Encrypter.Connection used the id to see if a connection is
        locally initiated?! """
        
        if DEBUG:
            print >>sys.stderr,"encoder: adding",len(dnsidlist),"peers to queue, current len",len(self.to_connect)
        wasempty = not self.to_connect
        
        # all reported addresses are stored in self._known_addresses
        # to prevent duplicated addresses being send
        new_addresses = []
        known_addresses = self._known_addresses
        for dns, _ in dnsidlist:
            address = "%s:%s" % dns
            if not address in known_addresses:
                known_addresses[address] = True
                new_addresses.append(address)

        if new_addresses:
            self._event_reporter.create_and_add_event("known-hosts", [b64encode(self.connecter.infohash), ";".join(new_addresses)])

        # prevent 'to much' memory usage
        if len(known_addresses) > 2500:
            known_addresses.clear()
        
        self.to_connect.update(dnsidlist)
        if wasempty:
            self.raw_server.add_task(self._start_connection_from_queue)
        
        # make sure addrs from various sources, like tracker, ut_pex and DHT are mixed
        # TODO: or not? For Tribler Supported we may want the tracker to
        # be more authoritative, such that official seeders found fast. Nah.
        
        #random.shuffle(self.to_connect) 
        #Jelle: Since objects are already placed in the Set in pseudo random order, they don't have to 
        # be shuffled (and a Set cannot be shuffled).
        
        self.trackertime = time() #update trackertime

    def _start_connection_from_queue(self,sched=True):
        try:
            if not self.to_connect:
                return
            
            if self.connecter.external_connection_made:
                max_initiate = self.config['max_initiate']
            else:
                max_initiate = int(self.config['max_initiate']*1.5)
            cons = len(self.connections)
            
            #Niels: if we're seeding then call incompletecounter with history = True, else skip history limit  
            seeding = False
            try:
                seeding = self.connecter.downloader.storage.amount_left == 0
            except:
                pass
            
            if DEBUG:
                print >>sys.stderr,"encoder: conns",cons,"max conns",self.max_connections,"max init",max_initiate
            
            if cons >= self.max_connections or cons >= max_initiate:
                delay = 60.0
                
            elif self.paused or incompletecounter.toomany(seeding):
                delay = 1.0
                
            else:
                delay = 0.0
                dns, id = self.to_connect.pop()
                self.start_connection(dns, id)
                
            if self.to_connect and sched:
                if DEBUG:
                    print >>sys.stderr,"encoder: start_from_queue delay",delay
                self.raw_server.add_task(self._start_connection_from_queue, delay)
        except:
            print_exc()
            raise

    def start_connection(self, dns, id, forcenew = False):
        """ Locally initiated connection """
        if DEBUG:
            print >>sys.stderr,"encoder: start_connection:",dns
            print >>sys.stderr,"encoder: start_connection: qlen",len(self.to_connect),"nconns",len(self.connections),"maxi",self.config['max_initiate'],"maxc",self.config['max_connections']
        
        if ( self.paused
             or len(self.connections) >= self.max_connections
             or id == self.my_id
             or self.banned.has_key(dns[0]) ) and not forcenew:
            if DEBUG:
                print >>sys.stderr,"encoder: start_connection: we're paused or too busy"
            return True
        for v in self.connections.values():    # avoid duplicated connection from a single ip
            if v is None:
                continue
            if id and v.id == id and not forcenew:
                if DEBUG:
                    print >>sys.stderr,"encoder: start_connection: already connected to peer",`id`
                return True
            ip = v.get_ip(True)
            port = v.get_port(False)
            
            if DEBUG:
                print >>sys.stderr,"encoder: start_connection: candidate",ip,port,"want",dns[0],dns[1]

            if self.config['security'] and ip != 'unknown' and ip == dns[0] and port == dns[1] and not forcenew:
                if DEBUG:
                    print >>sys.stderr,"encoder: start_connection: using existing",ip,"want port",dns[1],"existing port",port,"id",`id`
                return True
        try:
            if DEBUG:
                print >>sys.stderr,"encoder: start_connection: Setting up new to peer", dns,"id",`id`
            c = self.raw_server.start_connection(dns)
            con = Connection(self, c, id, dns = dns)
            self.connections[c] = con
            c.set_handler(con)
        except socketerror:
            if DEBUG:
                print >>sys.stderr,"Encoder.connection failed"
            return False
        return True

    def _start_connection(self, dns, id):
        def foo(self=self, dns=dns, id=id):
            self.start_connection(dns, id)
       
        self.schedulefunc(foo, 0)

    def got_id(self, connection):
        """ check if the connection can be accepted """
        
        if connection.id == self.my_id:
            # NETWORK AWARE
            ret = self.connecter.na_got_loopback(connection)
            if DEBUG:
                print >>sys.stderr,"encoder: got_id: connection to myself? keep",ret
            if ret == False:
                self.connecter.external_connection_made -= 1
            return ret
        
        ip = connection.get_ip(True)
        port = connection.get_port(False)
        
        # NETWORK AWARE
        connection.na_set_address_distance()
        
        if self.config['security'] and self.banned.has_key(ip):
            if DEBUG:
                print >>sys.stderr,"encoder: got_id: security ban on IP"
            return False
        for v in self.connections.values():
            if connection is not v:
                # NETWORK AWARE
                if DEBUG:
                    print >>sys.stderr,"encoder: got_id: new internal conn from peer? ids",connection.id,v.id
                if connection.id == v.id:
                    if DEBUG:
                        print >>sys.stderr,"encoder: got_id: new internal conn from peer? addrs",v.na_want_internal_conn_from,ip
                    if v.na_want_internal_conn_from == ip:
                        # We were expecting a connection from this peer that shares
                        # a NAT with us via the internal network. This is it.
                        self.connecter.na_got_internal_connection(v,connection)
                        return True  
                    elif v.create_time < connection.create_time:
                        if DEBUG:
                            print >>sys.stderr,"encoder: got_id: create time bad?!"
                    return False
                # don't allow multiple connections from the same ip if security is set.
                if self.config['security'] and ip != 'unknown' and ip == v.get_ip(True) and port == v.get_port(False):
                    print >>sys.stderr,"encoder: got_id: closing duplicate connection"
                    v.close()
        return True

    def external_connection_made(self, connection):
        """ Remotely initiated connection """
        if DEBUG:
            print >>sys.stderr,"encoder: external_conn_made",connection.get_ip()
        if self.paused or len(self.connections) >= self.max_connections:
            print >>sys.stderr,"encoder: external_conn_made: paused or too many"
            connection.close()
            return False
        con = Connection(self, connection, None)
        self.connections[connection] = con
        connection.set_handler(con)
        return True

    def externally_handshaked_connection_made(self, connection, options, msg_remainder):
        if DEBUG:
            print >>sys.stderr,"encoder: external_handshaked_conn_made",connection.get_ip()
        # 2fastbt_
        if self.paused or len(self.connections) >= self.max_connections:
            connection.close()
            return False
        # _2fastbt
        
        con = Connection(self, connection, None, True)
        con.set_options(options)
        # before: connection.handler = Encoder
        # Don't forget to count the external conns!
        self.connections[connection] = con
        connection.set_handler(con)
        # after: connection.handler = Encrypter.Connecter

        if msg_remainder:
            con.data_came_in(con, msg_remainder)
        return True

    def close_all(self):
        if DEBUG:
            print >>sys.stderr,"encoder: closing all connections"
        copy = self.connections.values()[:]
        for c in copy:
            c.close(closeall=True)
        self.connections = {}

    def ban(self, ip):
        self.banned[ip] = 1

    def pause(self, flag):
        self.paused = flag

    # ProxyService_
    def set_proxy(self, proxy):
        """ Sets the current proxy.
        
        Called from download_bt1.py
        
        @param proxy: the proxy object associated with the current download
        """
        self.proxy = proxy
    # _ProxyService    

    def set_rerequester(self,rerequest):
        self.rerequest = rerequest

    def admin_close(self,conn):
        del self.connections[conn]
        
        now = time()
        remaining_connections = len(self.connections) + len(self.to_connect)
        
        if DEBUG:
            if self.trackertime:
                print >>sys.stderr,"encoder: admin_close: now-tt is", int(now-self.trackertime), "remaining connections", remaining_connections
            else:
                print >>sys.stderr,"encoder: admin_close: remaining connections", remaining_connections
        
        if remaining_connections == 0 and self.trackertime and not self.scheduled_request_new_peers:
            self.scheduled_request_new_peers = True
            
            seeding = self.connecter.downloader.storage.amount_left == 0
            if seeding:
                schedule_refresh_in = 120
            else:
                #no more peers to connect to :(, schedule a refresh
                schedule_refresh_in = max(60, int(300 - (now - self.trackertime)))
            
            if DEBUG:
                print >>sys.stderr,"encoder: admin_close: want new peers in", schedule_refresh_in, "s"
            
            def request_new():
                #check if we still have no connections...
                remaining_connections = len(self.connections) + len(self.to_connect)
                if remaining_connections == 0:
                    self.rerequest.encoder_wants_new_peers()
                
                self.scheduled_request_new_peers = False
            
            if schedule_refresh_in <= 0:
                request_new()
            else:
                self.raw_server.add_task(request_new, schedule_refresh_in)

            #reset trackertime
            self.trackertime = None
