from threading import Event,currentThread

from sha import sha
from time import time
from struct import pack

from BitTornado.__init__ import createPeerID
from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import *
from permid import ChallengeResponse
from Tribler.BuddyCast.buddycast import BuddyCast
from MetadataHandler import MetadataHandler
from Tribler.DownloadHelp.helper import Helper
from Tribler.globalvars import GLOBAL
#from BT1.Connecter import Connecter
#from BT1.Encrypter import Encoder

protocol_name = 'BitTorrent protocol'    #TODO: 'BitTorrent+ protocol'
overlay_infohash = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

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
        self.alive_interval = 60    # It should be automatically closed if it isn't active for a short period. 
        self.peers = {}    # key: ip; value:{port:Connecter.Connection}. The connection is normal connection
        self.connections = {}  # key: permid, value: Connecter.Connection. Only overlay connections are list here
        self.crs = {}      # key: Connecter.Connection, value: ChallengeResponse. Only overlay connection can be the key
        self.close_conn = {}   # key: enc_conn; value: time_stamp. Used to close connections
        self.pending_prefxchange = []
        self.requested_infohash = {}
        self.tasks_queue = {}    # key:Conn.Conn, value: task. Pended tasks for each overlay swarm connection
        self.tasks_queue2 = {}   # key:(ip, port), value: (task, arg). Once the overlay swarm connection 
                                 # is established, the task here will be appended to the above task_queue
        self.valid_tasks = [
            'PREFERENCE_EXCHANGE',
            'GET_METADATA',
            'CHALLENGE',
            'DOWNLOAD_HELP',
            ]
        self.registered = False
                    
    def getInstance(*args, **kw):
        if OverlaySwarm.__single is None:
            OverlaySwarm(*args, **kw)
        return OverlaySwarm.__single
    getInstance = staticmethod(getInstance)

    def register(self, launchmany, multihandler, config, listen_port, errorfunc):
        # Register overlay_infohash as known swarm with MultiHandler
        
        if self.registered:
            return
        
        self.launchmany = launchmany
        self.multihandler = multihandler
        self.config = config
        self.doneflag = Event()
        self.rawserver = multihandler.newRawServer(self.infohash, 
                                              self.doneflag,
                                              self.protocol)
        self.listen_port = listen_port
        self.errorfunc = errorfunc
        
        # Create Connecter and Encoder for the swarm. TODO: ratelimiter
