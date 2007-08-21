# Written by Bram Cohen, Pawel Garbacki and Arno Bakker
# see LICENSE.txt for license information

import time
import traceback,sys
from sha import sha
from types import DictType,IntType
from random import shuffle

from BitTornado.bitfield import Bitfield
from BitTornado.clock import clock
from BitTornado.bencode import bencode,bdecode
from BitTornado.__init__ import version_short,decodePeerID,TRIBLER_PEERID_LETTER
from BitTornado.BT1.convert import tobinary,toint

from MessageID import *

# 2fastbt_
from Tribler.CacheDB.CacheDBHandler import PeerDBHandler, BarterCastDBHandler
from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.DecentralizedTracking.ut_pex import *
# _2fastbt

from Tribler.Overlay.permid import permid_for_user

from BitTornado.CurrentRateMeasure import Measure

try:
    True
except:
    True = 1
    False = 0

DEBUG = False
DEBUG_NORMAL_MSGS = False

UNAUTH_PERMID_PERIOD = 3600

"""
Arno: 2007-02-16:
uTorrent and Bram's BitTorrent now support an extension to the protocol,
documented on http://www.rasterbar.com/products/libtorrent/extension_protocol.html

The problem is that the bit they use in the options field of the BT handshake
is the same as we use to indicate a peer supports the overlay-swarm connection.
The new clients will send an EXTEND message with ID 20 after the handshake to
inform the otherside what new messages it supports.

As a result, Tribler <= 3.5.0 clients won't be confused, but can't talk to these 
new clients either or vice versa. The new client will think we understand the 
message, send it. But because we don't know that message ID, we will close 
the connection. Our attempts to establish a new overlay connection with the new
client will gracefully fail, as the new client will not know of infohash=00000...
and close the connection.

We solve this conflict by adding support for the EXTEND message. We are now be 
able to receive it, and send our own. Our message will contain one method name, 
i.e. Tr_OVERLAYSWARM=253. Processing is now as follows:

* If bit 43 is set and the peerID is from an old Tribler (<=3.5.0)
  peer, we initiate an overlay-swarm connection.
* If bit 43 is set and the peer's EXTEND hs message contains method Tr_OVERLAYSWARM,
  it's a new Tribler peer, and we initiate an overlay-swarm connection.
* If bit 43 is set, and the EXTEND hs message does not contain Tr_OVERLAYSWARM
  it's not a Tribler client and we do not initiate an overlay-swarm
  connection.

N.B. The EXTEND message is poorly designed, it lacks protocol versioning
support which is present in the Azureus Extended Messaging Protocol
and our overlay-swarm protocol.

"""
EXTEND_MSG_HANDSHAKE_ID = chr(0)
EXTEND_MSG_OVERLAYSWARM = 'Tr_OVERLAYSWARM'
EXTEND_MSG_G2G          = 'Tr_G2G'

def show(s):
    text = []
    for i in xrange(len(s)): 
        text.append(ord(s[i]))
    return text
    
