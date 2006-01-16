from threading import Event,currentThread

from sha import sha
from time import time
from struct import pack

from BitTornado.__init__ import createPeerID
from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *

from Tribler.BuddyCast.buddycast import BuddyCast
from Tribler.toofastbt.bthelper import Helper
from Tribler.__init__ import GLOBAL

from permid import ChallengeResponse
from MetadataHandler import MetadataHandler
from OverlayEncrypter import OverlayEncoder
from OverlayConnecter import OverlayConnecter

protocol_name = 'BitTorrent protocol'    #TODO: 'BitTorrent+ protocol'
overlay_infohash = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

from __init__ import CurrentVersion, LowestVersion, SupportedVersions

DEBUG = True

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
        
if DEBUG:
    class ENC_CONN:    # Encrypter.Connection class for test
        def __init__(self):
            pass
        
        def get_ip(self):
            return "1.2.3.4"
                        
        
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
        self.registered = False
                    
    def getInstance(*args, **kw):
        if OverlaySwarm.__single is None:
            OverlaySwarm(*args, **kw)
        return OverlaySwarm.__single
    getInstance = staticmethod(getInstance)

    def register(self, launchmany, secure_overlay, multihandler, config, listen_port, errorfunc):
        # Register overlay_infohash as known swarm with MultiHandler
        
        if self.registered:
            return
        
        self.launchmany = launchmany
        self.secure_overlay = secure_overlay
        self.config = config
        self.doneflag = Event()
        self.rawserver = multihandler.newRawServer(self.infohash, 
                                              self.doneflag,
                                              self.protocol)
        self.listen_port = listen_port
        self.errorfunc = errorfunc
        
        # Create Connecter and Encoder for the swarm. TODO: ratelimiter
        self.connecter = OverlayConnecter(self.config, None, self.rawserver.add_task)
        self.encoder = OverlayEncoder(self.connecter, self.rawserver, 
            self.myid, self.config['max_message_length'], self.rawserver.add_task, 
            self.config['keepalive_interval'], self.infohash, 
            lambda x: None, self.config)
        self.registered = True
        self.rawserver.start_listening(self.encoder)
            
    def connectPeer(self, dns):
        """ Connect to Overlay Socket given peer's ip and port """
        
        if DEBUG:
            print "Start overlay swarm connection to", dns
            class Conn:
                def __init__(self, dns):
                    self.dns = dns
                    self.permid = 'permid1'
                    self.closed = False
                def close(self):
                    print "connection closed"
                    self.closed = True
                    
            conn = Conn(dns)
            from time import sleep
            print "    waiting connection ..."
            sleep(3)
            self.connectionMade(conn)
        #self.encoder.start_connection(dns, 0)
            
    def sendMessage(self, connection, message):
        if DEBUG:
            print "send message", message, "from", connection
            
    def connectionMade(self, connection):    # Connecter.Connection. 
        """ notify that the connection has been made """
        self.secure_overlay.connectionMade(connection)
                
    def request_download_help(self, ip, port, torrent_hash):
        try:
            normal_conn = self.peers[ip][port]
            overlay_conn = self.connections[normal_conn.permid]
            self._request_download_help(overlay_conn, torrent_hash)
        except:
            self.connect_peer(ip, port)
            self.add_os_task2(ip, port, ('DOWNLOAD_HELP', torrent_hash))
            
    def _request_download_help(self, conn, torrent_hash):
        if not hasattr(self, "helper") or not conn.permid:
            print "start download help failed"
            return
        self.helper.send_dlhelp_request(conn, torrent_hash)

    def got_message(self, permid, message):    # Connecter.Connection
        """ Handle message for overlay swarm and return if the message is valid """
        if DEBUG:
            #print "GOT message:", len(message), show(message), message
            print "Overlay",
            printMessageID(message[0],message)
        self.secure_overlay.gotMessage(permid, message)
        
    def start_buddycast(self):
        self.buddycast = BuddyCast.getInstance()
        self.buddycast.set_rawserver(self.rawserver)
        self.buddycast.set_listen_port(self.listen_port)
        self.buddycast.set_errorfunc(self.errorfunc)
        self.buddycast.startup()
        self.start_metadata_handler()
        
    def start_metadata_handler(self):
        self.metadata_handler = MetadataHandler.getInstance()
        self.metadata_handler.set_rawserver(self.rawserver)
        self.metadata_handler.set_dlhelper(Helper.getInstance())
        self.metadata_handler.startup()
        
    def start_download_helper(self):
        self.helper = Helper.getInstance()
        self.helper.set_rawserver(self.rawserver)
        self.helper.set_metadata_handler(MetadataHandler.getInstance())
# 2fastbt_
        self.helper.set_launchmany(self.launchmany)
# _2fastbt
        self.helper.startup()

        
if DEBUG and __name__ == "__main__":
    overlayswarm = OverlaySwarm.getInstance()
    overlayswarm.listen_port = 4321
    enc_conn = ENC_CONN()
    enc_conn.overlayswarm = overlayswarm
    
    print "Testing REQUEST_LISTENING_PORT, LISTENING_PORT"
    overlayswarm.request_listening_port(enc_conn)
    
    print "\nTesting REQUEST_PREFERENCE, PREFERENCE"
    overlayswarm.request_preference(enc_conn, 5)
    
    print "\nTesting REQUEST_METADATA, METADATA"
    infohash = 'T\xcc\x03+\xd1\x03\xe5\xd20(\xfb{\xa9\x99\xe9\t\x97\xf7\xddE'
    overlayswarm.request_metadata(infohash)
    overlayswarm.do_request_metadata(enc_conn, infohash)
