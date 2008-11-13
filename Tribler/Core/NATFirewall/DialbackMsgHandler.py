# Written by Arno Bakker
# see LICENSE.txt for license information
#
# The dialback-message extension serves to (1)~see if we're externally reachable
# and (2)~to tell us what our external IP adress is. When an overlay connection
# is made when we're in dialback mode, we will send a DIALBACK_REQUEST message
# over the overlay connection. The peer is then support to initiate a new
# BT connection with infohash 0x00 0x00 ... 0x01 and send a DIALBACK_REPLY over
# that connection. Those connections are referred to as ReturnConnections
#
# TODO: security problem: if malicious peer connects 7 times to us and tells
# 7 times the same bad external iP, we believe him. Sol: only use locally 
# initiated conns + IP address check (BC2 message could be used to attack
# still)
#
# TODO: Arno,2007-09-18: Bittorrent mainline tracker e.g. 
# http://tracker.publish.bittorrent.com:6969/announce
# now also returns your IP address in the reply, i.e. there is a
# {'external ip': '\x82%\xc1@'}
# in the dict. We should use this info.
#

import sys
from time import time
from random import shuffle
from traceback import print_exc,print_stack
from threading import currentThread

from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.BitTornado.bencode import bencode,bdecode

from Tribler.Core.NATFirewall.ReturnConnHandler import ReturnConnHandler
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_THIRD
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.simpledefs import *

DEBUG = False

#
# Constants
# 

REPLY_WAIT = 60 # seconds
REPLY_VALIDITY = 2*24*3600.0    # seconds

# Normally, one would allow just one majority to possibly exists. However,
# as current Buddycast has a lot of stale peer addresses, let's make
# PEERS_TO_ASK not 5 but 7.
#
PEERS_TO_AGREE = 4   # peers have to say X is my IP before I believe them
YOURIP_PEERS_TO_AGREE = 16 # peers have to say X is my IP via 'yourip' in EXTEND hs before I believe them
PEERS_TO_ASK   = 7   # maximum number of outstanding requests 
MAX_TRIES      = 35  # 5 times 7 peers

