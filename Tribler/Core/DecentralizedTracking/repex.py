# Written by Raynor Vliegendhart
# see LICENSE.txt for license information
import sys
import os
from time import time as ts_now
from random import shuffle
from traceback import print_exc,print_stack
from threading import RLock,Condition,Event,Thread,currentThread
from binascii import b2a_hex

from Tribler.Core.simpledefs import *
from Tribler.Core.exceptions import *
from Tribler.Core.osutils import *
from Tribler.Core.DecentralizedTracking.ut_pex import check_ut_pex_peerlist

DEBUG = False
REPEX_DISABLE_BOOTSTRAP = False

# TODO: Move constants to simpledefs or make it configurable?
REPEX_SWARMCACHE_SIZE = 4      # Number of peers per SwarmCache table
REPEX_STORED_PEX_SIZE = 5      # Number of PEX addresses per peer per SwarmCache
REPEX_PEX_MINSIZE = 1          # minimum number of peers in PEX message before considered a good peer
                               # TODO: Currently set at 1, but what if a swarm consists of 1 user?
REPEX_INTERVAL = 20*60         # Refresh SwarmCache every 20 minutes.
REPEX_MIN_INTERVAL = 5*60      # Minimum time between attempts to prevent starvation in cases like continuous failures.
REPEX_PEX_MSG_MAX_PEERS = 200  # only consider the first 200 peers (Opera10 sends its *whole* neighborhood set)
REPEX_LISTEN_TIME = 50         # listen max. 50 seconds for PEX message 
REPEX_INITIAL_SOCKETS = 4      # number of sockets used initially
REPEX_MAX_SOCKETS = 8          # max number of sockets when all initial peers are checked or after the first failure has occured
REPEX_SCAN_INTERVAL = 1*60     # Scan for stopped Downloads every minute.


# Testing values
# REPEX_INTERVAL = 10
# REPEX_SCAN_INTERVAL = 30
# REPEX_MIN_INTERVAL = 60
# REPEX_DISABLE_BOOTSTRAP = True

class RePEXerInterface:
    """
    Describes the RePEXer interface required by the SingleDownload and
    the download engine classes.
    """
    
    def repex_ready(self, infohash, connecter, encoder, rerequester):
        """
        Called by network thread. SingleDownload calls this method when 
        everything is set up.
        @param infohash Infohash of download.
        @param connecter Connecter (Connecter.py from the download engine).
        @param encoder Encoder (Encrypter.py from the download engine).
        @param rerequester Rerequester (Rerequester.py from the download engine)
        """
    def repex_aborted(self, infohash, dlstatus=None):
        """
        Called by network thread. SingleDownload calls this method when 
        the download is stopped or restarted, interrupting the RePEX mode.
        @param infohash Infohash of download.
        @param dlstatus Status of the download when the RePEX mode was
        interrupted, or None if unknown.
        """
    def rerequester_peers(self, peers):
        """
        Called by network thread. Rerequester (accessible via Encoder) 
        schedules this method call when peers have arrived.
        @param peers [(dns,id)] or None in case of error.
        """
    def connection_timeout(self, connection):
        """
        Called by network thread. Encoder calls this when a connection
        was not established within Encrypter's autoclose timeout.
        @param connection Encrypter.Connection
        """
    def connection_closed(self, connection):
        """
        Called by network thread. Encoder or Connecter calls this when 
        a connection was closed, either locally or remotely. It is also 
        called right after a timeout. The RePEXer should maintain state 
        on connections it has started.
        @param connection Encrypter.Connection or Connecter.Connection
        """

    def connection_made(self, connection, ext_support):
        """
        Called by network thread. Connecter calls this when a connection
        was established.
        @param connection Connecter.Connection
        @param ext_support Flag indicating whether the connection supports
        the extension protocol.
        """
    
    def got_extend_handshake(self, connection, version=None):
        """
        Called by network thread. Connecter calls this when a extended
        handshake is received. Use connection's supports_extend_msg(msg_name)
        method to figure out whether a message is supported.
        @param connection Connecter.Connection
        @param version Version string or None if not available.
        """

    def got_ut_pex(self, connection, d):
        """
        Called by network thread. Connecter calls this when a PEX message is 
        received.
        @param connection Connecter.Connection
        @param d The PEX dictionary containing 'added' and 'added.f'
        """

def c2infohash_dns(connection):
    """
    Utility function to retrieve the infohash and dns of a Encrypter or
    Connecter Connection.
    """
    # luckily the same interface
    infohash = connection.connecter.infohash 
    #dns = (connection.get_ip(True), connection.get_port(False)) # buggy, get_port might return -1
    if hasattr(connection, 'got_ut_pex'):
        encr_connection = connection.connection
    else:
        encr_connection = connection
    dns = encr_connection.dns
    return infohash, dns

def swarmcache_ts(swarmcache):
    """
    Computes the timestamp of a SwarmCache or None if SwarmCache is empty.
    """
    ts = None
    if swarmcache:
        ts = max(v['last_seen'] for v in swarmcache.values())
    # Currently the greatest timestamp is chosen as *the*
    # timestamp of a SwarmCache. TODO: is this ok?
    return ts