class Connection:
    def __init__(self, connection, connecter):
        self.connection = connection    
        self.connecter = connecter
        self.got_anything = False
        self.next_upload = None
        self.outqueue = []
        self.partial_message = None
        self.download = None
        self.upload = None
        self.send_choke_queued = False
        self.just_unchoked = None
        self.unauth_permid = None
        self.looked_for_permid = UNAUTH_PERMID_PERIOD-3
        self.closed = False
        self.extend_hs_dict = {}        # what extended messages does this peer support
        self.initiated_overlay = False
        self.ut_pex_previous_conns = [] # last value of 'added' field for this peer

        self.use_g2g = False # set to true if both sides use G2G, indicated by self.connector.use_g2g
        self.parts_sent = {}

        config = self.connecter.config
        self.forward_speeds = [0] * 2
        self.forward_speeds[0] = Measure(config['max_rate_period'], config['upload_rate_fudge'])
        self.forward_speeds[1] = Measure(config['max_rate_period'], config['upload_rate_fudge'])
        
        # BarterCast counters
        self.total_downloaded = 0
        self.total_uploaded = 0

    def get_myip(self, real=False):
        return self.connection.get_myip(real)
    
    def get_myport(self, real=False):
        return self.connection.get_myport(real)
        
    def get_ip(self, real=False):
        return self.connection.get_ip(real)

    def get_port(self, real=False):
        return self.connection.get_port(real)

    #def set_permid(self, permid):
    #    self.permid = permid

    def get_unauth_permid(self):
        """ Linking this normal connection to the PermID of its peer in all
            cases is non-trivial. I currently hack this unsafe solution where
            we look at the database periodically.

            FIXME: very expensive operation in 50.000 peer DB indexed on permid
        """
        self.looked_for_permid += 1
        if self.looked_for_permid >= UNAUTH_PERMID_PERIOD:
            self.looked_for_permid = 0
            peerdb = PeerDBHandler()
            peerList = peerdb.findPeers('ip',self.connection.get_ip())
            if len(peerList) != 1:
                return # Don't know
            self.unauth_permid = peerList[0]['permid']
        return self.unauth_permid

    def get_id(self):
        return self.connection.get_id()

    def get_readable_id(self):
        return self.connection.get_readable_id()

    def close(self):
        if DEBUG:
            print 'connection closed'
        self.connection.close()
        self.closed = True
        
    def is_closed(self):
        return self.closed

    def is_locally_initiated(self):
        return self.connection.is_locally_initiated()

    def send_interested(self):
        self._send_message(INTERESTED)

    def send_not_interested(self):
        self._send_message(NOT_INTERESTED)

    def send_choke(self):
        if self.partial_message:
            self.send_choke_queued = True
        else:
            self._send_message(CHOKE)
            self.upload.choke_sent()
            self.just_unchoked = 0

    def send_unchoke(self):
        if self.send_choke_queued:
            self.send_choke_queued = False
            if DEBUG_NORMAL_MSGS:
                print 'CHOKE SUPPRESSED'
        else:
            self._send_message(UNCHOKE)
            if (self.partial_message or self.just_unchoked is None
                or not self.upload.interested or self.download.active_requests):
                self.just_unchoked = 0
            else:
                self.just_unchoked = clock()

    def send_request(self, index, begin, length):
        self._send_message(REQUEST + tobinary(index) + 
            tobinary(begin) + tobinary(length))
        if DEBUG_NORMAL_MSGS:
            print "sending REQUEST to",self.get_ip()
            print 'sent request: '+str(index)+': '+str(begin)+'-'+str(begin+length)

    def send_cancel(self, index, begin, length):
        self._send_message(CANCEL + tobinary(index) + 
            tobinary(begin) + tobinary(length))
        if DEBUG_NORMAL_MSGS:
            print 'sent cancel: '+str(index)+': '+str(begin)+'-'+str(begin+length)

    def send_bitfield(self, bitfield):
        self._send_message(BITFIELD + bitfield)

    def send_have(self, index):
        self._send_message(HAVE + tobinary(index))

    def send_keepalive(self):
        self._send_message('')

    def _send_message(self, s):
        s = tobinary(len(s))+s
        if self.partial_message:
            self.outqueue.append(s)
        else:
            self.connection.send_message_raw(s)

    def send_partial(self, bytes):
        if self.connection.closed:
            return 0
        if self.partial_message is None:
            s = self.upload.get_upload_chunk()
            if s is None:
                return 0
            # Merkle: send hashlist along with piece in HASHPIECE message
            index, begin, hashlist, piece = s

            if self.use_g2g:
                # ----- G2G: record who we send this to
                self.g2g_sent_piece_part( self, index, begin, hashlist, piece )

                # ---- G2G: we are uploading len(piece) data of piece #index
                for c in self.connecter.connections.itervalues():
                    if not c.use_g2g:
                        continue

                    # include sending to self, because it should not be excluded from the statistics

                    c.send_g2g_piece_xfer( index, begin, piece )

            if self.connecter.merkle_torrent:
                bhashlist = bencode(hashlist)
                self.partial_message = ''.join((
                                tobinary(1+4+4+4+len(bhashlist)+len(piece)), HASHPIECE,
                                tobinary(index), tobinary(begin), tobinary(len(bhashlist)), bhashlist, piece.tostring() ))
            else:
                self.partial_message = ''.join((
                            tobinary(len(piece) + 9), PIECE, 
                            tobinary(index), tobinary(begin), piece.tostring()))
            if DEBUG_NORMAL_MSGS:
                print 'sending chunk: '+str(index)+': '+str(begin)+'-'+str(begin+len(piece))

        if bytes < len(self.partial_message):
            self.connection.send_message_raw(self.partial_message[:bytes])
            self.partial_message = self.partial_message[bytes:]
            return bytes

        q = [self.partial_message]
        self.partial_message = None
        if self.send_choke_queued:
            self.send_choke_queued = False
            self.outqueue.append(tobinary(1)+CHOKE)
            self.upload.choke_sent()
            self.just_unchoked = 0
        q.extend(self.outqueue)
        self.outqueue = []
        q = ''.join(q)
        self.connection.send_message_raw(q)
        return len(q)

    def get_upload(self):
        return self.upload

    def get_download(self):
        return self.download

    def set_download(self, download):
        self.download = download

    def backlogged(self):
        return not self.connection.is_flushed()

    def got_request(self, i, p, l):
        self.upload.got_request(i, p, l)
        if self.just_unchoked:
            self.connecter.ratelimiter.ping(clock() - self.just_unchoked)
            self.just_unchoked = 0

    #
    # ut_pex support
    #
    def supports_extend_msg(self,msg_name):
        if 'm' in self.extend_hs_dict:
            return msg_name in self.extend_hs_dict['m']
        else:
            return False
    
    def got_extend_handshake(self,d):
        if DEBUG:
            print >>sys.stderr,"connecter: Got EXTEND handshake:",d
        if 'm' in d:
            if type(d['m']) != DictType:
                raise ValueError('Key m does not map to a dict')
            m = d['m']
            for key,val in m.iteritems():
                if type(val) != IntType:
                    raise ValueError('Message ID in m-dict not int')

            if not 'm' in self.extend_hs_dict:
                self.extend_hs_dict['m'] = {}
            # Note: we store the dict without converting the msg IDs to bytes.
            self.extend_hs_dict['m'].update(d['m'])
            if EXTEND_MSG_OVERLAYSWARM in self.extend_hs_dict['m']:
                # This peer understands our overlay swarm extension
                if self.connection.locally_initiated:
                    if DEBUG:
                        print >>sys.stderr,"connecter: Peer supports Tr_OVERLAYSWARM, attempt connection"
                    self.connect_overlay()
            if self.connecter.use_g2g and EXTEND_MSG_G2G in self.extend_hs_dict['m']:
                # Both us and the peer want to use G2G
                if self.connection.locally_initiated:
                    if DEBUG:
                        print >>sys.stderr,"connecter: Peer supports Tr_G2G"

                self.use_g2g = True
        # 'p' is peer's listen port, 'v' is peer's version, all optional
        # 'e' is used by uTorrent to show it prefers encryption (whatever that means)
        for key in ['p','e']:
            if key in d:
                self.extend_hs_dict[key] = d[key]

    def extend_msg_id_to_name(self,ext_id):
        """ find the name for the given message id (byte) """
        for key,val in self.extend_hs_dict['m'].iteritems():
            if val == ord(ext_id):
                return key
        return None
    
    def extend_msg_name_to_id(self,ext_name):
        """ returns the message id (byte) for the given message name or None """
        val = self.extend_hs_dict['m'].get(ext_name)
        if val is None:
            return val
        else:
            return chr(val)

    def got_ut_pex(self,d):
        if DEBUG:
            print >>sys.stderr,"connecter: Got uTorrent PEX:",d
        (added_peers,dropped_peers) = check_ut_pex(d)
        
        # DoS protection: we're accepting IP addresses from 
        # an untrusted source, so be a bit careful
        mx = self.connecter.ut_pex_max_addrs_from_peer
        if DEBUG:
            print >>sys.stderr,"connecter: Got",len(added_peers),"peers via uTorrent PEX, using max",mx
            #print >>sys.stderr,"connecter: Got",added_peers
        shuffle(added_peers)
        
        sample_added_peers = added_peers[:mx]
        if len(sample_added_peers) > 0:
            self.connection.Encoder.start_connections(sample_added_peers)

    def get_extend_encryption(self):
        return self.extend_hs_dict.get('e',0)
    
    def get_extend_listenport(self):
        return self.extend_hs_dict.get('p')

    def get_ut_pex_previous_conns(self):
        return self.ut_pex_previous_conns

    def set_ut_pex_previous_conns(self,conns):
        self.ut_pex_previous_conns = conns

    def send_extend_handshake(self):
        d = {}
        d['m'] = self.connecter.EXTEND_HANDSHAKE_M_DICT
        d['p'] = self.connecter.mylistenport
        ver = version_short.replace('-',' ',1)
        d['v'] = ver
        d['e'] = 0  # Apparently this means we don't like uTorrent encryption
        self._send_message(EXTEND + EXTEND_MSG_HANDSHAKE_ID + bencode(d))
        #if DEBUG:
        #    print >>sys.stderr,'connecter: sent extend: id=0+',d

    def send_extend_ut_pex(self,payload):
        msg = EXTEND+self.extend_msg_name_to_id(EXTEND_MSG_UTORRENT_PEX)+payload
        self._send_message(msg)

            
    #
    # SecureOverlay support
    #
    def connect_overlay(self):
        if DEBUG:
            print >>sys.stderr,"connecter: Initiating overlay connection"
        if not self.initiated_overlay:
            self.initiated_overlay = True
            so = SecureOverlay.getInstance()
            so.connect_dns(self.connection.dns,self.connect_dns_callback)

    def connect_dns_callback(self,exc,dns,permid,selversion):
        if exc is not None:
            print >>sys.stderr,"connecter: peer",dns,"said he supported overlay swarm, but we can't connect to him",exc

    def send_g2g_piece_xfer(self,index,begin,piece):
        self._send_message(G2G_PIECE_XFER + tobinary(index) + tobinary(begin) + tobinary(len(piece)))

    def got_g2g_piece_xfer(self,index,begin,length):
        self.g2g_peer_forwarded_piece_part( self, index, begin, length )

    def g2g_sent_piece_part( self, c, i, begin, hashlist, piece ):
        """ Keeps a record of the fact that we sent piece i[begin:end]. """

        record = (begin,begin+len(piece))
        if i in self.parts_sent:
            self.parts_sent[i].append( record )
        else:
            self.parts_sent[i] = [record]

    def g2g_peer_forwarded_piece_part( self, c, i, begin, length ):
        """ Processes this peer forwarding piece i[begin:end] to a grandchild. """

        end = begin + length

        # Reward for forwarding data in general
        self.forward_speeds[1].update_rate( length )

        if i not in self.parts_sent:
            # piece came from disk
            return

        # Extra reward if its data we sent
        for l in self.parts_sent[i]:
            b,e = l

            if begin < b < end or begin < e < end:
                # pieces overlap -- reward child for forwarding our data
                overlap = min( e, end ) - max( b, begin )

                self.forward_speeds[0].update_rate( overlap )

    def g2g_score( self ):
        return [x.get_rate() for x in self.forward_speeds]