class DialbackMsgHandler:
    
    __single = None
    
    def __init__(self):
        if DialbackMsgHandler.__single:
            raise RuntimeError, "DialbackMsgHandler is singleton"
        DialbackMsgHandler.__single = self

        self.peers_asked = {}
        self.myips = []
        self.consensusip = None # IP address according to peers
        self.fromsuperpeer = False
        self.dbreach = False    # Did I get any DIALBACK_REPLY?
        self.btenginereach = False # Did BT engine get incoming connections?
        self.ntries = 0        
        self.active = False     # Need defaults for test code
        self.rawserver = None
        self.launchmany = None
        self.peer_db = None
        self.superpeer_db = None
        self.trust_superpeers = None
        self.old_ext_ip = None
        self.myips_according_to_yourip = []
        self.returnconnhand = ReturnConnHandler.getInstance()
        

    def getInstance(*args, **kw):
        if DialbackMsgHandler.__single is None:
            DialbackMsgHandler(*args, **kw)
        return DialbackMsgHandler.__single
    getInstance = staticmethod(getInstance)
        
    def register(self,overlay_bridge,launchmany,rawserver,config):
        """ Called by MainThread """
        self.overlay_bridge = overlay_bridge
        self.rawserver = rawserver
        self.launchmany = launchmany
        self.peer_db = launchmany.peer_db 
        self.superpeer_db = launchmany.superpeer_db 
        self.active = config['dialback_active'],
        self.trust_superpeers = config['dialback_trust_superpeers']
        self.returnconnhand.register(self.rawserver,launchmany.multihandler,launchmany.listen_port,config['overlay_max_message_length'])
        self.returnconnhand.register_conns_callback(self.network_handleReturnConnConnection)
        self.returnconnhand.register_recv_callback(self.network_handleReturnConnMessage)
        self.returnconnhand.start_listening()

        self.old_ext_ip = launchmany.get_ext_ip()


    def register_yourip(self,launchmany):
        """ Called by MainThread """
        self.launchmany = launchmany


    def olthread_handleSecOverlayConnection(self,exc,permid,selversion,locally_initiated):
        """
        Called from OverlayApps to signal there is an overlay-connection,
        see if we should ask it to dialback
        """
        # Called by overlay thread
        if DEBUG:
            print >> sys.stderr,"dialback: handleConnection",exc,"v",selversion,"local",locally_initiated
        if selversion < OLPROTO_VER_THIRD:
            return True
        
        if exc is not None:
            try:
                del self.peers_asked[permid]
            except:
                if DEBUG:
                    print >> sys.stderr,"dialback: handleConnection: Got error on connection that we didn't ask for dialback"
                pass
            return
        
        if self.consensusip is None:
            self.ntries += 1
            if self.ntries >= MAX_TRIES:
                if DEBUG:
                    print >> sys.stderr,"dialback: tried too many times, giving up"
                return True
            
            if self.dbreach or self.btenginereach:
                self.launchmany.set_activity(NTFY_ACT_GET_EXT_IP_FROM_PEERS)
            else:
                self.launchmany.set_activity(NTFY_ACT_REACHABLE)

            # Also do this when the connection is not locally initiated.
            # That tells us that we're connectable, but it doesn't tell us
            # our external IP address.
            self.olthread_attempt_request_dialback(permid)
        return True
            
    def olthread_attempt_request_dialback(self,permid):
        # Called by overlay thread
        if DEBUG:
            print >> sys.stderr,"dialback: attempt dialback request",show_permid_short(permid)
                    
        dns = self.olthread_get_dns_from_peerdb(permid)
        ipinuse = False

        # 1. Remove peers we asked but didn't succeed in connecting back 
        threshold = time()-REPLY_WAIT
        newdict = {}
        for permid2,peerrec in self.peers_asked.iteritems():
            if peerrec['reqtime'] >= threshold:
                newdict[permid2] = peerrec
            if peerrec['dns'][0] == dns[0]:
                ipinuse = True
        self.peers_asked = newdict

        # 2. Already asked?
        if permid in self.peers_asked or ipinuse or len(self.peers_asked) >= PEERS_TO_ASK:
            # ipinuse protects a little against attacker that want us to believe
            # we have a certain IP address.
            if DEBUG:
                pipa = permid in self.peers_asked
                lpa = len(self.peers_asked)
                print >> sys.stderr,"dialback: No request made to",show_permid_short(permid),"already asked",pipa,"IP in use",ipinuse,"nasked",lpa

            return
        dns = self.olthread_get_dns_from_peerdb(permid)
        
        # 3. Ask him to dialback
        peerrec = {'dns':dns,'reqtime':time()}
        self.peers_asked[permid] = peerrec
        self.overlay_bridge.connect(permid,self.olthread_request_connect_callback)
    
    def olthread_request_connect_callback(self,exc,dns,permid,selversion):
        # Called by overlay thread
        if exc is None:
            if selversion >= OLPROTO_VER_THIRD:
                self.overlay_bridge.send(permid, DIALBACK_REQUEST+'',self.olthread_request_send_callback)
            elif DEBUG:
                print >> sys.stderr,"dialback: DIALBACK_REQUEST: peer speaks old protocol, weird",show_permid_short(permid)
        elif DEBUG:
            print >> sys.stderr,"dialback: DIALBACK_REQUEST: error connecting to",show_permid_short(permid),exc


    def olthread_request_send_callback(self,exc,permid):
        # Called by overlay thread
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"dialback: DIALBACK_REQUEST error sending to",show_permid_short(permid),exc
            pass

    def olthread_handleSecOverlayMessage(self,permid,selversion,message):
        """
        Handle incoming DIALBACK_REQUEST messages
        """
        # Called by overlay thread
        t = message[0]
        
        if t == DIALBACK_REQUEST:
            if DEBUG:
                print >> sys.stderr,"dialback: Got DIALBACK_REQUEST",len(message),show_permid_short(permid)
            return self.olthread_process_dialback_request(permid, message, selversion)
        else:
            if DEBUG:
                print >> sys.stderr,"dialback: UNKNOWN OVERLAY MESSAGE", ord(t)
            return False


    def olthread_process_dialback_request(self,permid,message,selversion):
        # Called by overlay thread
        # 1. Check
        if len(message) != 1:
            if DEBUG:
                print >> sys.stderr,"dialback: DIALBACK_REQUEST: message too big"
            return False

        # 2. Retrieve peer's IP address
        dns = self.olthread_get_dns_from_peerdb(permid)

        # 3. Send back reply
        # returnconnhand uses the network thread to do stuff, so the callback
        # will be made by the network thread
        self.returnconnhand.connect_dns(dns,self.network_returnconn_reply_connect_callback)

        # 4. Message processed OK, don't know about sending of reply though
        return True


    def network_returnconn_reply_connect_callback(self,exc,dns):
        # Called by network thread
        
        if not currentThread().getName().startswith("NetworkThread"):
            print >>sys.stderr,"dialback: network_returnconn_reply_connect_callback: called by",currentThread().getName()," not NetworkThread"
            print_stack()
        
        if exc is None:
            hisip = dns[0]
            try:
                reply = bencode(hisip)
                if DEBUG:
                    print >> sys.stderr,"dialback: DIALBACK_REPLY: sending to",dns
                self.returnconnhand.send(dns, DIALBACK_REPLY+reply, self.network_returnconn_reply_send_callback)
            except:
                print_exc()
                return False
        elif DEBUG:
            print >> sys.stderr,"dialback: DIALBACK_REPLY: error connecting to",dns,exc

    def network_returnconn_reply_send_callback(self,exc,dns):
        # Called by network thread
        if DEBUG:
            print >> sys.stderr,"dialback: DIALBACK_REPLY: send callback:",dns,exc

        
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"dialback: DIALBACK_REPLY: error sending to",dns,exc
            pass

    #
    # Receipt of connection that would carry DIALBACK_REPLY 
    #
    def network_handleReturnConnConnection(self,exc,dns,locally_initiated):
        # Called by network thread
        if DEBUG:
            print >> sys.stderr,"dialback: DIALBACK_REPLY: Got connection from",dns,exc
        pass

    def network_handleReturnConnMessage(self,dns,message):
        # Called by network thread
        t = message[0]
        
        if t == DIALBACK_REPLY:
            if DEBUG:
                print >> sys.stderr,"dialback: Got DIALBACK_REPLY",len(message),dns

            # Hand over processing to overlay thread
            olthread_process_dialback_reply_lambda = lambda:self.olthread_process_dialback_reply(dns, message)
            self.overlay_bridge.add_task(olthread_process_dialback_reply_lambda,0)
        
            # We're done and no longer need the return connection, so
            # call close explicitly
            self.returnconnhand.close(dns)
            return True
        else:
            if DEBUG:
                print >> sys.stderr,"dialback: UNKNOWN RETURNCONN MESSAGE", ord(t)
            return False


    def olthread_process_dialback_reply(self,dns,message):
        # Called by overlay thread
        
        # 1. Yes, we're reachable, now just matter of determining ext IP
        self.dbreach = True
        
        # 2. Authentication: did I ask this peer?
        permid = self.olthread_permid_of_asked_peer(dns)
        if permid is None:
            if DEBUG:
                print >> sys.stderr,"dialback: DIALBACK_REPLY: Got reply from peer I didn't ask",dns
            return False

        del self.peers_asked[permid]

        # 3. See what he sent us
        try:
            myip = bdecode(message[1:])
        except:
            print_exc()
            if DEBUG:
                print >> sys.stderr,"dialback: DIALBACK_REPLY: error becoding"
            return False
        if not isValidIP(myip):
            if DEBUG:
                print >> sys.stderr,"dialback: DIALBACK_REPLY: invalid IP"
            return False


        # 4. See if superpeer, then we're done, trusted source 
        if self.trust_superpeers:
            superpeers = self.superpeer_db.getSuperPeers()
            if permid in superpeers:
                if DEBUG:
                    print >> sys.stderr,"dialback: DIALBACK_REPLY: superpeer said my IP address is",myip,"setting it to that"
                self.consensusip = myip
                self.fromsuperpeer = True
        else:
            # 5, 6. 7, 8. Record this peers opinion and see if we get a 
            # majority vote.
            #
            self.myips,consensusip = tally_opinion(myip,self.myips,PEERS_TO_AGREE)
            if self.consensusip is None:
                self.consensusip = consensusip 

        # 8. Change IP address if different
        if self.consensusip is not None:
            
            self.launchmany.dialback_got_ext_ip_callback(self.consensusip)
            if DEBUG:
                print >> sys.stderr,"dialback: DIALBACK_REPLY: I think my IP address is",self.old_ext_ip,"others say",self.consensusip,", setting it to latter"

        # 9. Notify GUI that we are connectable
        self.launchmany.dialback_reachable_callback()

        return True
    

    #
    # Information from other modules
    #
    def network_btengine_reachable_callback(self):
        """ Called by network thread """
        if self.launchmany is not None:
            self.launchmany.dialback_reachable_callback()
            
        # network thread updating our state. Ignoring concurrency, as this is a
        # one time op.
        self.btenginereach = True

    def isConnectable(self):
        """ Called by overlay (BuddyCast) and network (Rerequester) thread """

        # network thread updating our state. Ignoring concurrency, as these
        # variables go from False to True once and stay there, or remain False
        return self.dbreach or self.btenginereach


    def network_btengine_extend_yourip(self,myip):
        """ Called by Connecter when we receive an EXTEND handshake that 
        contains an yourip line.
        
        TODO: weigh opinion based on whether we locally initiated the connection
        from a trusted tracker response, or that the address came from ut_pex.
        """
        self.myips_according_to_yourip, yourip_consensusip = tally_opinion(myip,self.myips_according_to_yourip,YOURIP_PEERS_TO_AGREE)
        if DEBUG:
            print >> sys.stderr,"dialback: yourip: someone said my IP is",myip
        if yourip_consensusip is not None:
            self.launchmany.yourip_got_ext_ip_callback(yourip_consensusip)
            if DEBUG:
                print >> sys.stderr,"dialback: yourip: I think my IP address is",self.old_ext_ip,"others via EXTEND hs say",yourip_consensusip,"recording latter as option"

    #
    # Internal methods
    #
    def olthread_get_dns_from_peerdb(self,permid):
        dns = None
        peer = self.peer_db.getPeer(permid)
        #print >>sys.stderr,"dialback: get_dns_from_peerdb: Got peer",peer
        if peer:
            ip = self.to_real_ip(peer['ip'])
            dns = (ip, int(peer['port']))
        return dns

    def to_real_ip(self,hostname_or_ip):
        """ If it's a hostname convert it to IP address first """
        ip = None
        try:
            """ Speed up: don't go to DNS resolver unnecessarily """
            socket.inet_aton(hostname_or_ip)
            ip = hostname_or_ip
        except:
            try:
                ip = socket.gethostbyname(hostname_or_ip)
            except:
                print_exc()
        return ip

        
    def olthread_permid_of_asked_peer(self,dns):
        for permid,peerrec in self.peers_asked.iteritems():
            if peerrec['dns'] == dns:
                # Yes, we asked this peer
                return permid
        return None


def tally_opinion(myip,oplist,requiredquorum):

    consensusip = None

    # 5. Ordinary peer, just add his opinion
    oplist.append([myip,time()])
    if DEBUG:
        print >> sys.stderr,"dialback: DIALBACK_REPLY: peer said I have IP address",myip

    # 6. Remove stale opinions
    newlist = []
    threshold = time()-REPLY_VALIDITY
    for pair in oplist:
        if pair[1] >= threshold:
            newlist.append(pair)
    oplist = newlist
    
    # 7. See if we have X peers that agree
    opinions = {}
    for pair in oplist:
        ip = pair[0]
        if not (ip in opinions):
            opinions[ip] = 1
        else:
            opinions[ip] += 1

    for o in opinions:
        if opinions[o] >= requiredquorum:
            # We have a quorum
            if consensusip is None:
                consensusip = o
                if DEBUG:
                    print >> sys.stderr,"dialback: DIALBACK_REPLY: Got consensus on my IP address being",consensusip
            else:
                # Hmmmm... more than one consensus
                pass

    return oplist,consensusip
