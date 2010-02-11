# Written by Bram Cohen, Pawel Garbacki, Arno Bakker and Njaal Borch
# see LICENSE.txt for license information

import time
import sys
from types import DictType,IntType,LongType,ListType,StringType
from random import shuffle
from traceback import print_exc
from math import ceil
import socket
import urlparse

from Tribler.Core.BitTornado.bitfield import Bitfield
from Tribler.Core.BitTornado.clock import clock
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.__init__ import version_short,decodePeerID,TRIBLER_PEERID_LETTER
from Tribler.Core.BitTornado.BT1.convert import tobinary,toint

from MessageID import *

from Tribler.Core.DecentralizedTracking.ut_pex import *
from Tribler.Core.BitTornado.BT1.track import compact_ip,decompact_ip

from Tribler.Core.BitTornado.CurrentRateMeasure import Measure
from Tribler.Core.ClosedSwarm import ClosedSwarm
from Tribler.Core.Status import Status

try:
    True
except:
    True = 1
    False = 0

KICK_OLD_CLIENTS=False

DEBUG = False
DEBUG_NORMAL_MSGS = False
DEBUG_UT_PEX = False
DEBUG_MESSAGE_HANDLING = False
DEBUG_CS = False # Debug closed swarms

UNAUTH_PERMID_PERIOD = 3600