class Connecter:
# 2fastbt_
    def __init__(self, make_upload, downloader, choker, numpieces,
            totalup, config, ratelimiter, merkle_torrent, sched = None, 
            coordinator = None, helper = None, mylistenport = None, use_g2g = False, infohash=None):
        self.downloader = downloader
        self.make_upload = make_upload
        self.choker = choker
        self.numpieces = numpieces
        self.config = config
        self.ratelimiter = ratelimiter
        self.rate_capped = False
        self.sched = sched
        self.totalup = totalup
        self.rate_capped = False
        self.connections = {}
        self.external_connection_made = 0
        self.merkle_torrent = merkle_torrent
        self.use_g2g = use_g2g
        # 2fastbt_
        self.coordinator = coordinator
        self.helper = helper
        self.round = 0
        self.mylistenport = mylistenport
        self.infohash = infohash
        self.overlay_enabled = 1
        if 'overlay' in self.config:
            self.overlay_enabled = self.config['overlay']
        self.ut_pex_enabled = 0
        if 'ut_pex_max_addrs_from_peer' in self.config:
            self.ut_pex_max_addrs_from_peer = self.config['ut_pex_max_addrs_from_peer']
            self.ut_pex_enabled = self.ut_pex_max_addrs_from_peer > 0
            
        if DEBUG:
            if self.ut_pex_enabled:
                print >>sys.stderr,"connecter: Enabling uTorrent PEX",self.ut_pex_max_addrs_from_peer
            else:
                print >>sys.stderr,"connecter: Disabling uTorrent PEX"

        # The set of messages we support. Note that the msg ID is an int not a byte in 
        # this dict.
        self.EXTEND_HANDSHAKE_M_DICT = {}
            
        if self.overlay_enabled:
            # Say in the EXTEND handshake we support the overlay-swarm ext.
            d = {EXTEND_MSG_OVERLAYSWARM:ord(CHALLENGE)}
            self.EXTEND_HANDSHAKE_M_DICT.update(d)
        if self.ut_pex_enabled:
            # Say in the EXTEND handshake we support uTorrent's peer exchange ext.
            d = {EXTEND_MSG_UTORRENT_PEX:ord(EXTEND_MSG_UTORRENT_PEX_ID)}
            self.EXTEND_HANDSHAKE_M_DICT.update(d)
            self.sched(self.ut_pex_callback,6)
        if self.use_g2g:
            # Say in the EXTEND handshake we want to do G2G.
            d = {EXTEND_MSG_G2G:ord(G2G_PIECE_XFER)}
            self.EXTEND_HANDSHAKE_M_DICT.update(d)
            
            
        # BarterCast    
        self.peerdb = PeerDBHandler()
        self.bartercastdb = BarterCastDBHandler()
            

    def how_many_connections(self):
        return len(self.connections)

    def connection_made(self, connection):
        c = Connection(connection, self)
        self.connections[connection] = c
        
        if self.overlay_enabled and connection.support_olswarm_extend:
            # The peer either supports our overlay-swarm extension or 
            # the utorrent extended protocol. And we have overlay swarm enabled.
            [client,version] = decodePeerID(connection.id)
            
            if DEBUG:
                print >>sys.stderr,"connecter: Peer is client",client,"version",version
            
            if client == TRIBLER_PEERID_LETTER and version <= '3.5.0' and connection.locally_initiated:
                # Old Tribler, establish overlay connection
                if DEBUG:
                    print >>sys.stderr,"connecter: Peer is previous Tribler version, attempt overlay connection"
                c.connect_overlay()
            else:
                # EXTEND handshake must be sent just after BT handshake, 
                # before BITFIELD even
                c.send_extend_handshake()
                
        #TODO: overlay swarm also needs upload and download to control transferring rate
        c.upload = self.make_upload(c, self.ratelimiter, self.totalup)
        c.download = self.downloader.make_download(c)
        self.choker.connection_made(c)
        return c

    def connection_lost(self, connection):
        c = self.connections[connection]

        ######################################
        # BarterCast

        ip = c.get_ip(False)       
        port = c.get_port(False)   

        permid = self.peerdb.getPermIDByIP(ip)

        print >> sys.stdout, "Up %d down %d peer %s:%s (PermID = %s)" % (c.total_uploaded, c.total_downloaded, ip, port, permid)
        my_permid = self.bartercastdb.my_permid

        # Save downloaded MBs in PeerDB
        if permid != None:

            name = self.bartercastdb.getName(permid)
            
            down_kb = int(c.total_downloaded / 1024)
            up_kb = int(c.total_uploaded / 1024)

            if down_kb > 0:
                new_value = self.bartercastdb.incrementItem((my_permid, permid), 'downloaded', down_kb)
 #               print >> sys.stdout, "DB: downloaded %d bytes from peer %s" % (new_value, name)

            if up_kb > 0:
                new_value = self.bartercastdb.incrementItem((my_permid, permid), 'uploaded', up_kb)
 #               print >> sys.stdout, "DB: uploaded %d bytes from peer %s" % (new_value, name)

        ###################################### 

        del self.connections[connection]
        if c.download:
            c.download.disconnected()
        self.choker.connection_lost(c)

    def connection_flushed(self, connection):
        conn = self.connections[connection]
        if conn.next_upload is None and (conn.partial_message is not None
               or conn.upload.buffer):
            self.ratelimiter.queue(conn)

    def got_piece(self, i):
        for co in self.connections.values():
            co.send_have(i)

    def ut_pex_callback(self):
        """ Periocially send info about the peers you know to the other peers """
        if DEBUG:
            print >>sys.stderr,"connecter: Periodic ut_pex update"
        for c in self.connections.values():
            if c.supports_extend_msg(EXTEND_MSG_UTORRENT_PEX):
                if DEBUG:
                    print >>sys.stderr,"connecter: ut_pex: Creating msg for",c.get_ip(),c.get_extend_listenport()
                try:
                    currconns = self.connections.values()
                    (addedconns,droppedconns) = ut_pex_get_conns_diff(currconns,c,c.get_ut_pex_previous_conns())
                    c.set_ut_pex_previous_conns(currconns)
                    if False: # DEBUG
                        for conn in addedconns:
                            print >>sys.stderr,"connecter: ut_pex: Added",conn.get_ip(),conn.get_extend_listenport()
                        for conn in droppedconns:
                            print >>sys.stderr,"connecter: ut_pex: Dropped",conn.get_ip(),conn.get_extend_listenport()
                    payload = create_ut_pex(addedconns,droppedconns)
                    c.send_extend_ut_pex(payload)
                except:
                    traceback.print_exc()
        self.sched(self.ut_pex_callback,60)

    def got_message(self, connection, message):
        # connection: Encrypter.Connection; c: Connecter.Connection
        c = self.connections[connection]    
        t = message[0]
        # EXTEND handshake will be sent just after BT handshake, 
        # before BITFIELD even
        
        #if DEBUG_NORMAL_MSGS:
        #    print "connecter: Got msg from",getMessageName(t),connection.get_ip()

        
        
        if t == EXTEND:
            self.got_extend_message(connection,c,message,self.ut_pex_enabled)
            return
        if t == BITFIELD and c.got_anything:
            if DEBUG:
                print "Close on BITFIELD"
            connection.close()
            return
        c.got_anything = True
        if (t in [CHOKE, UNCHOKE, INTERESTED, NOT_INTERESTED] and 
                len(message) != 1):
            if DEBUG:
                print "Close on bad (UN)CHOKE/(NOT_)INTERESTED",t
            connection.close()
            return
        if t == CHOKE:
            if DEBUG_NORMAL_MSGS:
                print "connecter: Got CHOKE from",connection.get_ip()
            c.download.got_choke()
        elif t == UNCHOKE:
            if DEBUG_NORMAL_MSGS:
                print "connecter: Got UNCHOKE from",connection.get_ip()
            c.download.got_unchoke()
        elif t == INTERESTED:
            if DEBUG_NORMAL_MSGS:
                print "connecter: Got INTERESTED from",connection.get_ip()
            if c.upload is not None:
                c.upload.got_interested()
        elif t == NOT_INTERESTED:
            c.upload.got_not_interested()
        elif t == HAVE:
            if len(message) != 5:
                if DEBUG:
                    print "Close on bad HAVE: msg len"
                connection.close()
                return
            i = toint(message[1:])
            if i >= self.numpieces:
                if DEBUG:
                    print "Close on bad HAVE: index out of range"
                connection.close()
                return
            if DEBUG_NORMAL_MSGS:
                print "connecter: Got HAVE(",i,") from",connection.get_ip()
            c.download.got_have(i)
        elif t == BITFIELD:
            if DEBUG_NORMAL_MSGS:
                print "connecter: Got BITFIELD from",connection.get_ip()
            try:
                b = Bitfield(self.numpieces, message[1:])
            except ValueError:
                if DEBUG:
                    print "Close on bad BITFIELD"
                connection.close()
                return
            if c.download is not None:
                c.download.got_have_bitfield(b)
        elif t == REQUEST:
            if len(message) != 13:
                if DEBUG:
                    print "Close on bad REQUEST: msg len"
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                if DEBUG:
                    print "Close on bad REQUEST: index out of range"
                connection.close()
                return
            if DEBUG_NORMAL_MSGS:
                print "connecter: Got REQUEST(",i,") from",connection.get_ip()
            c.got_request(i, toint(message[5:9]), toint(message[9:]))
        elif t == CANCEL:
            if len(message) != 13:
                if DEBUG:
                    print "Close on bad CANCEL: msg len"
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                if DEBUG:
                    print "Close on bad CANCEL: index out of range"
                connection.close()
                return
            c.upload.got_cancel(i, toint(message[5:9]), 
                toint(message[9:]))
        elif t == PIECE:
            if len(message) <= 9:
                if DEBUG:
                    print "Close on bad PIECE: msg len"
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                if DEBUG:
                    print "Close on bad PIECE: msg len"
                connection.close()
                return
            if DEBUG_NORMAL_MSGS:
                print "connecter: Got PIECE(",i,") from",connection.get_ip()
            if c.download.got_piece(i, toint(message[5:9]), [], message[9:]):
                self.got_piece(i)
            
        elif t == HASHPIECE:
            # Merkle: Handle pieces with hashes
            try:
                if len(message) <= 13:
                    if DEBUG:
                        print "Close on bad HASHPIECE: msg len"
                    connection.close()
                    return
                i = toint(message[1:5])
                if i >= self.numpieces:
                    if DEBUG:
                        print "Close on bad HASHPIECE: index out of range"
                    connection.close()
                    return
                begin = toint(message[5:9])
                len_hashlist = toint(message[9:13])
                bhashlist = message[13:13+len_hashlist]
                hashlist = bdecode(bhashlist)
                if not isinstance(hashlist, list):
                    raise AssertionError, "hashlist not list"
                for oh in hashlist:
                    if not isinstance(oh,list) or \
                    not (len(oh) == 2) or \
                    not isinstance(oh[0],int) or \
                    not isinstance(oh[1],str) or \
                    not ((len(oh[1])==20)): \
                        raise AssertionError, "hashlist entry invalid"
                piece = message[13+len_hashlist:]

                if c.download.got_piece(i, begin, hashlist, piece):
                    self.got_piece(i)
            except Exception,e:
                if DEBUG:
                    print "Close on bad HASHPIECE: exception",str(e)
                    traceback.print_exc()
                connection.close()
                return
        elif t == G2G_PIECE_XFER:
            if len(message) <= 12:
                if DEBUG:
                    print "Close on bad G2G_PIECE_XFER: msg len"
                connection.close()
                return
            if not c.use_g2g:
                if DEBUG:
                    print "Close on receiving G2G_PIECE_XFER over non-g2g connection"
                connection.close()
                return

            index = toint(message[1:5])
            begin = toint(message[5:9])
            length = toint(message[9:13])
            c.got_g2g_piece_xfer(index,begin,length)
        else:
            connection.close()


    def got_extend_message(self,connection,c,message,ut_pex_enabled):
        # connection: Encrypter.Connection; c: Connecter.Connection
        if DEBUG:
            print >>sys.stderr,"connecter: Got EXTEND message, len",len(message)
        try:
            if len(message) < 4:
                if DEBUG:
                    print "Close on bad EXTEND: msg len"
                connection.close()
                return
            ext_id = message[1]
            if ext_id == EXTEND_MSG_HANDSHAKE_ID: # Handshake:
                d = bdecode(message[2:])
                if type(d) == DictType:
                    c.got_extend_handshake(d)
                else:
                    if DEBUG:
                        print "Close on bad EXTEND: payload of handshake is not a bencoded dict"
                    connection.close()
                    return
            else:
                ext_msg_name = c.extend_msg_id_to_name(ext_id)
                if ext_msg_name is None:
                    if DEBUG:
                        print "Close on bad EXTEND: peer sent ID it didn't define in handshake"
                    connection.close()
                    return
                elif ext_msg_name == EXTEND_MSG_OVERLAYSWARM:
                    if DEBUG:
                        print "Not closing EXTEND+CHALLENGE: peer didn't read our spec right, be liberal"
                    pass
                elif ext_msg_name == EXTEND_MSG_UTORRENT_PEX and ut_pex_enabled:
                    d = bdecode(message[2:])
                    if type(d) == DictType:
                        c.got_ut_pex(d)
                    else:
                        if DEBUG:
                            print "Close on bad EXTEND: payload of handshake is not a bencoded dict"
                        connection.close()
                        return
                
                else:
                    if DEBUG:
                        print "Close on bad EXTEND: peer sent ID that maps to name we don't support"
                    connection.close()
                    return
            return
        except Exception,e:
            if DEBUG:
                print "Close on bad EXTEND: exception",str(e)
                traceback.print_exc()
            connection.close()
            return