class RePEXer(RePEXerInterface):
    """
    A RePEXer is associated with a single SingleDownload. While the interface 
    is set up in a way that allows a RePEXer to be associated with multiple 
    SingleDownloads, it is easier to maintain state when one RePEXer is created
    per Download instance.  
    """
    # (Actually, the interface does not quite work that way... when the 
    # rerequester delivers peers, the RePEXer cannot tell for which 
    # Download they are meant)
    
    _observers = []
    lock = RLock() # needed to atomically update observers list
        
    @classmethod
    def attach_observer(cls, observer):
        """
        Attaches an observer to observe all RePEXer instances.
        
        @param observer RePEXerStatusCallback.
        """
        cls.lock.acquire()   
        try:
            cls._observers.append(observer)
        finally:
            cls.lock.release()
    
    @classmethod
    def detach_observer(cls, observer):
        """
        Detaches a previously attached observer.
        
        @param observer RePEXerStatusCallback.
        """
        cls.lock.acquire()   
        try:
            cls._observers.remove(observer)
        finally:
            cls.lock.release()
    
    def __init__(self, infohash, swarmcache):
        """
        Constructs a RePEXer object, associated with a download's infohash. 
        
        @param infohash Infohash of download.
        @param swarmcache Previous SwarmCache to check, which is a dict 
        mapping dns to a dict with at least 'last_seen' and 'pex' keys.
        """
        # Note: internally in this class we'll use the name 'peertable',
        # but the outside world calls it more appropiately the SwarmCache.
        self.infohash = infohash
        self.connecter = None
        self.encoder = None
        self.rerequest = None
        
        self.starting_peertable = swarmcache
        self.final_peertable = None
        self.to_pex = []
        self.active_sockets = 0
        self.max_sockets = REPEX_INITIAL_SOCKETS
        self.attempted = set()
        self.live_peers = {} # The pex-capable and useful peers.
        
        # The following two sets are usable in a debugging/logging context
        self.bt_connectable = set() # sent BT handshake
        self.bt_ext = set() # supported ext
        self.bt_pex = set() # supported ut_pex
        
        self.dns2version = {} # additional data
        
        self.onlinecount = 0 # number of initial peers found online
        self.shufflecount = 0 # number of peers in peertable unconnectable or useless
        # sum of these two must become len(peertable) since we prefer the initial peertable
        
        self.datacost_bandwidth_keys = ['no_pex_support', 'no_pex_msg', 'pex', 'other']
        self.datacost_counter_keys = ['connection_attempts','connections_made','bootstrap_peers','pex_connections']
        self.datacost = {}
        self.datacost['no_pex_support'] = (0,0) # down,up
        self.datacost['no_pex_msg'] = (0,0) # down,up
        self.datacost['pex'] = (0,0) # down,up
        self.datacost['other'] = (0,0) # down,up
        self.datacost['connection_attempts'] = 0 # number of times connect() successfully created a connection 
        self.datacost['connections_made'] = 0 # number of times connection_made() was called
        self.datacost['bootstrap_peers'] = 0 # total number of peers given to rerequester_peers()
        self.datacost['pex_connections'] = 0 # total number of connections that sent a PEX reply
        
        self.requesting_tracker = False # needed to interact with Rerequester in case of failure
        self.bootstrap_counter = 0 # how often did we call bootstrap()?
        
        self.is_closing = False # flag so that we only call close_all once
        self.done = False # flag so we know when we're done or are aborted
        self.aborted = False # flag so we know the exact done-reason
        self.ready = False # flag so we know whether repex_ready has been called
        self.ready_ts = -1 # for logging purposes, store the time repex_ready event was triggered
        self.end_ts = -1 # for logging purposes, store the time done or aborted was sent
        
        # Added robustness, check whether received SwarmCache is not None
        if self.starting_peertable is None:
            print >>sys.stderr, 'RePEXer: __init__: swarmcache was None, defaulting to {}'
            self.starting_peertable = {}
            
    
    #
    # RePEXerInterface
    #
    def repex_ready(self, infohash, connecter, encoder, rerequester):
        if infohash != self.infohash:
            print >>sys.stderr, "RePEXer: repex_ready: wrong infohash:", b2a_hex(infohash)
            return
        if self.done:
            print >>sys.stderr, "RePEXer: repex_ready: already done"
            return
        if DEBUG:
            print >>sys.stderr, "RePEXer: repex_ready:", b2a_hex(infohash)
        self.ready = True
        self.ready_ts = ts_now()
        self.connecter = connecter
        self.encoder = encoder
        self.rerequest = rerequester
        
        # Fill connect queue
        self.to_pex = self.starting_peertable.keys()
        self.max_sockets = REPEX_INITIAL_SOCKETS
        
        # We'll also extend the queue with all peers from the pex messages
        # TODO: investigate whether a more sophisticated queueing scheme is more appropiate
        # For example, only fill the queue when countering a failure
        for dns in self.starting_peertable:
            self.to_pex.extend([pexdns for pexdns,flags in self.starting_peertable[dns].get('pex',[])])
        self.connect_queue()
        
        
    def repex_aborted(self, infohash, dlstatus):
        if self.done:
            return
        if infohash != self.infohash:
            print >>sys.stderr, "RePEXer: repex_aborted: wrong infohash:", b2a_hex(infohash)
            return
        if DEBUG:
            if dlstatus is None:
                status_string = str(None)
            else:
                status_string = dlstatus_strings[dlstatus]
            print >>sys.stderr, "RePEXer: repex_aborted:", b2a_hex(infohash),status_string
        self.done = True
        self.aborted = True
        self.end_ts = ts_now()
        for observer in self._observers:
            observer.repex_aborted(self, dlstatus)
        # Note that we do not need to close active connections
        #  1) If repex_aborted is called because the download was stopped, 
        #     the connections are closed automatically.
        #  2) If repex_aborted is called because the download was restarted,
        #     open connections are actually useful. 
        
    def rerequester_peers(self, peers):
        self.requesting_tracker = False
        if peers is not None:
            numpeers = len(peers)
        else:
            numpeers = -1
        if DEBUG:
            print >>sys.stderr, "RePEXer: rerequester_peers: received %s peers" % numpeers
        if numpeers > 0:
            self.to_pex.extend([dns for dns,id in peers])
            self.datacost['bootstrap_peers'] += numpeers
        self.connect_queue()
        
 
    def connection_timeout(self, connection):
        infohash, dns = c2infohash_dns(connection)
        if infohash != self.infohash:
            return
        if DEBUG:
            print >>sys.stderr, "RePEXer: connection_timeout: %s:%s" % dns
 
    def connection_closed(self, connection):
        self.active_sockets -= 1
        if self.active_sockets < 0:
            self.active_sockets = 0
        infohash, dns = c2infohash_dns(connection)
        c = None # Connecter.Connection
        if hasattr(connection, 'got_ut_pex'):
            c = connection
            connection = c.connection # Encrypter.Connection
        if infohash != self.infohash:
            return
        if DEBUG:
            print >>sys.stderr, "RePEXer: connection_closed: %s:%s" % dns
        
        singlesocket = connection.connection
        
        # Update costs and determine success
        success = False
        costtype = 'other'
        if c is not None:
            if c.pex_received > 0:
                costtype = 'pex'
                success = True
            elif not c.supports_extend_msg('ut_pex'):
                costtype = 'no_pex_support'
            elif c.pex_received == 0:
                costtype = 'no_pex_msg'
            
        if costtype:
            d, u = self.datacost[costtype]
            d += singlesocket.data_received
            u += singlesocket.data_sent
            self.datacost[costtype] = (d,u)
        
        # If the peer was in our starting peertable, update online/shuffle count
        if dns in self.starting_peertable:
            if success:
                self.onlinecount += 1
                self.live_peers[dns]['prev'] = True
            else:
                self.shufflecount += 1
                #self.to_pex.extend([pexdns for pexdns,flags in self.starting_peertable[dns]['pex']])
                # TODO: see repex_ready for now
        
        # Boost on failure of initial peer or when all initial peers are checked
        if (dns in self.starting_peertable and not success) or self.initial_peers_checked():
            self.max_sockets = REPEX_MAX_SOCKETS 
        
        # always try to connect
        self.connect_queue()
    
    def connection_made(self, connection, ext_support):
        infohash, dns = c2infohash_dns(connection)
        if infohash != self.infohash:
            return
        if DEBUG:
            print >>sys.stderr, "RePEXer: connection_made: %s:%s ext_support = %s" % (dns + (ext_support,))
        self.datacost['connections_made'] += 1
        self.bt_connectable.add(dns)
        if ext_support:
            self.bt_ext.add(dns)
            # Start timer on Encryption.Connection
            def auto_close(connection = connection.connection, dns=dns):
                if not connection.closed:
                    if DEBUG:
                        print >>sys.stderr, "RePEXer: auto_close: %s:%s" % dns
                    try:
                        # only in rare circumstances
                        # (like playing around in the REPL which is running in a diff. thread)
                        # an Assertion is thrown.
                        connection.close()
                    except AssertionError, e:
                        if DEBUG:
                            print >>sys.stderr, "RePEXer: auto_close:", `e`
                        self.connection_closed(connection)
            self.connecter.sched(auto_close, REPEX_LISTEN_TIME)
        else:
            connection.close()
    
    def got_extend_handshake(self, connection, version=None):
        infohash, dns = c2infohash_dns(connection)
        ut_pex_support = connection.supports_extend_msg('ut_pex')
        if infohash != self.infohash:
            return
        if DEBUG:
            print >>sys.stderr, "RePEXer: got_extend_handshake: %s:%s version = %s ut_pex_support = %s" % (dns + (`version`,ut_pex_support ))
        if ut_pex_support:
            self.bt_pex.add(dns)
        else:
            connection.close()
        self.dns2version[dns] = version
    
    def got_ut_pex(self, connection, d):
        infohash, dns = c2infohash_dns(connection)
        is_tribler_peer = connection.is_tribler_peer()
        added = check_ut_pex_peerlist(d,'added')[:REPEX_PEX_MSG_MAX_PEERS]
        addedf = map(ord, d.get('addedf',[]))[:REPEX_PEX_MSG_MAX_PEERS]
        addedf.extend( [0]*(len(added)-len(addedf)) )
        IS_SEED = 2
        IS_SAME = 4
        if infohash != self.infohash:
            return
        if DEBUG:
            print >>sys.stderr, "RePEXer: got_ut_pex: %s:%s pex_size = %s" % (dns + (len(added),))
        
        # Remove bad IPs like 0.x.x.x (often received from Transmission peers)
        for i in range(len(added)-1,-1,-1):
            if added[i][0].startswith('0.'):
                added.pop(i)
                addedf.pop(i)
        
        # only store peer when sufficiently connected
        if len(added) >= REPEX_PEX_MINSIZE:
            # Clear flag IS_SAME if it was not a Tribler peer
            if not is_tribler_peer:
                addedf = [flag & ~IS_SAME for flag in addedf]
                    
            # sample PEX message and
            picks = range(len(added))
            shuffle(picks)
            pex_peers = [(added[i],addedf[i]) for i in picks[:REPEX_STORED_PEX_SIZE]]
            self.live_peers[dns] = {'last_seen' : ts_now(),
                                    'pex' : pex_peers,
                                    'version' : self.dns2version[dns]}
            # Should we do the following? Might lower the load on the tracker even more?
            # self.to_pex.extend(zip(*pex_peers)[0])
            # Possible danger: too much crawling, wasting resources?
            
            # TODO: Might be more sophisticated to sampling of PEX msg at the end?
            # (allows us to get more diversity and perhaps also security?)
        
        self.datacost['pex_connections'] += 1
        
        # Closing time
        connection.close()
    
    #
    # Status methods
    #
    def initial_peers_checked(self):
        return len(self.starting_peertable) == (self.onlinecount + self.shufflecount)
    
    #
    # Connect and bootstrap methods
    #
    def connect(self, dns, id=0):
        if dns in self.attempted:
            return
        if DEBUG:
            print >>sys.stderr, "RePEXer: connecting: %s:%s" % dns
        self.active_sockets += 1
        self.datacost['connection_attempts'] += 1
        self.attempted.add(dns)
        if not self.encoder.start_connection(dns, id, forcenew = True):
            print >>sys.stderr, "RePEXer: connecting failed: %s:%s" % dns
            self.active_sockets -= 1
            self.datacost['connection_attempts'] -= 1
            if dns in self.starting_peertable:
                self.shufflecount += 1
    
    def next_peer_from_queue(self):
        # Only return a peer if we can connect
        if self.can_connect() and self.to_pex:
            return self.to_pex.pop(0)
        else:
            return None
    
    def can_connect(self):
        return self.active_sockets < self.max_sockets
    
    def connect_queue(self):
        if DEBUG:
            print >>sys.stderr, "RePEXer: connect_queue: active_sockets: %s" % self.active_sockets
        
        # We get here from repex_ready, connection_closed or from rerequester_peers.
        # First we check whether we can connect, whether we're done, or whether we are closing.
        if self.done or self.is_closing or not self.can_connect():
            return
        # when we have found sufficient live peers and at least the initial peers are checked,
        # we are done and close the remaining connections:
        if self.initial_peers_checked() and len(self.live_peers) >= REPEX_SWARMCACHE_SIZE:
            # close_all() will result in generate several connection_closed events.
            # To prevent reentry of this function, we'll set a flag we check at function entry.
            self.is_closing = True
            self.encoder.close_all()
            assert self.active_sockets == 0
            if self.active_sockets == 0:
                self.send_done()
            return
        
        # Connect to peers in the queue
        peer = self.next_peer_from_queue()
        while peer is not None:
            self.connect(peer)
            peer = self.next_peer_from_queue()
        
        # if we didn't connect at all and we have checked all initial peers, we are forced to bootstrap
        if self.active_sockets == 0 and self.initial_peers_checked():
            if self.bootstrap_counter == 0:
                self.bootstrap()
            elif not self.requesting_tracker:
                # we have contacted the tracker before and that
                # didn't give us any new live peers, so we are
                # forced to give up
                self.send_done()
        
        if DEBUG:
            print >>sys.stderr, "RePEXer: connect_queue: active_sockets: %s" % self.active_sockets
            
    def bootstrap(self):
        if DEBUG:
            print >>sys.stderr, "RePEXer: bootstrap"
        self.bootstrap_counter += 1
        if REPEX_DISABLE_BOOTSTRAP or self.rerequest is None:
            self.rerequester_peers(None)
            return
        
        # In the future, bootstrap needs to try 2-Hop TorrentSmell first...
        # Or, Rerequester needs to modified to incorporate 2-Hop TorrentSmell.
        if self.rerequest.trackerlist in [ [], [[]] ]:
            # no trackers?
            self.rerequester_peers(None)
            return
            
        self.requesting_tracker = True
        def tracker_callback(self=self):
            if self.requesting_tracker:
                # in case of failure, call  rerequester_peers with None
                self.requesting_tracker = False
                self.rerequester_peers(None)
        self.rerequest.announce(callback=tracker_callback)
    
    #
    # Get SwarmCache
    #
    def get_swarmcache(self):
        """
        Returns the updated SwarmCache and its timestamp when done (self.done), 
        otherwise the old SwarmCache and its timestamp. The timestamp is 
        None when the SwarmCache is empty.
        
        @return A dict mapping dns to a dict with at least 'last_seen'
        and 'pex' keys. If it contains a 'prev'=True key-value pair, the peer
        was known to be in the SwarmCache's predecessor.
        """
        if self.done:
            swarmcache = self.final_peertable
        else:
            swarmcache = self.starting_peertable
        ts = swarmcache_ts(swarmcache)
        return swarmcache, ts
    
    #
    # When done (or partially in case of peer shortage)
    #
    def send_done(self):
        self.done = True
        self.end_ts = ts_now()
        
        # Construct the new SwarmCache by removing excess peers
        swarmcache = dict(self.live_peers)
        to_delete = max(len(swarmcache) - REPEX_SWARMCACHE_SIZE, 0)
        deleted = 0
        for dns in swarmcache.keys():
            if deleted == to_delete:
                break
            if dns not in self.starting_peertable:
                del swarmcache[dns]
                deleted += 1
        
        # TODO: Should we change the shuffle algorithm such that we 
        # prefer to replace an offline peer with one of the peers
        # in its PEX message?
        
        # create shufflepeers dict, allowing us to deduce why a peer was shuffled out
        shufflepeers = {}
        for dns in self.starting_peertable:
            if dns not in swarmcache:
                shufflepeers[dns] = (dns in self.bt_connectable, dns in self.bt_pex, self.starting_peertable[dns].get('last_seen',0))
        
        self.final_peertable = swarmcache
        for observer in self._observers:
            if DEBUG:
                print >>sys.stderr, "RePEXer: send_done: calling repex_done on", `observer`
            try:
                observer.repex_done(self,
                                    swarmcache,
                                    self.shufflecount,
                                    shufflepeers,
                                    self.bootstrap_counter,
                                    self.datacost)
            except:
                print_exc()
    
    #
    # Informal string representation of a RePEXer
    #
    def __str__(self):
        if self.done and self.aborted:
            status = 'ABORTED'
        elif self.done:
            status = 'DONE'
        elif self.ready:
            status = 'REPEXING'
        else:
            status = 'WAITING'
        infohash = '[%s]' % b2a_hex(self.infohash)
        summary = ''
        table = ''
        datacost = ''
        if self.done and not self.aborted:
            infohash = '\n    ' + infohash
            swarmcache = self.final_peertable
            summary = '\n    table size/shuffle/bootstrap %s/%s/%s' % (len(swarmcache), self.shufflecount, self.bootstrap_counter)
            prev_peers = set(self.starting_peertable.keys())
            cur_peers = set(swarmcache.keys())
            
            for dns in sorted(set.symmetric_difference(prev_peers,cur_peers)):
                if dns in cur_peers:
                    table += '\n        A: %s:%s' % dns
                else:
                    table += '\n        D: %s:%s - BT/PEX %s/%s' % (dns + (dns in self.bt_connectable, dns in self.bt_pex))
            table += '\n'
            datacost = '    datacost:\n        %s(%s)/%s BT(PEX) connections made, received %s bootstrap peers\n'
            datacost %= (self.datacost['connections_made'],self.datacost['pex_connections'],
                         self.datacost['connection_attempts'],self.datacost['bootstrap_peers'])
            for k in self.datacost_bandwidth_keys:
                v = self.datacost[k]
                datacost += '          %s: %s bytes down / %s bytes up\n' % (k.ljust(16), str(v[0]).rjust(6), str(v[1]).rjust(6))
        
        return '<RePEXer(%s)%s%s%s%s>' % (status,infohash,summary,table,datacost)