"""
Arno: 2007-02-16:
uTorrent and Bram's BitTorrent now support an extension to the protocol,
documented on http://www.bittorrent.org/beps/bep_0010.html (previously
http://www.rasterbar.com/products/libtorrent/extension_protocol.html)

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
EXTEND_MSG_G2G_V1       = 'Tr_G2G'
EXTEND_MSG_G2G_V2       = 'Tr_G2G_v2'
EXTEND_MSG_HASHPIECE    = 'Tr_hashpiece'
EXTEND_MSG_CS           = 'NS_CS'

CURRENT_LIVE_VERSION=1
EXTEND_MSG_LIVE_PREFIX  = 'Tr_LIVE_v'
LIVE_FAKE_MESSAGE_ID    = chr(254)



G2G_CALLBACK_INTERVAL = 4

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

        # G2G
        self.use_g2g = False # set to true if both sides use G2G, indicated by self.connector.use_g2g
        self.g2g_version = None 
        self.perc_sent = {}
        # batch G2G_XFER information and periodically send it out.
        self.last_perc_sent = {}

        config = self.connecter.config
        self.forward_speeds = [0] * 2
        self.forward_speeds[0] = Measure(config['max_rate_period'], config['upload_rate_fudge'])
        self.forward_speeds[1] = Measure(config['max_rate_period'], config['upload_rate_fudge'])
        
        # BarterCast counters
        self.total_downloaded = 0
        self.total_uploaded = 0
        
        self.ut_pex_first_flag = True # first time we sent a ut_pex to this peer?
        self.na_candidate_ext_ip = None
        
        self.na_candidate_ext_ip = None
        
        # RePEX counters and repexer instance field
        self.pex_received = 0 # number of PEX messages received

        # Closed swarm stuff
        # Closed swarms
        self.is_closed_swarm = False
        self.remote_is_authenticated = False
        self.remote_supports_cs = False
        status = Status.get_status_holder("LivingLab")
        self.cs_status = status.create_event("CS_protocol")
        # This is a total for all
        self.cs_status_unauth_requests = status.get_or_create_status_element("unauthorized_requests", 0)
        self.cs_status_supported = status.get_or_create_status_element("nodes_supporting_cs", 0)
        self.cs_status_not_supported = status.get_or_create_status_element("nodes_not_supporting_cs", 0)
        
        if self.connecter.is_closed_swarm:
            if DEBUG:
                print >>sys.stderr,"connecter: conn: CS: This is a closed swarm"
            self.is_closed_swarm = True
            if 'poa' in self.connecter.config:
                try:
                    from base64 import decodestring
                    #poa = self.connecter.config.get_poa()
                    poa = ClosedSwarm.POA.deserialize(decodestring(self.connecter.config['poa']))
                    #poa = self.connecter.config['poa']
                except Exception,e:
                    print_exc()
                    poa = None
            else:
                print >>sys.stderr,"connecter: conn: CS: Missing POA"
                poa = None
        
            # Need to also get the rest of the info, like my keys
            # and my POA
            my_keypair = ClosedSwarm.read_cs_keypair(self.connecter.config['eckeypairfilename'])
            self.closed_swarm_protocol = ClosedSwarm.ClosedSwarm(my_keypair,
                                                                 self.connecter.infohash,
                                                                 self.connecter.config['cs_keys'],
                                                                 poa)
            if DEBUG_CS:                                                                 
                print >>sys.stderr,"connecter: conn: CS: Closed swarm ready to start handshake"


    def get_myip(self, real=False):
        return self.connection.get_myip(real)
    
    def get_myport(self, real=False):
        return self.connection.get_myport(real)
        
    def get_ip(self, real=False):
        return self.connection.get_ip(real)

    def get_port(self, real=False):
        return self.connection.get_port(real)

    def get_id(self):
        return self.connection.get_id()

    def get_readable_id(self):
        return self.connection.get_readable_id()

    def can_send_to(self):
        if self.is_closed_swarm and not self.remote_is_authenticated:
            return False
        return True

    def close(self):
        if DEBUG:
            if self.get_ip() == self.connecter.tracker_ip:
                print >>sys.stderr,"connecter: close: live: WAAH closing SOURCE"

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
                print >>sys.stderr,'Connection: send_unchoke: CHOKE SUPPRESSED'
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
            print >>sys.stderr,"sending REQUEST to",self.get_ip()
            print >>sys.stderr,'sent request: '+str(index)+': '+str(begin)+'-'+str(begin+length)

    def send_cancel(self, index, begin, length):
        self._send_message(CANCEL + tobinary(index) + 
            tobinary(begin) + tobinary(length))
        if DEBUG_NORMAL_MSGS:
            print >>sys.stderr,'sent cancel: '+str(index)+': '+str(begin)+'-'+str(begin+length)

    def send_bitfield(self, bitfield):
        if self.can_send_to():
            self._send_message(BITFIELD + bitfield)
        else:
            self.cs_status_unauth_requests.inc()
            print >>sys.stderr,"Sending empty bitfield to unauth node"
            self._send_message(BITFIELD + Bitfield(self.connecter.numpieces).tostring())


    def send_have(self, index):
        if self.can_send_to():
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
        if not self.can_send_to():
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

                    c.queue_g2g_piece_xfer( index, begin, piece )

            if self.connecter.merkle_torrent:
                hashpiece_msg_id = self.his_extend_msg_name_to_id(EXTEND_MSG_HASHPIECE)
                bhashlist = bencode(hashlist)
                if hashpiece_msg_id is None:
                    # old Tribler <= 4.5.2 style
                    self.partial_message = ''.join((
                                    tobinary(1+4+4+4+len(bhashlist)+len(piece)), HASHPIECE,
                                    tobinary(index), tobinary(begin), tobinary(len(bhashlist)), bhashlist, piece.tostring() ))
                else:
                    # Merkle BEP
                    self.partial_message = ''.join((
                                    tobinary(2+4+4+4+len(bhashlist)+len(piece)), EXTEND, hashpiece_msg_id,
                                    tobinary(index), tobinary(begin), tobinary(len(bhashlist)), bhashlist, piece.tostring() ))
                    
            else:
                self.partial_message = ''.join((
                            tobinary(len(piece) + 9), PIECE, 
                            tobinary(index), tobinary(begin), piece.tostring()))
            if DEBUG_NORMAL_MSGS:
                print >>sys.stderr,'sending chunk: '+str(index)+': '+str(begin)+'-'+str(begin+len(piece))

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
    # Extension protocol support
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
            newm = {}
            for key,val in m.iteritems():
                if type(val) != IntType:
                    # Fix for BitTorrent 4.27.2e
                    if type(val) == StringType:
                        newm[key]= ord(val)
                        continue
                    else:
                        raise ValueError('Message ID in m-dict not int')
                newm[key]= val

            if not 'm' in self.extend_hs_dict:
                self.extend_hs_dict['m'] = {}
            # Note: we store the dict without converting the msg IDs to bytes.
            self.extend_hs_dict['m'].update(newm)
            if self.connecter.overlay_enabled and EXTEND_MSG_OVERLAYSWARM in self.extend_hs_dict['m']:
                # This peer understands our overlay swarm extension
                if self.connection.locally_initiated:
                    if DEBUG:
                        print >>sys.stderr,"connecter: Peer supports Tr_OVERLAYSWARM, attempt connection"
                    self.connect_overlay()
                    
            if EXTEND_MSG_CS in self.extend_hs_dict['m']:
                self.remote_supports_cs = True
                self.cs_status_supported.inc()
                if self.is_closed_swarm and self.connection.locally_initiated:
                    self.start_cs_handshake()
            else:
                self.remote_supports_cs = False
                self.cs_status_not_supported.inc()
                if DEBUG:
                    print >>sys.stderr,"connecter: conn: Remote node does not support CS, flagging CS as done"
                self.connecter.cs_handshake_completed()
                status = Status.get_status_holder("LivingLab")
                status.add_event(self.cs_status)
                self.cs_status = status.create_event("CS_protocol")
                
                
            if self.connecter.use_g2g and (EXTEND_MSG_G2G_V1 in self.extend_hs_dict['m'] or EXTEND_MSG_G2G_V2 in self.extend_hs_dict['m']):
                # Both us and the peer want to use G2G
                if self.connection.locally_initiated:
                    if DEBUG:
                        print >>sys.stderr,"connecter: Peer supports Tr_G2G"

                self.use_g2g = True
                if EXTEND_MSG_G2G_V2 in self.extend_hs_dict['m']:
                    self.g2g_version = EXTEND_MSG_G2G_V2
                else:
                    self.g2g_version = EXTEND_MSG_G2G_V1
            
            # LIVEHACK
            if KICK_OLD_CLIENTS:
                peerhaslivekey = False
                for key in self.extend_hs_dict['m']:
                    if key.startswith(EXTEND_MSG_LIVE_PREFIX):
                        peerhaslivekey = True
                        livever = int(key[len(EXTEND_MSG_LIVE_PREFIX):])
                        if livever < CURRENT_LIVE_VERSION:
                            raise ValueError("Too old LIVE VERSION "+livever)
                        else:
                            print >>sys.stderr,"Connecter: live: Keeping connection to up-to-date peer v",livever,self.get_ip()
                        
                if not peerhaslivekey:
                    if self.get_ip() == self.connecter.tracker_ip:
                        # Keep connection to tracker / source
                        print >>sys.stderr,"Connecter: live: Keeping connection to SOURCE",self.connecter.tracker_ip 
                    else:
                        raise ValueError("Kicking old LIVE peer "+self.get_ip())

        # 'p' is peer's listen port, 'v' is peer's version, all optional
        # 'e' is used by uTorrent to show it prefers encryption (whatever that means)
        # See http://www.bittorrent.org/beps/bep_0010.html
        for key in ['p','e', 'yourip','ipv4','ipv6','reqq']:
            if key in d:
                self.extend_hs_dict[key] = d[key]
        
        #print >>sys.stderr,"connecter: got_extend_hs: keys",d.keys()

        # If he tells us our IP, record this and see if we get a majority vote on it
        if 'yourip' in d:
            try:
                yourip = decompact_ip(d['yourip'])

                try:
                    from Tribler.Core.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
                    dmh = DialbackMsgHandler.getInstance()
                    dmh.network_btengine_extend_yourip(yourip)
                except:
                    if DEBUG:
                        print_exc()
                    pass
                
                if 'same_nat_try_internal' in self.connecter.config and self.connecter.config['same_nat_try_internal']:
                    if 'ipv4' in d:
                        self.na_check_for_same_nat(yourip)
            except:
                print_exc()
        
        # RePEX: Tell repexer we have received an extended handshake
        repexer = self.connecter.repexer
        if repexer:
            try:
                version = d.get('v',None)
                repexer.got_extend_handshake(self, version)
            except:
                print_exc()

    def his_extend_msg_name_to_id(self,ext_name):
        """ returns the message id (byte) for the given message name or None """
        val = self.extend_hs_dict['m'].get(ext_name)
        if val is None:
            return val
        else:
            return chr(val)

    def get_extend_encryption(self):
        return self.extend_hs_dict.get('e',0)
    
    def get_extend_listenport(self):
        return self.extend_hs_dict.get('p')

    def is_tribler_peer(self):
        client, version = decodePeerID(self.connection.id)
        return client == TRIBLER_PEERID_LETTER

    def send_extend_handshake(self):

        # NETWORK AWARE
        hisip = self.connection.get_ip(real=True)
        ipv4 = None
        if self.connecter.config.get('same_nat_try_internal',0):
            is_tribler_peer = self.is_tribler_peer()
            print >>sys.stderr,"connecter: send_extend_hs: Peer is Tribler client",is_tribler_peer
            if is_tribler_peer:
                # If we're connecting to a Tribler peer, show our internal IP address
                # as 'ipv4'.
                ipv4 = self.get_ip(real=True)
        
        # See: http://www.bittorrent.org/beps/bep_0010.html
        d = {}
        d['m'] = self.connecter.EXTEND_HANDSHAKE_M_DICT
        d['p'] = self.connecter.mylistenport
        ver = version_short.replace('-',' ',1)
        d['v'] = ver
        d['e'] = 0  # Apparently this means we don't like uTorrent encryption
        d['yourip'] = compact_ip(hisip)
        if ipv4 is not None:
            # Only send IPv4 when necessary, we prefer this peer to use this addr.
            d['ipv4'] = compact_ip(ipv4) 
        
        self._send_message(EXTEND + EXTEND_MSG_HANDSHAKE_ID + bencode(d))
        if DEBUG:
            print >>sys.stderr,'connecter: sent extend: id=0+',d,"yourip",hisip,"ipv4",ipv4

    #
    # ut_pex support
    #
    def got_ut_pex(self,d):
        if DEBUG_UT_PEX:
            print >>sys.stderr,"connecter: Got uTorrent PEX:",d
        (same_added_peers,added_peers,dropped_peers) = check_ut_pex(d)
        
        # RePEX: increase counter
        self.pex_received += 1
        
        # RePEX: for now, we pass the whole PEX dict to the repexer and
        # let it decode it. The reason is that check_ut_pex's interface
        # has recently changed, currently returning a triple to prefer
        # Tribler peers. The repexer, however, might have different 
        # interests (e.g., storinng all flags). To cater to both interests,
        # check_ut_pex needs to be rewritten. 
        repexer = self.connecter.repexer
        if repexer:
            try:
                repexer.got_ut_pex(self, d)
            except:
                print_exc()
            return
        
        # DoS protection: we're accepting IP addresses from 
        # an untrusted source, so be a bit careful
        mx = self.connecter.ut_pex_max_addrs_from_peer
        if DEBUG_UT_PEX:
            print >>sys.stderr,"connecter: Got",len(added_peers),"peers via uTorrent PEX, using max",mx
            
        # for now we have a strong bias towards Tribler peers
        if self.is_tribler_peer():
            shuffle(same_added_peers)
            shuffle(added_peers)
            sample_peers = same_added_peers
            sample_peers.extend(added_peers)
        else:
            sample_peers = same_added_peers
            sample_peers.extend(added_peers)
            shuffle(sample_peers)
        
        # Take random sample of mx peers
        sample_added_peers_with_id = []

        # Put the sample in the format desired by Encoder.start_connections()
        for dns in sample_peers[:mx]:
            peer_with_id = (dns, 0)
            sample_added_peers_with_id.append(peer_with_id)
        if len(sample_added_peers_with_id) > 0:
            if DEBUG_UT_PEX:
                print >>sys.stderr,"connecter: Starting ut_pex conns to",len(sample_added_peers_with_id)
            self.connection.Encoder.start_connections(sample_added_peers_with_id)

    def get_extend_encryption(self):
        return self.extend_hs_dict.get('e',0)
    
    def get_extend_listenport(self):
        return self.extend_hs_dict.get('p')

    def send_extend_handshake(self):
        
        d = {}
        d['m'] = self.connecter.EXTEND_HANDSHAKE_M_DICT
        d['p'] = self.connecter.mylistenport
        ver = version_short.replace('-',' ',1)
        d['v'] = ver
        d['e'] = 0  # Apparently this means we don't like uTorrent encryption
        self._send_message(EXTEND + EXTEND_MSG_HANDSHAKE_ID + bencode(d))
        if DEBUG:
            print >>sys.stderr,'connecter: sent extend: id=0+',d

    def send_extend_ut_pex(self,payload):
        msg = EXTEND+self.his_extend_msg_name_to_id(EXTEND_MSG_UTORRENT_PEX)+payload
        self._send_message(msg)
            
    def first_ut_pex(self):
        if self.ut_pex_first_flag:
            self.ut_pex_first_flag = False
            return True
        else:
            return False

    def _send_cs_message(self, cs_list):
        if DEBUG_CS:
            print >>sys.stderr,"connecter: conn: _send_cs_message",cs_list[0]
        blist = bencode(cs_list)
        self._send_message(EXTEND + self.his_extend_msg_name_to_id(EXTEND_MSG_CS) + blist)
        
    def got_cs_message(self, cs_list):
        if DEBUG_CS:
            print >>sys.stderr,"connecter: conn: got_cs_message",cs_list[0]
        if not self.is_closed_swarm:
            raise Exception("Got ClosedSwarm message, but this swarm is not closed")

        # Process incoming closed swarm messages
        t = cs_list[0]
        if t == CS_CHALLENGE_A:
            if DEBUG_CS:
                print >>sys.stderr,"connecter: conn: CS: Got initial challenge"
            # Got a challenge to authenticate to participate in a closed swarm
            try:
                response = self.closed_swarm_protocol.b_create_challenge(cs_list)
                self._send_cs_message(response)
            except Exception,e:
                self.cs_status.add_value("CS_bad_initial_challenge")
                if DEBUG_CS:
                    print >>sys.stderr,"connecter: conn: CS: Bad initial challenge:",e
        elif t == CS_CHALLENGE_B:
            if DEBUG_CS:
                print >>sys.stderr,"connecter: conn: CS: Got return challenge"
            try:
                response = self.closed_swarm_protocol.a_provide_poa_message(cs_list)
                self.remote_is_authenticated = self.closed_swarm_protocol.is_remote_node_authorized()
                if DEBUG_CS:
                    print >>sys.stderr,"connecter: conn: CS: Remote node authorized:",self.remote_is_authenticated
                self._send_cs_message(response)
            except Exception,e:
                self.cs_status.add_value("CS_bad_return_challenge")
                if DEBUG_CS:
                    print >>sys.stderr,"connecter: conn: CS: Bad return challenge",e
                print_exc()
                
        elif t == CS_POA_EXCHANGE_A:
            if DEBUG_CS:
               print >>sys.stderr,"connecter: conn: CS:Got POA from A"
            try:
                response = self.closed_swarm_protocol.b_provide_poa_message(cs_list)
                self.remote_is_authenticated = self.closed_swarm_protocol.is_remote_node_authorized()
                if DEBUG_CS:
                    print >>sys.stderr,"connecter: conn: CS: Remote node authorized:",self.remote_is_authenticated
                if response:
                    self._send_cs_message(response)
            except Exception,e:
                self.cs_status.add_value("CS_bad_POA_EXCHANGE_A")
                if DEBUG_CS:
                   print >>sys.stderr,"connecter: conn: CS: Bad POA from A:",e
                
        elif t == CS_POA_EXCHANGE_B:
            try:
                self.closed_swarm_protocol.a_check_poa_message(cs_list)
                self.remote_is_authenticated = self.closed_swarm_protocol.is_remote_node_authorized()
                if DEBUG_CS:
                   print >>sys.stderr,"connecter: conn: CS: Remote node authorized:",self.remote_is_authenticated
            except Exception,e:
                self.cs_status.add_value("CS_bad_POA_EXCHANGE_B")
                if DEBUG_CS:
                   print >>sys.stderr,"connecter: conn: CS: Bad POA from B:",e

        if not self.closed_swarm_protocol.is_incomplete():
            self.connecter.cs_handshake_completed()
            status = Status.get_status_holder("LivingLab")
            # Don't need to add successful CS event

    #
    # Give-2-Get
    #
    def g2g_sent_piece_part( self, c, index, begin, hashlist, piece ):
        """ Keeps a record of the fact that we sent piece index[begin:begin+chunk]. """

        wegaveperc = float(len(piece))/float(self.connecter.piece_size)
        if index in self.perc_sent:
            self.perc_sent[index] = self.perc_sent[index] + wegaveperc 
        else:
            self.perc_sent[index] = wegaveperc
    
    
    def queue_g2g_piece_xfer(self,index,begin,piece):
        """ Queue the fact that we sent piece index[begin:begin+chunk] for
        tranmission to peers 
        """
        if self.g2g_version == EXTEND_MSG_G2G_V1:
            self.send_g2g_piece_xfer_v1(index,begin,piece)
            return
        
        perc = float(len(piece))/float(self.connecter.piece_size)
        if index in self.last_perc_sent:
            self.last_perc_sent[index] = self.last_perc_sent[index] + perc 
        else:
            self.last_perc_sent[index] = perc

    def dequeue_g2g_piece_xfer(self):
        """ Send queued information about pieces we sent to peers. Called
        periodically.
        """ 
        psf = float(self.connecter.piece_size)
        ppdict = {}
        
        #print >>sys.stderr,"connecter: g2g dq: orig",self.last_perc_sent
        
        for index,perc in self.last_perc_sent.iteritems():
            # due to rerequests due to slow pieces the sum can be above 1.0
            capperc = min(1.0,perc) 
            percb = chr(int((100.0 * capperc)))
            # bencode can't deal with int keys
            ppdict[str(index)] = percb
        self.last_perc_sent = {}
        
        #print >>sys.stderr,"connecter: g2g dq: dest",ppdict
        
        if len(ppdict) > 0:
            self.send_g2g_piece_xfer_v2(ppdict)

    def send_g2g_piece_xfer_v1(self,index,begin,piece):
        """ Send fact that we sent piece index[begin:begin+chunk] to a peer
        to all peers (G2G V1).
        """
        self._send_message(self.his_extend_msg_name_to_id(EXTEND_MSG_G2G_V1) + tobinary(index) + tobinary(begin) + tobinary(len(piece)))

    def send_g2g_piece_xfer_v2(self,ppdict):
        """ Send list of facts that we sent pieces to all peers (G2G V2). """
        blist = bencode(ppdict)
        self._send_message(EXTEND + self.his_extend_msg_name_to_id(EXTEND_MSG_G2G_V2) + blist)

    def got_g2g_piece_xfer_v1(self,index,begin,length):
        """ Got a G2G_PIECE_XFER message in V1 format. """
        hegaveperc = float(length)/float(self.connecter.piece_size)
        self.g2g_peer_forwarded_piece_part(index,hegaveperc)

    def got_g2g_piece_xfer_v2(self,ppdict):
        """ Got a G2G_PIECE_XFER message in V2 format. """
        for indexstr,hegavepercb in ppdict.iteritems():
            index = int(indexstr)
            hegaveperc = float(ord(hegavepercb))/100.0
            self.g2g_peer_forwarded_piece_part(index,hegaveperc)

    def g2g_peer_forwarded_piece_part(self,index,hegaveperc):
        """ Processes this peer forwarding piece i[begin:end] to a grandchild. """
        # Reward for forwarding data in general
        length = ceil(hegaveperc * float(self.connecter.piece_size))
        self.forward_speeds[1].update_rate(length)

        if index not in self.perc_sent:
            # piece came from disk
            return

        # Extra reward if its data we sent
        wegaveperc = self.perc_sent[index]
        overlapperc = wegaveperc * hegaveperc
        overlap = ceil(overlapperc * float(self.connecter.piece_size))
        if overlap > 0:
            self.forward_speeds[0].update_rate( overlap )

    def g2g_score( self ):
        return [x.get_rate() for x in self.forward_speeds]


    #
    # SecureOverlay support
    #
    def connect_overlay(self):
        if DEBUG:
            print >>sys.stderr,"connecter: Initiating overlay connection"
        if not self.initiated_overlay:
            from Tribler.Core.Overlay.SecureOverlay import SecureOverlay
            
            self.initiated_overlay = True
            so = SecureOverlay.getInstance()
            so.connect_dns(self.connection.dns,self.network_connect_dns_callback)

    def network_connect_dns_callback(self,exc,dns,permid,selversion):
        # WARNING: WILL BE CALLED BY NetworkThread
        if exc is not None:
            print >>sys.stderr,"connecter: peer",dns,"said he supported overlay swarm, but we can't connect to him",exc

    def start_cs_handshake(self):
        try:
            if DEBUG_CS:
                print >>sys.stderr,"connecter: conn: CS: Initiating Closed Swarm Handshake"
            challenge = self.closed_swarm_protocol.a_create_challenge()
            self._send_cs_message(challenge)
        except Exception,e:
            print >>sys.stderr,"connecter: conn: CS: Bad initial challenge:",e
        

    #
    # NETWORK AWARE
    #
    def na_check_for_same_nat(self,yourip):
        """ See if peer is local, e.g. behind same NAT, same AS or something.
        If so, try to optimize:
        - Same NAT -> reconnect to use internal network 
        """
        hisip = self.connection.get_ip(real=True)
        if hisip == yourip:
            # Do we share the same NAT?
            myextip = self.connecter.get_extip_func(unknowniflocal=True)
            myintip = self.get_ip(real=True)

            if DEBUG:
                print >>sys.stderr,"connecter: na_check_for_same_nat: his",hisip,"myext",myextip,"myint",myintip
            
            if hisip != myintip or hisip == '127.0.0.1': # to allow testing
                # He can't fake his source addr, so we're not running on the
                # same machine,

                # He may be quicker to determine we should have a local
                # conn, so prepare for his connection in advance.
                #
                if myextip is None:
                    # I don't known my external IP and he's not on the same
                    # machine as me. yourip could be our real external IP, test.
                    if DEBUG:
                        print >>sys.stderr,"connecter: na_check_same_nat: Don't know my ext ip, try to loopback to",yourip,"to see if that's me"
                    self.na_start_loopback_connection(yourip)
                elif hisip == myextip:
                    # Same NAT. He can't fake his source addr.
                    # Attempt local network connection
                    if DEBUG:
                        print >>sys.stderr,"connecter: na_check_same_nat: Yes, trying to connect via internal"
                    self.na_start_internal_connection()
                else: 
                    # hisip != myextip
                    # He claims we share the same IP, but I think my ext IP
                    # is something different. Either he is lying or I'm
                    # mistaken, test
                    if DEBUG:
                        print >>sys.stderr,"connecter: na_check_same_nat: Maybe, me thinks not, try to loopback to",yourip
                    self.na_start_loopback_connection(yourip)
                
                
    def na_start_loopback_connection(self,yourip):
        """ Peer claims my external IP is "yourip". Try to connect back to myself """
        if DEBUG:
            print >>sys.stderr,"connecter: na_start_loopback: Checking if my ext ip is",yourip
        self.na_candidate_ext_ip = yourip
        
        dns = (yourip,self.connecter.mylistenport)
        self.connection.Encoder.start_connection(dns,0,forcenew=True)

    def na_got_loopback(self,econnection):
        """ Got a connection with my peer ID. Check that this is indeed me looping
        back to myself. No man-in-the-middle attacks protection. This is complex
        if we're also connecting to ourselves because of a stale tracker 
        registration. Window of opportunity is small. 
        """
        himismeip = econnection.get_ip(real=True)
        if DEBUG:
            print >>sys.stderr,"connecter: conn: na_got_loopback:",himismeip,self.na_candidate_ext_ip
        if self.na_candidate_ext_ip == himismeip:
            self.na_start_internal_connection()
                    

    def na_start_internal_connection(self):
        """ Reconnect to peer using internal network """
        if DEBUG:
            print >>sys.stderr,"connecter: na_start_internal_connection"
        
        # Doesn't really matter who initiates. Letting other side do it makes
        # testing easier.
        if not self.is_locally_initiated():
            
            hisip = decompact_ip(self.extend_hs_dict['ipv4'])
            hisport = self.extend_hs_dict['p']
            
            # For testing, see Tribler/Test/test_na_extend_hs.py
            if hisip == '224.4.8.1' and hisport == 4810:
                hisip = '127.0.0.1'
                hisport = 4811
                
            self.connection.na_want_internal_conn_from = hisip        
            
            hisdns = (hisip,hisport)
            if DEBUG:
                print >>sys.stderr,"connecter: na_start_internal_connection to",hisdns
            self.connection.Encoder.start_connection(hisdns,0)

    def na_get_address_distance(self):
        return self.connection.na_get_address_distance()

    def is_live_source(self):
        if self.connecter.live_streaming:
            if self.get_ip() == self.connecter.tracker_ip:
                return True
        return False
            

class Connecter:
# 2fastbt_
    def __init__(self, make_upload, downloader, choker, numpieces, piece_size,
            totalup, config, ratelimiter, merkle_torrent, sched = None, 
            coordinator = None, helper = None, get_extip_func = lambda: None, mylistenport = None, use_g2g = False, infohash=None, tracker=None, live_streaming = False):

        self.downloader = downloader
        self.make_upload = make_upload
        self.choker = choker
        self.numpieces = numpieces
        self.piece_size = piece_size
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
        self.get_extip_func = get_extip_func
        self.mylistenport = mylistenport
        self.infohash = infohash
        self.live_streaming = live_streaming
        self.tracker = tracker
        try:
            (scheme, netloc, path, pars, query, _fragment) = urlparse.urlparse(self.tracker)
            host = netloc.split(':')[0] 
            self.tracker_ip = socket.getaddrinfo(host,None)[0][4][0]
        except:
            print_exc()
            self.tracker_ip = None
        #print >>sys.stderr,"Connecter: live: source/tracker is",self.tracker_ip
        
        self.overlay_enabled = 0
        if self.config['overlay']:
            self.overlay_enabled = True

        if DEBUG:
            if self.overlay_enabled:
                print >>sys.stderr,"connecter: Enabling overlay"
            else:
                print >>sys.stderr,"connecter: Disabling overlay"
            
        self.ut_pex_enabled = 0
        if 'ut_pex_max_addrs_from_peer' in self.config:
            self.ut_pex_max_addrs_from_peer = self.config['ut_pex_max_addrs_from_peer']
            self.ut_pex_enabled = self.ut_pex_max_addrs_from_peer > 0
        self.ut_pex_previous_conns = [] # last value of 'added' field for all peers
            
        if DEBUG_UT_PEX:
            if self.ut_pex_enabled:
                print >>sys.stderr,"connecter: Enabling uTorrent PEX",self.ut_pex_max_addrs_from_peer
            else:
                print >>sys.stderr,"connecter: Disabling uTorrent PEX"

        # The set of messages we support. Note that the msg ID is an int not a byte in 
        # this dict.
        self.EXTEND_HANDSHAKE_M_DICT = {}
        
        # Say in the EXTEND handshake that we support Closed swarms
        if DEBUG:
            print >>sys.stderr,"connecter: I support Closed Swarms"
        d = {EXTEND_MSG_CS:ord(CS_CHALLENGE_A)}
        self.EXTEND_HANDSHAKE_M_DICT.update(d)

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
            d = {EXTEND_MSG_G2G_V2:ord(G2G_PIECE_XFER)}
            self.EXTEND_HANDSHAKE_M_DICT.update(d)
            self.sched(self.g2g_callback,G2G_CALLBACK_INTERVAL)
        if self.merkle_torrent:
            d = {EXTEND_MSG_HASHPIECE:ord(HASHPIECE)}
            self.EXTEND_HANDSHAKE_M_DICT.update(d)
            
        # LIVEHACK
        livekey = EXTEND_MSG_LIVE_PREFIX+str(CURRENT_LIVE_VERSION)
        d = {livekey:ord(LIVE_FAKE_MESSAGE_ID)}
        self.EXTEND_HANDSHAKE_M_DICT.update(d)

        if DEBUG:
            print >>sys.stderr,"Connecter: EXTEND: my dict",self.EXTEND_HANDSHAKE_M_DICT

        # BarterCast
        if config['overlay']:
            from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
            
            self.overlay_bridge = OverlayThreadingBridge.getInstance()
        else:
            self.overlay_bridge = None
            
        # RePEX
        self.repexer = None # Should this be called observer instead?
            
        # Closed Swarm stuff
        self.is_closed_swarm = False
        self.cs_post_func = None
        if 'cs_keys' in self.config:
            if self.config['cs_keys'] != None:
                if len(self.config['cs_keys']) == 0:
                    if DEBUG_CS:
                        print >>sys.stderr, "connecter: cs_keys is empty"
                else:
                    if DEBUG_CS:
                       print >>sys.stderr, "connecter: This is a closed swarm  - has cs_keys"
                    self.is_closed_swarm = True


    def how_many_connections(self):
        return len(self.connections)

    def connection_made(self, connection):

        assert connection
        c = Connection(connection, self)
        self.connections[connection] = c
        
        # RePEX: Inform repexer connection is made
        repexer = self.repexer
        if repexer:
            try:
                repexer.connection_made(c,connection.supports_extend_messages())
                if c.closed:
                    # The repexer can close the connection in certain cases.
                    # If so, we abort further execution of this function.
                    return c
            except:
                print_exc()
        
        if connection.supports_extend_messages():
            # The peer either supports our overlay-swarm extension or 
            # the utorrent extended protocol.
            
            [client,version] = decodePeerID(connection.id)
            
            if DEBUG:
                print >>sys.stderr,"connecter: Peer is client",client,"version",version,c.get_ip()
            
            if self.overlay_enabled and client == TRIBLER_PEERID_LETTER and version <= '3.5.0' and connection.locally_initiated:
                # Old Tribler, establish overlay connection<
                if DEBUG:
                    print >>sys.stderr,"connecter: Peer is previous Tribler version, attempt overlay connection"
                c.connect_overlay()
            elif self.ut_pex_enabled:
                # EXTEND handshake must be sent just after BT handshake, 
                # before BITFIELD even
                c.send_extend_handshake()
                
        #TODO: overlay swarm also needs upload and download to control transferring rate
        # If this is a closed swarm, don't do this now - will be done on completion of the CS protocol!
        c.upload = self.make_upload(c, self.ratelimiter, self.totalup)
        c.download = self.downloader.make_download(c)
        if not self.is_closed_swarm:
            if DEBUG_CS:
               print >>sys.stderr,"connecter: connection_made: Freeing choker!"
            self.choker.connection_made(c)
        else:
            if DEBUG_CS:
                print >>sys.stderr,"connecter: connection_made: Will free choker later"
            self.choker.add_connection(c)
            #self.cs_post_func = lambda:self.choker.connection_made(c)
            #self.cs_post_func = lambda:self.choker.start_connection(c)
            self.cs_post_func = lambda:self._cs_completed(c)

        return c

    def connection_lost(self, connection):
        c = self.connections[connection]

        # RePEX: inform repexer of closed connection
        repexer = self.repexer
        if repexer:
            try:
                repexer.connection_closed(c)
            except:
                print_exc()

        ######################################
        # BarterCast
        if self.overlay_bridge is not None:
            ip = c.get_ip(False)       
            port = c.get_port(False)   
            down_kb = int(c.total_downloaded / 1024)
            up_kb = int(c.total_uploaded / 1024)
            
            if DEBUG:
                print >> sys.stderr, "bartercast: attempting database update, adding olthread"
            
            olthread_bartercast_conn_lost_lambda = lambda:olthread_bartercast_conn_lost(ip,port,down_kb,up_kb)
            self.overlay_bridge.add_task(olthread_bartercast_conn_lost_lambda,0)
        else:
            if DEBUG:
                print >> sys.stderr, "bartercast: no overlay bridge found"
            
        #########################
        
        if DEBUG:
            if c.get_ip() == self.tracker_ip:
                print >>sys.stderr,"connecter: connection_lost: live: WAAH2 closing SOURCE"
            
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

    def our_extend_msg_id_to_name(self,ext_id):
        """ find the name for the given message id (byte) """
        for key,val in self.EXTEND_HANDSHAKE_M_DICT.iteritems():
            if val == ord(ext_id):
                return key
        return None

    def get_ut_pex_conns(self):
        conns = []
        for conn in self.connections.values():
            if conn.get_extend_listenport() is not None:
                conns.append(conn)
        return conns
            
    def get_ut_pex_previous_conns(self):
        return self.ut_pex_previous_conns

    def set_ut_pex_previous_conns(self,conns):
        self.ut_pex_previous_conns = conns

    def ut_pex_callback(self):
        """ Periocially send info about the peers you know to the other peers """
        if DEBUG_UT_PEX:
            print >>sys.stderr,"connecter: Periodic ut_pex update"
            
        currconns = self.get_ut_pex_conns()
        (addedconns,droppedconns) = ut_pex_get_conns_diff(currconns,self.get_ut_pex_previous_conns())
        self.set_ut_pex_previous_conns(currconns)
        if DEBUG_UT_PEX:
            for conn in addedconns:
                print >>sys.stderr,"connecter: ut_pex: Added",conn.get_ip(),conn.get_extend_listenport()
            for conn in droppedconns:
                print >>sys.stderr,"connecter: ut_pex: Dropped",conn.get_ip(),conn.get_extend_listenport()
            
        for c in currconns:
            if c.supports_extend_msg(EXTEND_MSG_UTORRENT_PEX):
                try:
                    if DEBUG_UT_PEX:
                        print >>sys.stderr,"connecter: ut_pex: Creating msg for",c.get_ip(),c.get_extend_listenport()
                    if c.first_ut_pex():
                        aconns = currconns
                        dconns = []
                    else:
                        aconns = addedconns
                        dconns = droppedconns
                    payload = create_ut_pex(aconns,dconns,c)    
                    c.send_extend_ut_pex(payload)
                except:
                    print_exc()
        self.sched(self.ut_pex_callback,60)

    def g2g_callback(self):
        try:
            self.sched(self.g2g_callback,G2G_CALLBACK_INTERVAL)
            for c in self.connections.itervalues():
                if not c.use_g2g:
                    continue
    
                c.dequeue_g2g_piece_xfer()
        except:
            print_exc()

            
    def got_hashpiece(self, connection, message):
        """ Process Merkle hashpiece message. Note: EXTEND byte has been 
        stripped, it starts with peer's Tr_hashpiece id for historic reasons ;-)
        """
        try:
            c = self.connections[connection]
            
            if len(message) <= 13:
                if DEBUG:
                    print >>sys.stderr,"Close on bad HASHPIECE: msg len"
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                if DEBUG:
                    print >>sys.stderr,"Close on bad HASHPIECE: index out of range"
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

            if DEBUG_NORMAL_MSGS:
                print >>sys.stderr,"connecter: Got HASHPIECE",i,begin

            if c.download.got_piece(i, begin, hashlist, piece):
                self.got_piece(i)
        except Exception,e:
            if DEBUG:
                print >>sys.stderr,"Close on bad HASHPIECE: exception",str(e)
                print_exc()
            connection.close()

    # NETWORK AWARE
    def na_got_loopback(self,econnection):
        if DEBUG:
            print >>sys.stderr,"connecter: na_got_loopback: Got connection from",econnection.get_ip(),econnection.get_port()
        for c in self.connections.itervalues():
            ret = c.na_got_loopback(econnection)
            if ret is not None:
                return ret
        return False

    def na_got_internal_connection(self,origconn,newconn):
        """ This is called only at the initiator side of the internal conn.
        Doesn't matter, only one is enough to close the original connection.
        """
        if DEBUG:
            print >>sys.stderr,"connecter: na_got_internal: From",newconn.get_ip(),newconn.get_port()
        
        origconn.close()


    def got_message(self, connection, message):
        # connection: Encrypter.Connection; c: Connecter.Connection
        c = self.connections[connection]    
        t = message[0]
        # EXTEND handshake will be sent just after BT handshake, 
        # before BITFIELD even

        if DEBUG_MESSAGE_HANDLING:
            st = time.time()

        if DEBUG_NORMAL_MSGS:
            print >>sys.stderr,"connecter: Got",getMessageName(t),connection.get_ip()
        
        if t == EXTEND:
            self.got_extend_message(connection,c,message,self.ut_pex_enabled)
            return

        # If this is a closed swarm and we have not authenticated the 
        # remote node, we must NOT GIVE IT ANYTHING!
        #if self.is_closed_swarm and c.closed_swarm_protocol.is_incomplete():
            #print >>sys.stderr, "connecter: Remote node not authorized, ignoring it"
            #return

        if self.is_closed_swarm and c.can_send_to():
            c.got_anything = False # Is this correct or does it break something?
            
        if t == BITFIELD and c.got_anything:
            if DEBUG:
                print >>sys.stderr,"Close on BITFIELD"
            connection.close()
            return
        c.got_anything = True
        if (t in [CHOKE, UNCHOKE, INTERESTED, NOT_INTERESTED] and 
                len(message) != 1):
            if DEBUG:
                print >>sys.stderr,"Close on bad (UN)CHOKE/(NOT_)INTERESTED",t
            connection.close()
            return
        if t == CHOKE:
            if DEBUG_NORMAL_MSGS:
                print >>sys.stderr,"connecter: Got CHOKE from",connection.get_ip()
            c.download.got_choke()
        elif t == UNCHOKE:
            if DEBUG_NORMAL_MSGS:
                print >>sys.stderr,"connecter: Got UNCHOKE from",connection.get_ip()
            c.download.got_unchoke()
        elif t == INTERESTED:
            if DEBUG_NORMAL_MSGS:
                print >>sys.stderr,"connecter: Got INTERESTED from",connection.get_ip()
            if c.upload is not None:
                c.upload.got_interested()
        elif t == NOT_INTERESTED:
            c.upload.got_not_interested()
        elif t == HAVE:
            if len(message) != 5:
                if DEBUG:
                    print >>sys.stderr,"Close on bad HAVE: msg len"
                connection.close()
                return
            i = toint(message[1:])
            if i >= self.numpieces:
                if DEBUG:
                    print >>sys.stderr,"Close on bad HAVE: index out of range"
                connection.close()
                return
            if DEBUG_NORMAL_MSGS:
                print >>sys.stderr,"connecter: Got HAVE(",i,") from",connection.get_ip()
            c.download.got_have(i)
        elif t == BITFIELD:
            if DEBUG_NORMAL_MSGS:
                print >>sys.stderr,"connecter: Got BITFIELD from",connection.get_ip()
            try:
                b = Bitfield(self.numpieces, message[1:],calcactiveranges=self.live_streaming)
            except ValueError:
                if DEBUG:
                    print >>sys.stderr,"Close on bad BITFIELD"
                connection.close()
                return
            if c.download is not None:
                c.download.got_have_bitfield(b)
        elif t == REQUEST:
            if not c.can_send_to():
                self.cs_status_unauth_requests.inc()
                print >> sys.stderr,"Got REQUEST but remote node is not authenticated"
                return # TODO: Do this better

            if len(message) != 13:
                if DEBUG:
                    print >>sys.stderr,"Close on bad REQUEST: msg len"
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                if DEBUG:
                    print >>sys.stderr,"Close on bad REQUEST: index out of range"
                connection.close()
                return
            if DEBUG_NORMAL_MSGS:
                print >>sys.stderr,"connecter: Got REQUEST(",i,") from",connection.get_ip()
            c.got_request(i, toint(message[5:9]), toint(message[9:]))
        elif t == CANCEL:
            if len(message) != 13:
                if DEBUG:
                    print >>sys.stderr,"Close on bad CANCEL: msg len"
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                if DEBUG:
                    print >>sys.stderr,"Close on bad CANCEL: index out of range"
                connection.close()
                return
            c.upload.got_cancel(i, toint(message[5:9]), 
                toint(message[9:]))
        elif t == PIECE:
            if len(message) <= 9:
                if DEBUG:
                    print >>sys.stderr,"Close on bad PIECE: msg len"
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                if DEBUG:
                    print >>sys.stderr,"Close on bad PIECE: msg len"
                connection.close()
                return
            if DEBUG_NORMAL_MSGS: # or connection.get_ip().startswith("192"):
                print >>sys.stderr,"connecter: Got PIECE(",i,") from",connection.get_ip()
            #if connection.get_ip().startswith("192"):
            #    print >>sys.stderr,"@",
            try:
                if c.download.got_piece(i, toint(message[5:9]), [], message[9:]):
                    self.got_piece(i)
            except Exception,e:
                if DEBUG:
                    print >>sys.stderr,"Close on bad PIECE: exception",str(e)
                    print_exc()
                connection.close()
                return
            
        elif t == HASHPIECE:
            # Merkle: Handle pieces with hashes, old Tribler<= 4.5.2 style
            self.got_hashpiece(connection,message)
            
        elif t == G2G_PIECE_XFER: 
            # EXTEND_MSG_G2G_V1 only, V2 is proper EXTEND msg 
            if len(message) <= 12:
                if DEBUG:
                    print >>sys.stderr,"Close on bad G2G_PIECE_XFER: msg len"
                connection.close()
                return
            if not c.use_g2g:
                if DEBUG:
                    print >>sys.stderr,"Close on receiving G2G_PIECE_XFER over non-g2g connection"
                connection.close()
                return

            index = toint(message[1:5])
            begin = toint(message[5:9])
            length = toint(message[9:13])
            c.got_g2g_piece_xfer_v1(index,begin,length)

        else:
            connection.close()

        if DEBUG_MESSAGE_HANDLING:
            et = time.time()
            diff = et - st
            if diff > 0.1:
                print >>sys.stderr,"connecter: $$$$$$$$$$$$",getMessageName(t),"took",diff


    def got_extend_message(self,connection,c,message,ut_pex_enabled):
        # connection: Encrypter.Connection; c: Connecter.Connection
        if DEBUG:
            print >>sys.stderr,"connecter: Got EXTEND message, len",len(message)
            print >>sys.stderr,"connecter: his handshake",c.extend_hs_dict,c.get_ip()
            
        try:
            if len(message) < 4:
                if DEBUG:
                    print >>sys.stderr,"Close on bad EXTEND: msg len"
                connection.close()
                return
            ext_id = message[1]
            if DEBUG:
                print >>sys.stderr,"connecter: Got EXTEND message, id",ord(ext_id)
            if ext_id == EXTEND_MSG_HANDSHAKE_ID: 
                # Message is Handshake
                d = bdecode(message[2:])
                if type(d) == DictType:
                    c.got_extend_handshake(d)
                else:
                    if DEBUG:
                        print >>sys.stderr,"Close on bad EXTEND: payload of handshake is not a bencoded dict"
                    connection.close()
                    return
            else:
                # Message is regular message e.g ut_pex
                ext_msg_name = self.our_extend_msg_id_to_name(ext_id)
                if ext_msg_name is None:
                    if DEBUG:
                        print >>sys.stderr,"Close on bad EXTEND: peer sent ID we didn't define in handshake"
                    connection.close()
                    return
                elif ext_msg_name == EXTEND_MSG_OVERLAYSWARM:
                    if DEBUG:
                        print >>sys.stderr,"Not closing EXTEND+CHALLENGE: peer didn't read our spec right, be liberal"
                elif ext_msg_name == EXTEND_MSG_UTORRENT_PEX and ut_pex_enabled:
                    d = bdecode(message[2:])
                    if type(d) == DictType:
                        c.got_ut_pex(d)
                    else:
                        if DEBUG:
                            print >>sys.stderr,"Close on bad EXTEND: payload of ut_pex is not a bencoded dict"
                        connection.close()
                        return
                elif ext_msg_name == EXTEND_MSG_G2G_V2 and self.use_g2g:
                    ppdict = bdecode(message[2:])
                    if type(ppdict) != DictType:
                        if DEBUG:
                            print >>sys.stderr,"Close on bad EXTEND+G2G: payload not dict"
                        connection.close()
                        return
                    for k,v in ppdict.iteritems():
                        if type(k) != StringType or type(v) != StringType:
                            if DEBUG:
                                print >>sys.stderr,"Close on bad EXTEND+G2G: key,value not of type int,char"
                            connection.close()
                            return
                        try:
                            int(k)
                        except:
                            if DEBUG:
                                print >>sys.stderr,"Close on bad EXTEND+G2G: key not int"
                            connection.close()
                            return
                        if ord(v) > 100:
                            if DEBUG:
                                print >>sys.stderr,"Close on bad EXTEND+G2G: value too big",ppdict,v,ord(v)
                            connection.close()
                            return
                            
                    c.got_g2g_piece_xfer_v2(ppdict)
                    
                elif ext_msg_name == EXTEND_MSG_HASHPIECE and self.merkle_torrent:
                    # Merkle: Handle pieces with hashes, Merkle BEP
                    oldmsg = message[1:]
                    self.got_hashpiece(connection,oldmsg)
                    
                elif ext_msg_name == EXTEND_MSG_CS:
                    cs_list = bdecode(message[2:])
                    c.got_cs_message(cs_list)
                    
                else:
                    if DEBUG:
                        print >>sys.stderr,"Close on bad EXTEND: peer sent ID that maps to name we don't support",ext_msg_name,`ext_id`,ord(ext_id)
                    connection.close()
                    return
            return
        except Exception,e:
            if not DEBUG:
                print >>sys.stderr,"Close on bad EXTEND: exception:",str(e),`message[2:]`
                print_exc()
            connection.close()
            return

    def _cs_completed(self, connection):
        """
        When completed, this is a callback function to reset the connection
        """
        try:
            # Can't send bitfield here, must loop and send a bunch of HAVEs
            # Get the bitfield from the uploader
            have_list = connection.upload.storage.get_have_list()
            bitfield = Bitfield(self.numpieces, have_list)
            i = 0
            for b in bitfield.toboollist():
                if b:
                    connection.send_have(i)
                i += 1
            #connection.upload.send_bitfield(connection)
            connection.got_anyUpohing = False
            self.choker.start_connection(connection)
        except Exception,e:
            print >> sys.stderr,"Error restarting after CS handshake:",e
        
    def cs_handshake_completed(self):
        if DEBUG_CS:
            print >>sys.stderr,"connecter: Closed swarm handshake completed!"
        if self.cs_post_func:
            self.cs_post_func()
        elif DEBUG_CS:
            print >>sys.stderr,"connecter: CS: Woops, don't have post function"


def olthread_bartercast_conn_lost(ip,port,down_kb,up_kb):
    """ Called by OverlayThread to store information about the peer to
    whom the connection was just closed in the (slow) databases. """
    
    from Tribler.Core.CacheDB.CacheDBHandler import PeerDBHandler, BarterCastDBHandler
    
    peerdb = PeerDBHandler.getInstance()
    bartercastdb = BarterCastDBHandler.getInstance()
    
    if bartercastdb:
    
        permid = peerdb.getPermIDByIP(ip)
        my_permid = bartercastdb.my_permid
    
        if DEBUG:
            print >> sys.stderr, "bartercast: (Connecter): Up %d down %d peer %s:%s (PermID = %s)" % (up_kb, down_kb, ip, port, `permid`)
    
        # Save exchanged KBs in BarterCastDB
        changed = False
        if permid is not None:
            #name = bartercastdb.getName(permid)
            
            if down_kb > 0:
                new_value = bartercastdb.incrementItem((my_permid, permid), 'downloaded', down_kb, commit=False)
                changed = True
     
            if up_kb > 0:
                new_value = bartercastdb.incrementItem((my_permid, permid), 'uploaded', up_kb, commit=False)
                changed = True
     
        # For the record: save KBs exchanged with non-tribler peers
        else:
            if down_kb > 0:
                new_value = bartercastdb.incrementItem((my_permid, 'non-tribler'), 'downloaded', down_kb, commit=False)
                changed = True
     
            if up_kb > 0:
                new_value = bartercastdb.incrementItem((my_permid, 'non-tribler'), 'uploaded', up_kb, commit=False)
                changed = True
                
        if changed:
            bartercastdb.commit()

    else:
        if DEBUG:
            print >> sys.stderr, "BARTERCAST: No bartercastdb instance"
            

            
