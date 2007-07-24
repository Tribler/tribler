# Written by Bram Cohen and Pawel Garbacki
# see LICENSE.txt for license information

import traceback,sys
from sha import sha
from types import DictType,IntType

from BitTornado.bitfield import Bitfield
from BitTornado.clock import clock
from BitTornado.bencode import bencode,bdecode
from BitTornado.__init__ import version_short,decodePeerID,TRIBLER_PEERID_LETTER
from BitTornado.BT1.convert import tobinary,toint

from MessageID import *

# 2fastbt_
from Tribler.CacheDB.CacheDBHandler import PeerDBHandler
from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.DecentralizedTracking.ut_pex import *
# _2fastbt

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
# The set of messages we support. Note that the msg ID is an int not a byte in this dict
EXTEND_HANDSHAKE_M_DICT = {EXTEND_MSG_OVERLAYSWARM:ord(CHALLENGE)}
#                           EXTEND_MSG_UTORRENT_PEX:ord(EXTEND_MSG_UTORRENT_PEX_ID)}

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

    def send_extend_ut_pex(self,payload):
        msg = EXTEND+chr(self.extend_msg_name_to_id(EXTEND_MSG_UTORRENT_PEX))+payload
        self._send_message(msg)

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
            print "Got uTorrent PEX:",d
        # TODO: add format checks
        check_ut_pex(d)
        # TODO: use peers from peer exchange
        # TODO: reply? Should send it periodically

    def get_extend_encryption(self):
        return self.hs_dict.get('e',0)
    
    def get_extend_listenport(self):
        return self.hs_dict.get('p')

    def get_ut_pex_previous_conns(self):
        return self.ut_pex_previous_conns

    def set_ut_pex_previous_conns(self,conns):
        self.ut_pex_previous_conns = conns

    def send_extend_handshake(self):
        d = {}
        d['m'] = EXTEND_HANDSHAKE_M_DICT
        d['p'] = self.connecter.mylistenport
        ver = version_short.replace('-',' ',1)
        d['v'] = ver
        d['e'] = 0  # Apparently this means we don't like uTorrent encryption
        self._send_message(EXTEND + EXTEND_MSG_HANDSHAKE_ID + bencode(d))
        if DEBUG:
            print 'sent extend: id=0+',d
            
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
            print >>sys.stderr,"encoder: peer",dns,"said he supported overlay swarm, but we can't connect to him",exc




class Connecter:
# 2fastbt_
    def __init__(self, make_upload, downloader, choker, numpieces,
            totalup, config, ratelimiter, merkle_torrent, sched = None, 
            coordinator = None, helper = None, mylistenport = None):
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
        # 2fastbt_
        self.coordinator = coordinator
        self.helper = helper
        self.round = 0
        self.mylistenport = mylistenport
        self.overlay_enabled = 1
        if 'overlay' in self.config:
            self.overlay_enabled = self.config['overlay']
        if EXTEND_MSG_UTORRENT_PEX in EXTEND_HANDSHAKE_M_DICT:
            self.sched(self.ut_pex_callback,60)

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
        for c in self.connections:
            if c.supports_extend_msg(EXTEND_MSG_UTORRENT_PEX):
                (addedconns,droppedconns) = ut_pex_get_conns_diff(self.connections,c,c.get_ut_pex_previous_conns())
                c.set_ut_pex_previous_conns(addedconns)
                payload = create_ut_pex(addedconns,droppedconns)
                c.send_ut_pex(payload)
        self.sched(self.ut_pex_callback,60)

    def got_message(self, connection, message):
        # connection: Encrypter.Connection; c: Connecter.Connection
        c = self.connections[connection]    
        t = message[0]
        # EXTEND handshake will be sent just after BT handshake, 
        # before BITFIELD even
        if t == EXTEND:
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
                    elif ext_msg_name == EXTEND_MSG_UTORRENT_PEX:
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
                    traceback.print_exc(file=sys.stderr)
                connection.close()
                return
        else:
            connection.close()