class RePEXerStatusCallback:
    """
    Describes the interface required by RePEXer for status callbacks.
    """
    def repex_aborted(self, repexer, dlstatus=None):
        """
        Called by network thread. RePEXer calls this method when the
        repex task is aborted. It is the propagation of the similarly 
        named method in RePEXerInterface.
        @param repexer RePEXer
        @param dlstatus Status of the download when the RePEX mode was
        interrupted, or None when unknown.
        """

    def repex_done(self, repexer, swarmcache, shufflecount, shufflepeers, bootstrapcount, datacost):
        """
        Called by network thread. RePEXer calls this method when it is done
        repexing. 
        @param repexer RePEXer
        @param swarmcache A dict mapping dns to a dict with 'last_seen' and 
        'pex' keys. The 'pex' key contains a list of (dns,flags) tuples.
        @param shufflecount The number of peers in the old SwarmCache that
        were not responding with a PEX message.
        @param shufflepeers A dict mapping a shuffle peer's dns to a triple,
        indicating (a) whether it sent a BT handshake, (b) whether it supported
        ut_pex, and (c) the last time the peer was seen. 
        @param bootstrapcount The number of times bootstrapping was needed.
        @param datacost A dict with keys 'no_pex_support', 'no_pex_msg', 
        'pex' and 'other', containing (download,upload) byte tuples, and
        keys 'connection_attempts', 'connections_made', 'bootstrap_peers',
        containing simple counters.
        """