#        self.connecter = Connecter(None, None, None, 
#                            None, None, self.config, 
#                            None, False,
#                            self.rawserver.add_task, self)
#        self.encoder = Encoder(self.connecter, self.rawserver, 
#            self.myid, self.config['max_message_length'], self.rawserver.add_task, 
#            self.config['keepalive_interval'], self.infohash, 
#            lambda x: None, self.config, self)
        self.registered = True
            
    def start(self):
        return
        if not self.registered:
            return
        self.rawserver.start_listening(self.encoder)
       
    def connection_made(self, conn):
        """ Initiate overlay swarm connection """
        
        ip = conn.get_ip(True)
        port = conn.get_port(True)
        self.connect_peer(ip, port)
        if hasattr(self, 'buddycast') and not self.buddycast.my_ip:
            self.buddycast.set_myip(conn.get_myip(True))
            
    def connect_peer(self, ip, port):
            """ Connect to overlay swarm given peer's ip and port """
        
        #if not self.peers.has_key(ip) or not self.peers[ip][port].is_overlayswarm():
            if DEBUG:
                print "Start overlay swarm connection to", ip + ':' + str(port)
            # The new Encrypter.Connection will be registered at OverlaySwarm.connections
            dns = (ip, port)
            self.encoder.start_connection(dns, 0)
            
    def add_os_task(self, conn, task):
        print "add_os_task:",currentThread()
        if isinstance(task, str):
            task = (task, None)
        if task[0] not in self.valid_tasks:
            print "TASK 0 NOT VALID",task[0]
            return
        if conn not in self.tasks_queue:
            self.tasks_queue[conn] = []
        self.tasks_queue[conn].append(task)
        print "TASK ADDED!!",conn,task
        
    def add_os_task2(self, ip, port, task):
        print "add_os_task2:",currentThread()
        if DEBUG:
            print "Add overlay swarm task ", ip, " ", port, " ", task
        if isinstance(task, str):
            task = (task, None)
        if task[0] not in self.valid_tasks:
            return
        if (ip, port) not in self.tasks_queue2:
            self.tasks_queue2[(ip, port)] = []
        self.tasks_queue2[(ip, port)].append(task)
        if DEBUG:
            print "Added overlay swarm task ", ip, " ", port, " ", task, " - \n"

    def move_os_tasks(self, ip, port, conn):    # move tasks from task_queue2 to task_queue
        print "move_os_task:",currentThread()
        try:
            if DEBUG:
                print "Moving os tasks ", (ip, port), " ", self.tasks_queue2, " - \n"
            while True:
                print "HALLO"
                task = self.tasks_queue2[(ip, port)].pop(0)
                print "DAG"
                self.add_os_task(conn, task)
                if DEBUG:
                    print "Moving os task: ", ip, " ", port, " ", task
        except Exception,e:
            print "EXCEPTION IN MOVE",e
            pass
        
    def check_os_task(self, conn):    # fetch one task to execute
        print "check_os_task:",currentThread()
        print "Fetching task to execute for",conn
        while True:
            try:
                task = self.tasks_queue[conn].pop(0)
            except Exception,e:
                print "Exception while fetching task!",e 
                return
            if task[0] == 'CHALLENGE':
                self.start_cr(conn)
            elif task[0] == 'PREFERENCE_EXCHANGE':
                self._start_prefxchg(conn)
            elif task[0] == 'DOWNLOAD_HELP':
                if DEBUG:
                    print "Executing delayed task: ", task[0]
                self._request_download_help(conn, task[1])
            elif task[0] == 'GET_METADATA':
                self.metadata_handler.send_metadata_request(conn, task[1])
            else:
                return
                
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

    def start_prefxchg(self, ip, port):
        try:
            normal_conn = self.peers[ip][port]
            overlay_conn = self.connections[normal_conn.permid]
            self._start_prefxchg(overlay_conn)
        except:
            self.connect_peer(ip, port)
            self.add_os_task2(ip, port, 'PREFERENCE_EXCHANGE')
            
    def _start_prefxchg(self, conn):
        if not hasattr(self, "buddycast") or not conn.permid:
            print "start prefxchg failed", self.buddycast, conn.permid
            return
        self.buddycast.add_new_buddy(conn)
        if conn.is_locally_initiated():
            self.buddycast.exchange_preference(conn)
    
    def add_peer(self, ip, port, conn):
        """ Register a peer's overlay swarm connection indexed by ip """
        
        self.peers[ip] = {port:conn}    # It is normal swarm connection first but will be replaced by overlay swarm connection
        
    def remove_peer(self, conn):
        ip = conn.get_ip()
        if not self.peers.has_key(ip):
            return
        for port in self.peers[ip].keys():
            if self.peers[ip][port] == conn:
                del self.peers[ip][port]
                self.tasks_queue.pop(conn)
            
    def couple_connections(self, overlay_conn):
        """ Couple normal connection with overlay connection """
        
        ip = overlay_conn.get_ip(True)
        if overlay_conn.is_locally_initiated():
            port = overlay_conn.get_port(True)
        else:
            port = 0
            
        if not self.peers.has_key(ip) or not self.peers[ip]:
            return
            
        if port == 0:   # if not locally initiated, couple overlay_conn with all (normal)connections in self.peers[ip]
            for port in self.peers[ip].keys():    
                 if not self.peers[ip][port].is_overlayswarm():
                    self.peers[ip][port].overlay_connection = overlay_conn    # couple normal connection with its overlay connection
                    self.peers[ip][port].permid = overlay_conn.get_permid()
                    self.peers[ip][port] = overlay_conn    # change to overlay connection
        elif self.peers[ip].has_key(port): 
            if not self.peers[ip][port].is_overlayswarm():
                self.peers[ip][port].overlay_connection = overlay_conn    # couple normal connection with its overlay connection
                self.peers[ip][port].permid = overlay_conn.get_permid()
                self.peers[ip][port] = overlay_conn    # change to overlay connection
            
    def add_connection(self, conn, permid):
        """ Register a peer's overlay swarm connection indexed by permid """

        permid = str(permid)
        self.connections[permid] = conn    # overlay swarm Conneter.Connection
        conn.set_permid(permid)
        self.couple_connections(conn)
        del self.crs[conn]    # not to use any more
        self.post_connection_added(conn)    #TODO: decide what to do next
        if DEBUG:
            print "Add overlay connection"
        
    def post_connection_added(self, conn):
        ip = conn.get_ip(True)
        port = conn.get_port(True)
        print "POSTCONN BEFORE MOVE"
        self.move_os_tasks(ip, port, conn)
        print "POSTCONN AFTER MOVE"        
        self.check_os_task(conn)
        print "POSTCONN AFTER CHECK"
        
    def start_cr(self, conn):
        """ Start permid exchange and challenge/response validation """
        
        # don't start c/r if conn is invalid or permid was exchanged
        if not conn or self.crs.has_key(conn) and self.crs[conn]:
            return
        cr = ChallengeResponse(self.myid,self,self.errorfunc)    # one cr per connection
        self.crs[conn] = cr
        cr.start_cr(conn)
                
    def remove_connection(self, permid):
        if self.connections.has_key(permid):
            del self.connections[permid]
    
    def got_message(self, conn, message):
        """ Handle message for overlay swarm and return if the message is valid """
        if DEBUG:
            #print "GOT message:", len(message), show(message), message
            print "Overlay",
            printMessageID(message[0],message)

        if not conn:
            return False
        t = message[0]
        
        if t in PermIDMessages:
            if not self.crs.has_key(conn) or not self.crs[conn]:    # incoming permid exchange
                cr = ChallengeResponse(self.myid,self,self.errorfunc)
                self.crs[conn] = cr
            return self.crs[conn].got_message(conn, message)
        
        if not conn.permid:    # Do not go ahead without permid
            return False
            
        if t in BuddyCastMessages:
            if not hasattr(self, "buddycast"):
                return False
            return self.buddycast.got_message(conn, message)
        
        if t in MetadataMessages:
            if not hasattr(self, "metadata_handler"):
                return False
            return self.metadata_handler.got_message(conn, message)
        
        if t in HelpMessages:
            if not hasattr(self, "helper"):
                return False
            return self.helper.got_message(conn, message)
        
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
