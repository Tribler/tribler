# Written by Jie Yang
# see LICENSE.txt for license information
import sys
from threading import Event,currentThread
from sha import sha
from time import time
from struct import pack
from traceback import print_exc

from BitTornado.__init__ import createPeerID
from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *

from Tribler.__init__ import GLOBAL
from Tribler.utilities import show_permid2
from permid import ChallengeResponse
from OverlayEncrypter import OverlayEncoder
from OverlayConnecter import OverlayConnecter

protocol_name = 'BitTorrent protocol'    #TODO: 'BitTorrent+ protocol'
overlay_infohash = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

from __init__ import CurrentVersion, LowestVersion, SupportedVersions

DEBUG = False

def show(s):
    text = []
    for i in xrange(len(s)): 
        text.append(ord(s[i]))
    return text

def tobinary(i):
    return (chr(i >> 24) + chr((i >> 16) & 0xFF) + 
        chr((i >> 8) & 0xFF) + chr(i & 0xFF))
        
def toint(s):
    return long(b2a_hex(s), 16)        
        
def wrap_message(message_id, payload=None):
    if payload is not None:
        ben_payload = bencode(payload)
        message = tobinary(1+len(ben_payload)) + message_id + ben_payload
    else:
        message = tobinary(1) + message_id
    return message
        

class OverlaySwarm:
    # Code to make this a singleton
    __single = None
    infohash = overlay_infohash

    def __init__(self):
        if OverlaySwarm.__single:
            raise RuntimeError, "OverlaySwarm is singleton"
        OverlaySwarm.__single = self 
        self.myid = createPeerID()
        self.myid = self.myid[:16] + pack('H', LowestVersion) + pack('H', CurrentVersion)
        self.protocol = protocol_name
        self.crs = {}
        self.registered = False
                    
    def getInstance(*args, **kw):
        if OverlaySwarm.__single is None:
            OverlaySwarm(*args, **kw)
        return OverlaySwarm.__single
    getInstance = staticmethod(getInstance)

    def register(self, listen_port, secure_overlay, multihandler, config, errorfunc):
        # Register overlay_infohash as known swarm with MultiHandler
        
        if self.registered:
            return
        
        self.myid = self.myid[:14] + pack('H', listen_port) + self.myid[16:]
        self.secure_overlay = secure_overlay
        self.config = config
        self.doneflag = Event()
        self.rawserver = multihandler.newRawServer(self.infohash, 
                                              self.doneflag,
                                              self.protocol)
        self.errorfunc = errorfunc
        
        # Create Connecter and Encoder for the swarm. TODO: ratelimiter
        self.connecter = OverlayConnecter(self, self.config)
        self.encoder = OverlayEncoder(self, self.connecter, self.rawserver, 
            self.myid, self.config['max_message_length'], self.rawserver.add_task, 
            self.config['keepalive_interval'], self.infohash, 
            lambda x: None, self.config)
        self.registered = True

    def isRegistered(self):
        return self.registered

    def start_listening(self):
        self.rawserver.start_listening(self.encoder)
            
    def connectPeer(self, dns):
        """ Connect to Overlay Socket given peer's ip and port """
        
        if DEBUG:
            print >> sys.stderr,"overlay: Start overlay swarm connection to", dns
        self.encoder.start_connection(dns, 0)
            
    def sendMessage(self, connection, message):
        if DEBUG:
            print >> sys.stderr,"overlay: send message", getMessageName(message[0]), "to", show_permid2(connection.permid)
        connection.send_message(message)

    def connectionMade(self, connection):
        """ phase 1: Connecter.Connection is created but permid has not been verified """

        if DEBUG:
            print >> sys.stderr,"overlay: Bare connection",connection.get_myip(),connection.get_myport(),"to",connection.get_ip(),connection.get_port(),"reported by thread",currentThread().getName()
        
        #def c(conn = connection):
        #""" Start permid exchange and challenge/response validation """
        if not connection or self.crs.has_key(connection):
            return    # don't start c/r if connection is invalid or permid was exchanged
        cr = ChallengeResponse(self.myid, self, self.errorfunc)
        self.crs[connection] = cr
        cr.start_cr(connection)
        #self.rawserver.add_task(c, 0)
            
    def permidSocketMade(self, connection):    # Connecter.Connection. 
        """ phase 2: notify that the connection has been made """
        
        if self.crs.has_key(connection):
            self.crs.pop(connection)
        ## Arno: I don't see the need for letting the rawserver do it.
        ## gotMessage isn't scheduled on rawserver.
        #def notify(connection=connection):
        self.secure_overlay.connectionMade(connection)
        #self.rawserver.add_task(notify, 0)
                
    def connectionLost(self,connection):
        if DEBUG:
            print >> sys.stderr,"overlay: connectionLost: connection is",connection.get_ip(),connection.get_port()
        if connection.permid is None:
            # No permid, so it was never reported to the SecureOverlay
            return
        #def notify(connection=connection):
        self.secure_overlay.connectionLost(connection)
        #self.rawserver.add_task(notify, 0)

    def got_message(self, conn, message):    # Connecter.Connection
        """ Handle message for overlay swarm and return if the message is valid """

        if DEBUG:
            print >> sys.stderr, "overlay: Got",getMessageName(message[0]),"len",len(message)
        
        if not conn:
            return False
        t = message[0]
        
        if t in PermIDMessages:
            try:
                if not self.crs.has_key(conn):    # incoming permid exchange
                    self.crs[conn] = ChallengeResponse(self.myid, self, self.errorfunc)
                if self.crs[conn].got_message(conn, message) == False:
                    if conn and self.crs.has_key(conn):
                        self.crs.pop(conn)
                        conn.close()
            except:
                print_exc()
        else:
            if conn.permid:    # Do not go ahead without permid
                self.secure_overlay.gotMessage(conn.permid, message)
            else:
                print >> sys.stderr, "overlay: Got a message but not found the permid"