# TODO: move this class to a module in Policies
class RePEXScheduler(RePEXerStatusCallback):
    """
    The RePEXScheduler periodically requests a list of DownloadStates from
    the Session and repexes the stopped downloads in a round robin fashion.
    """
    __single = None    # used for multithreaded singletons pattern
    lock = RLock()
    
    @classmethod
    def getInstance(cls, *args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if cls.__single is None:
            cls.lock.acquire()   
            try:
                if cls.__single is None:
                    cls.__single = cls(*args, **kw)
            finally:
                cls.lock.release()
        return cls.__single
    
    def __init__(self):
        # always use getInstance() to create this object
        # ARNOCOMMENT: why isn't the lock used on this read?!
        if self.__single != None:
            raise RuntimeError, "RePEXScheduler is singleton"
        from Tribler.Core.Session import Session # Circular import fix
        self.session = Session.get_instance()
        self.lock = RLock()
        self.active = False
        self.current_repex = None # infohash
        self.downloads = {} # infohash -> Download; in order to stop Downloads that are done repexing
        self.last_attempts = {} # infohash -> ts; in order to prevent starvation when a certain download
                                #                 keeps producing empty SwarmCaches
        
    
    def start(self):
        """ Starts the RePEX scheduler. """
        if DEBUG:
            print >>sys.stderr, "RePEXScheduler: start"
        self.lock.acquire()
        try:
            if self.active:
                return
            self.active = True
            self.session.set_download_states_callback(self.network_scan)
            RePEXer.attach_observer(self)
        finally:
            self.lock.release()
    
    def stop(self):
        """ Stops the RePEX scheduler. """
        if DEBUG:
            print >>sys.stderr, "RePEXScheduler: stop"
        self.lock.acquire()
        try:
            if not self.active:
                return
            RePEXer.detach_observer(self)
            self.active = False
            self.session.set_download_states_callback(self.network_stop_repex)
        finally:
            self.lock.release()
        
    def network_scan(self, dslist):
        """
        Called by network thread. Scans for stopped downloads and stores
        them in a queue.
        @param dslist List of DownloadStates"""
        # TODO: only repex last X Downloads instead of all.
        if DEBUG:
            print >>sys.stderr, "RePEXScheduler: network_scan: %s DownloadStates" % len(dslist)
        self.lock.acquire()
        exception = None
        try:
            try:
                if not self.active or self.current_repex is not None:
                    return -1, False
                
                now = ts_now()
                found_infohash = None
                found_download = None
                found_age = -1
                for ds in dslist:
                    download = ds.get_download()
                    infohash = download.tdef.get_infohash()
                    debug_msg = None
                    if DEBUG:
                        print >>sys.stderr, "RePEXScheduler: network_scan: checking", `download.tdef.get_name_as_unicode()`
                    if ds.get_status() == DLSTATUS_STOPPED and ds.get_progress()==1.0:
                        # TODO: only repex finished downloads or also prematurely stopped ones?
                        age = now - (swarmcache_ts(ds.get_swarmcache()) or 0)
                        last_attempt_ago = now - self.last_attempts.get(infohash, 0)
                        
                        if last_attempt_ago < REPEX_MIN_INTERVAL:
                            debug_msg = "...too soon to try again, last attempt was %ss ago" % last_attempt_ago
                        elif age < REPEX_INTERVAL:
                            debug_msg = "...SwarmCache too fresh: %s seconds" % age
                        else:
                            if age >= REPEX_INTERVAL:
                                debug_msg = "...suitable for RePEX!"
                                if age > found_age:
                                    found_download = download
                                    found_infohash = infohash
                                    found_age = age
                    else:
                        debug_msg = "...not repexable: %s %s%%" % (dlstatus_strings[ds.get_status()], ds.get_progress()*100)
                    if DEBUG:
                        print >>sys.stderr, "RePEXScheduler: network_scan:", debug_msg
                
                if found_download is None:
                    if DEBUG:
                        print >>sys.stderr, "RePEXScheduler: network_scan: nothing found yet"
                    return REPEX_SCAN_INTERVAL, False
                else:
                    if DEBUG:
                        print >>sys.stderr, "RePEXScheduler: network_scan: found %s, starting RePEX phase." % `found_download.tdef.get_name_as_unicode()`
                    self.current_repex = found_infohash
                    self.downloads[found_infohash] = found_download
                    found_download.set_mode(DLMODE_NORMAL)
                    found_download.restart(initialdlstatus=DLSTATUS_REPEXING)
                    return -1, False
            except Exception, e:
                exception = e
        finally:
            self.lock.release()
        if exception is not None: raise exception
    
    def network_stop_repex(self, dslist):
        """Called by network thread.
        @param dslist List of DownloadStates"""
        if DEBUG:
            print >>sys.stderr, "RePEXScheduler: network_stop_repex:"
        for d in [ds.get_download() for ds in dslist if ds.get_status() == DLSTATUS_REPEXING]:
            if DEBUG:
                print >>sys.stderr, "\t...",`d.tdef.get_name_as_unicode()`
            d.stop()
        return -1, False
        
    #
    # RePEXerStatusCallback interface (called by network thread)
    #
    def repex_aborted(self, repexer, dlstatus=None):
        if DEBUG:
            if dlstatus is None:
                status_string = str(None)
            else:
                status_string = dlstatus_strings[dlstatus]
            print >>sys.stderr, "RePEXScheduler: repex_aborted:", b2a_hex(repexer.infohash), status_string
        self.current_repex = None
        self.last_attempts[repexer.infohash] = ts_now() 
        self.session.set_download_states_callback(self.network_scan)

    def repex_done(self, repexer, swarmcache, shufflecount, shufflepeers, bootstrapcount, datacost):
        if DEBUG:
            print >>sys.stderr, 'RePEXScheduler: repex_done: %s\n\ttable size/shuffle/bootstrap %s/%s/%s' % (
                                b2a_hex(repexer.infohash), len(swarmcache), shufflecount, bootstrapcount)
        self.current_repex = None
        self.last_attempts[repexer.infohash] = ts_now()
        self.downloads[repexer.infohash].stop()
        self.session.set_download_states_callback(self.network_scan)

#
# Classes for logging/measurement purposes
#

class RePEXLogger(RePEXerStatusCallback):
    """
    For measurement: This class' sole purpose is to log all repex done 
    messages.
    """
    __single = None    # used for multithreaded singletons pattern
    lock = RLock()
    
    @classmethod
    def getInstance(cls, *args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if cls.__single is None:
            cls.lock.acquire()   
            try:
                if cls.__single is None:
                    cls.__single = cls(*args, **kw)
            finally:
                cls.lock.release()
        return cls.__single
    
    def __init__(self):
        # always use getInstance() to create this object
        # ARNOCOMMENT: why isn't the lock used on this read?!
        if self.__single != None:
            raise RuntimeError, "RePEXLogger is singleton"
        self.repexlog = RePEXLogDB.getInstance()
        self.active = False
    
    def start(self):
        """ Starts the RePEX logger. """
        if DEBUG:
            print >>sys.stderr, "RePEXLogger: start"
        self.lock.acquire()
        try:
            if self.active:
                return
            self.active = True
            RePEXer.attach_observer(self)
        finally:
            self.lock.release()
    
    def stop(self):
        """ Stops the RePEX logger. """
        if DEBUG:
            print >>sys.stderr, "RePEXLogger: stop"
        self.lock.acquire()
        try:
            if not self.active:
                return
            RePEXer.detach_observer(self)
            self.active = False
        finally:
            self.lock.release()
    
    #
    # RePEXerStatusCallback interface
    #
    def repex_aborted(self, repexer, dlstatus=None):
        if dlstatus is None:
            status_string = str(None)
        else:
            status_string = dlstatus_strings[dlstatus]
        if DEBUG:
            print >>sys.stderr, "RePEXLogger: repex_aborted:", b2a_hex(repexer.infohash), status_string
    
    def repex_done(self, repexer, swarmcache, shufflecount, shufflepeers, bootstrapcount, datacost):
        if DEBUG:
            print >>sys.stderr, 'RePEXLogger: repex_done: %s' % repexer
        self.repexlog.storeSwarmCache(repexer.infohash, swarmcache,
                                      (shufflecount,shufflepeers,bootstrapcount,datacost),
                                      timestamp=repexer.ready_ts, commit=True)

class RePEXLogDB:
    """
    For measurements, stores the intermediate RePEX results.
    """
    __single = None    # used for multithreaded singletons pattern
    lock = RLock()
    PEERDB_FILE = 'repexlog.pickle'
    PEERDB_VERSION = '0.6'
    MAX_HISTORY = 20480 # let's say 1K per SwarmCache, 20480 would be max 20 MB...
    
    @classmethod
    def getInstance(cls, *args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if cls.__single is None:
            cls.lock.acquire()   
            try:
                if cls.__single is None:
                    cls.__single = cls(*args, **kw)
            finally:
                cls.lock.release()
        return cls.__single
    
    def __init__(self, *args, **kargs):
        # always use getInstance() to create this object
        # ARNOCOMMENT: why isn't the lock used on this read?!
        if self.__single != None:
            raise RuntimeError, "RePEXLogDB is singleton"
        #SQLiteCacheDBBase.__init__(self, *args, **kargs)
        
        from Tribler.Core.Session import Session # Circular import fix
        state_dir = Session.get_instance().sessconfig['state_dir']
        self.db = os.path.join(state_dir, self.PEERDB_FILE)
        if not os.path.exists(self.db):
            self.version = self.PEERDB_VERSION
            self.history = []
        else:
            import cPickle as pickle
            f = open(self.db,'rb')
            tuple = pickle.load(f)
            self.version, self.history = tuple
            f.close()
    
    def commit(self):
        """
        Commits the last changes to file.
        """
        self.lock.acquire()   
        try:
            import cPickle as pickle
            f = open(self.db,'wb')
            pickle.dump((self.version, self.history), f)
            f.close()
        finally:
            self.lock.release()
        
    def storeSwarmCache(self, infohash, swarmcache, stats = None, timestamp=-1, commit=False):
        """
        Stores the SwarmCache for a given infohash. Does not automatically
        commit the changes to file.
        @param infohash SHA1 hash of the swarm.
        @param swarmcache A dict mapping dns to a dict with at least 
        'last_seen' and 'pex' keys.
        @param stats (shufflecount, shufflepeers, bootstrapcount, datacost) 
        quadruple or None.
        @param timestamp Optional timestamp, by default -1. Empty SwarmCaches 
        don't contain any time information at all, so it's useful to explicitly
        specify the time when the SwarmCache was created.
        @param commit Flag to commit automatically.
        """
        if DEBUG:
            print >>sys.stderr, 'RePEXLogDB: storeSwarmCache: DEBUG:\n\t%s\n\t%s\n\t%s' % (
                            #b2a_hex(infohash), swarmcache, stats) # verbose
                            b2a_hex(infohash), '', '') # less cluttered
        self.lock.acquire()
        try:
            self.history.append((infohash,swarmcache,stats,timestamp))
            if len(self.history) > self.MAX_HISTORY:
                del self.history[:-self.MAX_HISTORY]
            if commit:
                self.commit()
        finally:
            self.lock.release()
    
    def getHistoryAndCleanup(self):
        """
        For measurement purposes, gets the history of all stored SwarmCaches
        (infohash, swarmcache, stats). This method clears the history and 
        commits the empty history to file.
        """
        self.lock.acquire()
        try:
            res = self.history
            self.history = []
            self.commit()
            return res
        finally:
            self.lock.release()
    

#
# Manual testing class
#

class RePEXerTester(RePEXerStatusCallback):
    """
    Manual testing class for in the Python REPL.
    
    Usage:
    
    >>> from Tribler.Core.TorrentDef import TorrentDef
    >>> from Tribler.Core.DownloadConfig import *
    >>> from Tribler.Core.DecentralizedTracking.repex import *
    >>> tdef = TorrentDef.load('foo.torrent')
    >>> dscfg = DownloadStartupConfig()
    >>> dscfg.set_dest_dir('/tmp')
    >>> r = RePEXerTester() 
    >>> d = r.stopped_download(tdef,dscfg)
    >>> sys.stdout=sys.stderr # optionally
    >>> r.test_repex(d)
    ...
    >>> r.test_repex(d)
    ...
    >>> r.test_repex(d, swarmcache={('xxx.xxx.xxx.xxx',zzz) : {'last_seen':0, 'pex': []}})
    ...
    >>> r.test_repex(d, use_peerdb=True)
    ...
    
    r.repexers[Download] and r.swarmcaches[Download] contain a list of created 
    repexers and the SwarmCaches they have returned. 
    """
    def __init__(self):
        from Tribler.Core.Session import Session # Circular import fix
        self.session = Session.get_instance()
        self.peerdb = RePEXLogDB.getInstance()
        self.downloads = {} # infohash -> Download 
        self.swarmcaches = {} # Download -> [SwarmCache]
        self.repexers = {} # Download -> [repexer]
        # register as global observer
        RePEXer.attach_observer(self)
    
    def stopped_download(self, tdef, dcfg):
        """
        For testing purposes, creates a stopped download given a TorrentDef 
        and config.
        @param tdef  A finalized TorrentDef.
        @param dcfg DownloadStartupConfig or None, in which case 
        a new DownloadStartupConfig() is created with its default settings
        and the result becomes the runtime config of this Download.
        @return Download
        """
        d = self.session.start_download(tdef,dcfg)
        d.stop()
        self.downloads[d.tdef.get_infohash()] = d
        return d
    
    def test_repex(self, download, swarmcache=None):
        """
        Performs a RePEX on a stopped Download.
        @param download A stopped Download
        @param swarmcache Initial SwarmCache to use. If None, the latest
        SwarmCache in the Download's pstate will be used.
        """
        download.stop()
        self.downloads[download.tdef.get_infohash()] = download
        if swarmcache is not None:
            # Hacking into pstate must happen after network_stop!
            def hack_into_pstate(d=download,swarmcache=swarmcache):
                d.pstate_for_restart.setdefault('dlstate',{})['swarmcache'] = swarmcache
            self.session.lm.rawserver.add_task(hack_into_pstate,0.0)
        
        download.set_mode(DLMODE_NORMAL)
        download.restart(initialdlstatus=DLSTATUS_REPEXING)
    
    #
    # RePEXerStatusCallback interface
    #
    def repex_aborted(self, repexer, dlstatus=None):
        if dlstatus is None:
            status_string = str(None)
        else:
            status_string = dlstatus_strings[dlstatus]
        print >>sys.stderr, "RePEXerTester: repex_aborted:", `repexer`,status_string
        download = self.downloads[repexer.infohash]
        self.repexers.setdefault(download,[]).append(repexer)
        self.swarmcaches.setdefault(download,[]).append(None)
    
    def repex_done(self, repexer, swarmcache, shufflecount, shufflepeers, bootstrapcount, datacost):
        download = self.downloads[repexer.infohash]
        print >>sys.stderr, 'RePEXerTester: repex_done: %s' % repexer
        self.repexers.setdefault(download,[]).append(repexer)
        self.swarmcaches.setdefault(download,[]).append(swarmcache)
        
        # Always log to RePEXLogDB
        self.peerdb.storeSwarmCache(repexer.infohash, swarmcache,
                                    (shufflecount,shufflepeers,bootstrapcount,datacost),
                                    timestamp=repexer.ready_ts, commit=True)
