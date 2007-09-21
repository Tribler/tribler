# Written by Arno Bakker, Bram Cohen, Jie Yang
# see LICENSE.txt for license information
#
# Please apply networking code fixes also to DialbackConnHandler.py

import sys
from struct import pack,unpack
from time import time
from sets import Set
from cStringIO import StringIO
from threading import currentThread
from socket import gethostbyname
from traceback import print_exc,print_stack

from BitTornado.__init__ import createPeerID
from BitTornado.BT1.MessageID import protocol_name,option_pattern,getMessageName
from BitTornado.BT1.convert import tobinary,toint

from Tribler.CacheDB.CacheDBHandler import MyDBHandler
from Tribler.CacheDB.SynDBHandler import SynPeerDBHandler
from Tribler.Overlay.permid import ChallengeResponse
from Tribler.utilities import show_permid_short

DEBUG = False

#
# Public definitions
#
overlay_infohash = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

# Overlay-protocol version numbers in use in the wild
OLPROTO_VER_FIRST  = 1  # Internally used only.
OLPROTO_VER_SECOND = 2  # First public release, >= 3.3.4
OLPROTO_VER_THIRD  = 3  # Second public release, >= 3.6.0, Dialback, BuddyCast2
OLPROTO_VER_FOURTH = 4  # Third public release, >= 3.7.0, BuddyCast3
OLPROTO_VER_FIFTH = 5   # Fourth public release, >= 4.0.0, SOCIAL_OVERLAP
OLPROTO_VER_SIXTH = 6   # Fifth public release, >= 4.1.0, extra BC fields, remote query

# Overlay-swarm protocol version numbers
OLPROTO_VER_CURRENT = OLPROTO_VER_SIXTH
OLPROTO_VER_LOWEST = OLPROTO_VER_SECOND
SupportedVersions = range(OLPROTO_VER_LOWEST, OLPROTO_VER_CURRENT+1)

#
# Private definitions
#

# States for overlay connection
STATE_INITIAL = 0
STATE_HS_FULL_WAIT = 1
STATE_HS_PEERID_WAIT = 2
STATE_AUTH_WAIT = 3
STATE_DATA_WAIT = 4
STATE_CLOSED = 5

# Misc
EXPIRE_THRESHOLD =      300    # seconds::  keep consistent with sockethandler
EXPIRE_CHECK_INTERVAL = 60     # seconds
NO_REMOTE_LISTEN_PORT_KNOWN = -481


class SecureOverlay:
    __single = None

    def __init__(self):
        if SecureOverlay.__single:
            raise RuntimeError, "SecureOverlay is Singleton"
        SecureOverlay.__single = self 
        self.olproto_ver_current = OLPROTO_VER_CURRENT

    #
    # Interface for upper layer
    #
    def getInstance(*args, **kw):
        if SecureOverlay.__single is None:
            SecureOverlay(*args, **kw)
        return SecureOverlay.__single
    getInstance = staticmethod(getInstance)

    def register(self,rawserver,multihandler,mylistenport,max_len,mykeypair):
        self.rawserver = rawserver
        self.sock_hand = self.rawserver.sockethandler
        self.multihandler = multihandler
        self.overlay_rawserver = multihandler.newRawServer(overlay_infohash, 
                                              self.rawserver.doneflag,
                                              protocol_name)
        self.myid = create_my_peer_id(mylistenport)
        self.max_len = max_len
        self.iplport2oc = {}    # (IP,listen port) -> OverlayConnection
        self.usermsghandler = None
        self.userconnhandler = None
        self.peer_db = SynPeerDBHandler()
        self.mykeypair = mykeypair
        self.permid = str(mykeypair.pub().get_der())
        self.myip = MyDBHandler().getMyIP()
        self.myport = mylistenport

    def resetSingleton(self):
        """ For testing purposes """
        SecureOverlay.__single = None 

    def start_listening(self):
        self.overlay_rawserver.start_listening(self)

    def connect_dns(self,dns,callback):
        """ Connects to the indicated endpoint and determines the permid 
            at that endpoint. Non-blocking. 
            
            Pre: "dns" must be an IP address, not a hostname.
            
            Network thread calls "callback(exc,dns,permid,selver)" when the connection
            is established or when an error occurs during connection 
            establishment. In the former case, exc is None, otherwise
            it contains an Exception.

            The established connection will auto close after EXPIRE_THRESHOLD
            seconds of inactivity.
        """
        if DEBUG:
            print >> sys.stderr,"secover: connect_dns",dns
        # To prevent concurrency problems on sockets the calling thread 
        # delegates to the network thread.
        task = Task(self._connect_dns,dns,callback)
        self.rawserver.add_task(task.start, 0)


    def connect(self,permid,callback):
        """ Connects to the indicated permid. Non-blocking.
            
            Network thread calls "callback(exc,dns,permid,selver)" when the connection
            is established or when an error occurs during connection 
            establishment. In the former case, exc is None, otherwise
            it contains an Exception.

            The established connection will auto close after EXPIRE_THRESHOLD
            seconds of inactivity.
        """
        if DEBUG:
            print >> sys.stderr,"secover: connect",show_permid_short(permid)
        # To prevent concurrency problems on sockets the calling thread 
        # delegates to the network thread.
        task = Task(self._connect,permid,callback)
        self.rawserver.add_task(task.start, 0)


    def send(self,permid,msg,callback):
        """ Sends a message to the indicated permid. Non-blocking.
            
            Pre: connection to permid must have been established successfully.

            Network thread calls "callback(exc,permid)" when the message is sent
            or when an error occurs during sending. In the former case, exc 
            is None, otherwise it contains an Exception.
        """
        # To prevent concurrency problems on sockets the calling thread 
        # delegates to the network thread.
        task = Task(self._send,permid,msg,callback)
        self.rawserver.add_task(task.start, 0)



    def close(self,permid):
        """ Closes any connection to indicated permid. Non-blocking.
            
            Pre: connection to permid must have been established successfully.

            Network thread calls "callback(exc,permid,selver)" when the connection
            is closed.
        """
        # To prevent concurrency problems on sockets the calling thread 
        # delegates to the network thread.
        task = Task(self._close,permid)
        self.rawserver.add_task(task.start, 0)


    def register_recv_callback(self,callback):
        """ Register a callback to be called when receiving a message from 
            any permid. Non-blocking.

            Network thread calls "callback(exc,permid,selver,msg)" when a message 
            is received. The callback is not called on errors e.g. remote 
            connection close.
            
            The callback must return True to keep the connection open.
        """
        self.usermsghandler = callback

    def register_conns_callback(self,callback):
        """ Register a callback to be called when receiving a connection from 
            any permid. Non-blocking.

            Network thread calls "callback(exc,permid,selver,locally_initiated)" 
            when a connection is established (locally initiated or remote), or
            when a connection is closed locally or remotely. In the former case, 
            exc is None, otherwise it contains an Exception.

            Note that this means that if a callback is registered via this method,
            both this callback and the callback passed to a connect() method 
            will be called.
        """
        self.userconnhandler = callback


    #
    # Internal methods
    #
    def _connect_dns(self,dns,callback):
        try:
            if DEBUG:
                print >> sys.stderr,"secover: actual connect_dns",dns
            if dns[0] == self.myip and int(dns[1]) == self.myport:
                callback(KeyError('IP and port of the target is the same as myself'),dns,None,0)
            iplport = ip_and_port2str(dns[0],dns[1])
            oc = None
            try:
                oc = self.iplport2oc[iplport]
            except KeyError:
                pass
            if oc is None:
                oc = self.start_connection(dns)
                self.iplport2oc[iplport] = oc
            if not oc.is_auth_done():
                oc.queue_callback(dns,callback)
            else:
                callback(None,dns,oc.get_auth_permid(),oc.get_sel_proto_ver())
        except Exception,exc:
            if DEBUG:
                print_exc()
            callback(exc,dns,None,0)

    def _connect(self,expectedpermid,callback):
        if DEBUG:
            print >> sys.stderr,"secover: actual connect",show_permid_short(expectedpermid)
        if expectedpermid == self.permid:
            callback(KeyError('The target permid is the same as my permid'),None,expectedpermid,0)
        try:
            oc = self.get_oc_by_permid(expectedpermid)
            if oc is None:
                dns = self.get_dns_from_peerdb(expectedpermid)
                if dns is None:
                    callback(KeyError('IP address + port for permid unknown'),dns,expectedpermid,0)
                else:
                    self._connect_dns(dns,lambda exc,dns2,peerpermid,selver:\
                          self._whoishe_callback(exc,dns2,peerpermid,selver,expectedpermid,callback))
            else:
                # We already have a connection to this permid
                self._whoishe_callback(None,(oc.get_ip(),oc.get_auth_listen_port()),expectedpermid,oc.get_sel_proto_ver(),expectedpermid,callback)
        except Exception,exc:
            if DEBUG:
                print_exc()
            callback(exc,None,expectedpermid,0)

    def _whoishe_callback(self,exc,dns,peerpermid,selver,expectedpermid,callback):
        """ Called by network thread after the permid on the other side is known
            or an error occured
        """
        try:
            if exc is None:
                # Connect went OK
                if peerpermid == expectedpermid:
                    callback(None,dns,expectedpermid,selver)
                else:
                    # Someone else answered the phone
                    callback(KeyError('Recorded IP address + port now of other permid'),
                                     dns,expectedpermid,0)
            else:
                callback(exc,dns,expectedpermid,0)
        except Exception,exc:
            if DEBUG:
                print_exc()
            callback(exc,dns,expectedpermid,0)

    def _send(self,permid,message,callback):
        if DEBUG:
            print >> sys.stderr,"secover: actual send",getMessageName(message[0]),\
                        "to",show_permid_short(permid)
        try:
            dns = self.get_dns_from_peerdb(permid)
            if dns is None:
                callback(KeyError('IP address + port for permid unknown'),permid)
            else:
                iplport = ip_and_port2str(dns[0],dns[1])
                oc = None
                try:
                    oc = self.iplport2oc[iplport]
                except KeyError:
                    pass
                if oc is None:
                    callback(KeyError('Not connected to permid'),permid)
                elif oc.is_auth_done():
                    if oc.get_auth_permid() == permid:
                        oc.send_message(message)
                        callback(None,permid)
                    else:
                        callback(KeyError('Recorded IP address + port now of other permid'),permid,0)
                else:
                    callback(KeyError('Connection not yet established'),permid)
        except Exception,exc:
            if DEBUG:
                print_exc()
            callback(exc,permid)


    def _close(self,permid):
        if DEBUG:
            print >> sys.stderr,"secover: actual close",show_permid_short(permid)
        try:
            oc = self.get_oc_by_permid(permid)
            if not oc:
                if DEBUG:
                    print >> sys.stderr,"secover: error - actual close, but no connection to peer in admin"
            else:
                oc.close()
        except Exception,e:
            print_exc()

    #
    # Interface for SocketHandler
    #
    def external_connection_made(self,singsock):
        """ incoming connection (never used) """
        if DEBUG:
            print >> sys.stderr,"secover: external_connection_made",singsock.get_ip(),singsock.get_port()
        oc = OverlayConnection(self,singsock,self.rawserver)
        singsock.set_handler(oc)

    def connection_flushed(self,singsock):
        """ sockethandler flushes connection """
        if DEBUG:
            print >> sys.stderr,"secover: connection_flushed",singsock.get_ip(),singsock.get_port()
        pass

    #
    # Interface for ServerPortHandler
    #
    def externally_handshaked_connection_made(self, singsock, options, msg_remainder):
        """ incoming connection, handshake partially read to identity 
            as an it as overlay connection (used always)
        """
        if DEBUG:
            print >> sys.stderr,"secover: externally_handshaked_connection_made",\
                singsock.get_ip(),singsock.get_port()
        oc = OverlayConnection(self,singsock,self.rawserver,ext_handshake = True, options = options)
        singsock.set_handler(oc)
        if msg_remainder:
            oc.data_came_in(singsock,msg_remainder)
        return True


    #
    # Interface for OverlayConnection
    #
    def got_auth_connection(self,oc):
        """ authentication of peer via identity protocol succesful """
        if DEBUG:
            print >> sys.stderr,"secover: got_auth_connection", \
                show_permid_short(oc.get_auth_permid()),oc.get_ip(),oc.get_auth_listen_port()

        if oc.is_locally_initiated() and oc.get_port() != oc.get_auth_listen_port():
            if DEBUG:
                print >> sys.stderr,"secover: got_auth_connection: closing because auth", \
                    "listen port not as expected",oc.get_port(),oc.get_auth_listen_port()
            self.cleanup_admin_and_callbacks(oc,Exception('closing because auth listen port not as expected'))
            return False

        ret = True
        iplport = ip_and_port2str(oc.get_ip(),oc.get_auth_listen_port())
        known = iplport in self.iplport2oc
        if not known:
            self.iplport2oc[iplport] = oc
        elif known and not oc.is_locally_initiated():
            # Locally initiated connections will already be registered,
            # so if it's not a local connection and we already have one 
            # we have a duplicate, and we close the new one.
            if DEBUG:
                print >> sys.stderr,"secover: got_auth_connection:", \
                    "closing because we already have a connection to",iplport
            self.cleanup_admin_and_callbacks(oc,
                     Exception('closing because we already have a connection to peer'))
            ret = False
            
        if ret:
            self.add_peer_to_db(oc)
            
            if self.userconnhandler is not None:
                try:
                    self.userconnhandler(None,oc.get_auth_permid(),oc.get_sel_proto_ver(),oc.is_locally_initiated())
                except:
                    # Catch all
                    print_exc()
            oc.dequeue_callbacks()
        return ret

    def local_close(self,oc):
        """ our side is closing the connection """
        if DEBUG:
            print >> sys.stderr,"secover: local_close"
        self.update_peer_status(oc)
        self.cleanup_admin_and_callbacks(oc,Exception('local close'))

    def connection_lost(self,oc):
        """ overlay connection telling us to clear admin """
        if DEBUG:
            print >> sys.stderr,"secover: connection_lost"
        self.update_peer_status(oc)
        self.cleanup_admin_and_callbacks(oc,Exception('connection lost'))

    def add_peer_to_db(self,oc):
        """ add a connected peer to database """
        if oc.is_auth_done():
            ip = oc.get_ip()
            port = oc.get_auth_listen_port()
            peer_permid = oc.get_auth_permid()
            oversion = oc.get_cur_proto_ver()
            now = int(time())
            peer_data = {'permid':peer_permid, 'ip':ip, 'port':port, 'oversion':oversion, 'last_seen':now, 'last_connected':now}
            self.peer_db.addPeer(peer_permid, peer_data, update_dns=True)
            self.peer_db.updateTimes(peer_permid, 'connected_times', 1)
            try:
                # Arno: PARANOID SYNC
                self.peer_db.sync()
            except:
                print_exc()
        
    def update_peer_status(self, oc):
        """ update last_seen and last_connected in peer db when close """
        now = int(time())
        if oc.is_auth_done():
            peer_permid = oc.get_auth_permid()
            self.peer_db.updatePeer(peer_permid, 'last_seen', now)
            self.peer_db.updatePeer(peer_permid, 'last_connected', now)
        

    def got_message(self,permid,message,selversion):
        """ received message from authenticated peer, pass to upper layer """
        if DEBUG:
            print >> sys.stderr,"secover: got_message",getMessageName(message[0]),\
                            "v"+str(selversion)
        if self.usermsghandler is None:
            if DEBUG:
                print >> sys.stderr,"secover: User receive callback not set"
            return
        try:
            ret = self.usermsghandler(permid,selversion,message)
            if ret is None:
                if DEBUG:
                    print >> sys.stderr,"secover: INTERNAL ERROR:", \
                        "User receive callback returned None, not True or False"
                ret = False
            elif DEBUG:
                print >> sys.stderr,"secover: message handler returned",ret
            return ret
        except:
            # Catch all
            print_exc()
            return False


    def get_max_len(self):
        return self.max_len
    
    def get_my_peer_id(self):
        return self.myid

    def get_my_keypair(self):
        return self.mykeypair

    def measurefunc(self,length):
        pass

    #
    # Interface for debugging
    #
    def debug_get_live_connections(self):
        """ return a list of (permid,dns) tuples of the peers with which we 
            are connected. Like all methods here it must be called by the network thread
        """
        live_conn = []
        for iplport in self.iplport2oc:
            oc = self.iplport2oc[iplport]
            if oc:
                peer_permid = oc.get_auth_permid()
                if peer_permid:
                    live_conn.append((peer_permid,(oc.get_ip(),oc.get_port())))
        return live_conn

    #
    # Internal methods
    #
    def get_dns_from_peerdb(self,permid):
        dns = None
        peer = self.peer_db.getPeer(permid)
        if peer:
            ip = self.to_real_ip(peer['ip'])
            dns = (ip, int(peer['port']))
        return dns

    def to_real_ip(self,hostname_or_ip):
        """ If it's a hostname convert it to IP address first """
        ip = None
        try:
            ip = gethostbyname(hostname_or_ip)
        except:
            pass
        return ip

    def start_connection(self,dns):
        if DEBUG:
            print >> sys.stderr,"secover: Attempt to connect to",dns
        singsock = self.sock_hand.start_connection(dns)
        oc = OverlayConnection(self,singsock,self.rawserver,
                               locally_initiated=True,specified_dns=dns)
        singsock.set_handler(oc)
        return oc

    def cleanup_admin_and_callbacks(self,oc,exc):
        oc.cleanup_callbacks(exc)
        self.cleanup_admin(oc)
        if oc.is_auth_done() and self.userconnhandler is not None:
            self.userconnhandler(exc,oc.get_auth_permid(),oc.get_sel_proto_ver(),
                                 oc.is_locally_initiated())

    def cleanup_admin(self,oc):
        iplports = []
        d = 0
        for key in self.iplport2oc.keys():
            #print "***** iplport2oc:", key, self.iplport2oc[key]
            if self.iplport2oc[key] == oc:
                del self.iplport2oc[key]
                #print "*****!!! del", key, oc
                d += 1
        
    def get_oc_by_permid(self, permid):
        """ return the OverlayConnection instance given a permid """

        for iplport in self.iplport2oc:
            oc = self.iplport2oc[iplport]
            if oc.get_auth_permid() == permid:
                return oc
        return None



class Task:
    def __init__(self,method,*args, **kwargs):
        self.method = method
        self.args = args
        self.kwargs = kwargs

    def start(self):
        if DEBUG:
            print >> sys.stderr,"secover: task: start",self.method
            #print_stack()
        self.method(*self.args,**self.kwargs)
    

class OverlayConnection:
    def __init__(self,handler,singsock,rawserver,locally_initiated = False,
                 specified_dns = None, ext_handshake = False,options = None):
        self.handler = handler        
        self.singsock = singsock # for writing
        self.rawserver = rawserver
        self.buffer = StringIO()
        self.cb_queue = []
        self.auth_permid = None
        self.unauth_peer_id = None
        self.auth_peer_id = None
        self.auth_listen_port = None
        self.low_proto_ver = 0
        self.cur_proto_ver = 0
        self.sel_proto_ver = 0
        self.options = None
        self.locally_initiated = locally_initiated
        self.specified_dns = specified_dns
        self.last_use = time()

        self.state = STATE_INITIAL
        self.write(chr(len(protocol_name)) + protocol_name + 
                option_pattern + overlay_infohash + self.handler.get_my_peer_id())
        if ext_handshake:
            self.state = STATE_HS_PEERID_WAIT
            self.next_len = 20
            self.next_func = self.read_peer_id
            self.set_options(options)
        else:
            self.state = STATE_HS_FULL_WAIT
            self.next_len = 1
            self.next_func = self.read_header_len
            
        # Leave autoclose here instead of SecureOverlay, as that doesn't record
        # remotely-initiated OverlayConnections before authentication is done.
        self.rawserver.add_task(self._olconn_auto_close, EXPIRE_CHECK_INTERVAL)

    #
    # Interface for SocketHandler
    #
    def data_came_in(self, singsock, data):
        """ sockethandler received data """
        # now we got something we can ask for the peer's real port
        dummy_port = singsock.get_port(True)

        if DEBUG:
            print >> sys.stderr,"olconn: data_came_in",singsock.get_ip(),singsock.get_port()
        self.handler.measurefunc(len(data))
        self.last_use = time()
        while 1:
            if self.state == STATE_CLOSED:
                return
            i = self.next_len - self.buffer.tell()
            if i > len(data):
                self.buffer.write(data)
                return
            self.buffer.write(data[:i])
            data = data[i:]
            m = self.buffer.getvalue()
            self.buffer.reset()
            self.buffer.truncate()
            try:
                if DEBUG:
                    print >> sys.stderr,"olconn: Trying to read",self.next_len,"using",self.next_func
                x = self.next_func(m)
            except:
                self.next_len, self.next_func = 1, self.read_dead
                if DEBUG:
                    print_exc()
                raise
            if x is None:
                if DEBUG:
                    print >> sys.stderr,"olconn: next_func returned None",self.next_func
                self.close()
                return
            self.next_len, self.next_func = x

    def connection_lost(self,singsock):
        """ kernel or socket handler reports connection lost """
        if DEBUG:
            print >> sys.stderr,"olconn: connection_lost",singsock.get_ip(),singsock.get_port(),self.state
        if self.state != STATE_CLOSED:
            self.state = STATE_CLOSED
            self.handler.connection_lost(self)

    def connection_flushed(self,singsock):
        """ sockethandler flushes connection """
        pass

    # 
    # Interface for SecureOverlay
    #
    def send_message(self,message):
        self.last_use = time()
        s = tobinary(len(message))+message
        self.write(s)

    def is_locally_initiated(self):
        return self.locally_initiated

    def get_ip(self):
        return self.singsock.get_ip()

    def get_port(self):
        return self.singsock.get_port()

    def is_auth_done(self):
        return self.auth_permid is not None

    def get_auth_permid(self):
        return self.auth_permid

    def get_auth_listen_port(self):
        return self.auth_listen_port

    def get_remote_listen_port(self):
        if self.is_auth_done():
            return self.auth_listen_port
        elif self.is_locally_initiated():
            return self.specified_dns[1]
        else:
            return NO_REMOTE_LISTEN_PORT_KNOWN

    def get_low_proto_ver(self):
        return self.low_proto_ver

    def get_cur_proto_ver(self):
        return self.cur_proto_ver

    def get_sel_proto_ver(self):
        return self.sel_proto_ver

    def queue_callback(self,dns,callback):
        if callback is not None:
            self.cb_queue.append(callback)

    def dequeue_callbacks(self):
        try:
            permid = self.get_auth_permid()
            for callback in self.cb_queue:
                callback(None,self.specified_dns,permid,self.get_sel_proto_ver())
            self.cb_queue = []
        except Exception,e:
            print_exc()


    def cleanup_callbacks(self,exc):
        if DEBUG:
            print >> sys.stderr,"olconn: cleanup_callbacks: #callbacks is",len(self.cb_queue)
        try:
            for callback in self.cb_queue:
                ## Failure connecting
                if DEBUG:
                   print >> sys.stderr,"olconn: cleanup_callbacks: callback is",callback
                callback(exc,self.specified_dns,self.get_auth_permid(),0)
        except Exception,e:
            print_exc()

    #
    # Interface for ChallengeResponse
    #
    def get_unauth_peer_id(self):
        return self.unauth_peer_id

    def got_auth_connection(self,singsock,permid,peer_id):
        """ authentication of peer via identity protocol succesful """
        self.auth_permid = str(permid)
        self.auth_peer_id = peer_id
        self.auth_listen_port = decode_auth_listen_port(peer_id)

        self.state = STATE_DATA_WAIT

        if not self.handler.got_auth_connection(self):
            self.close()
            return

    #
    # Internal methods
    #
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
            print >> sys.stderr,"olconn: Reserved bits:", `s`
        self.set_options(s)
        return 20, self.read_download_id

    def read_download_id(self, s):
        if s != overlay_infohash:
            return None
        return 20, self.read_peer_id

    def read_peer_id(self, s):
        self.unauth_peer_id = s
        [self.low_proto_ver,self.cur_proto_ver] = get_proto_version_from_peer_id(self.unauth_peer_id)
        self.sel_proto_ver = select_supported_protoversion(self.low_proto_ver,self.cur_proto_ver)
        if not self.sel_proto_ver:
            if DEBUG:
                print >> sys.stderr,"olconn: We don't support peer's version of the protocol"
            return None
        elif DEBUG:
                print >> sys.stderr,"olconn: Selected protocol version",self.sel_proto_ver

        self.state = STATE_AUTH_WAIT
        self.cr = ChallengeResponse(self.handler.get_my_keypair(),self.handler.get_my_peer_id(),self)
        if self.locally_initiated:
            self.cr.start_cr(self)
        return 4, self.read_len
    

    def read_len(self, s):
        l = toint(s)
        if l > self.handler.get_max_len():
            return None
        return l, self.read_message

    def read_message(self, s):
        if s != '':
            if self.state == STATE_AUTH_WAIT:
                if not self.cr.got_message(self,s):
                    return None
            elif self.state == STATE_DATA_WAIT:
                if not self.handler.got_message(self.auth_permid,s,self.sel_proto_ver):
                    return None
            else:
                if DEBUG:
                    print >> sys.stderr,"olconn: Received message while in illegal state, internal error!"
                return None
        return 4, self.read_len

    def read_dead(self, s):
        return None

    def write(self,s):
        self.singsock.write(s)

    def set_options(self,options):
        self.options = options

    def close(self):
        if DEBUG:
            print >> sys.stderr,"olconn: we close()",self.get_ip(),self.get_port()
            #print_stack()
        self.state_when_error = self.state
        if self.state != STATE_CLOSED:
            self.state = STATE_CLOSED
            self.handler.local_close(self)
            self.singsock.close()
        return

    def _olconn_auto_close(self):
        if (time() - self.last_use) > EXPIRE_THRESHOLD:
            self.close()
        else:
            self.rawserver.add_task(self._olconn_auto_close, EXPIRE_CHECK_INTERVAL)


#
# Internal functions
#
def create_my_peer_id(my_listen_port):
    myid = createPeerID()
    myid = myid[:16] + pack('<H', OLPROTO_VER_LOWEST) + pack('<H', OLPROTO_VER_CURRENT)
    myid = myid[:14] + pack('<H', my_listen_port) + myid[16:]
    return myid

def get_proto_version_from_peer_id(peerid):
    """ overlay swarm versioning solution- use last 4 bytes in PeerID """

    low_ver_str = peerid[16:18]
    cur_ver_str = peerid[18:20]
    low_ver = unpack('<H', low_ver_str)[0]
    cur_ver = unpack('<H', cur_ver_str)[0]
    return [low_ver,cur_ver]

def is_proto_version_supported(low_ver,cur_ver):
    if cur_ver != OLPROTO_VER_CURRENT:
        if low_ver > OLPROTO_VER_CURRENT:    # the other's version is too high
            return False
        if cur_ver < OLPROTO_VER_LOWEST:     # the other's version is too low
            return False           
        if cur_ver < OLPROTO_VER_CURRENT and \
           cur_ver not in SupportedVersions:   # the other's version is not supported
            return False
    return True

def select_supported_protoversion(his_low_ver,his_cur_ver):
    selected = None
    if his_cur_ver != OLPROTO_VER_CURRENT:
        if his_low_ver > OLPROTO_VER_CURRENT:    # the other's low version is too high
            return selected
        if his_cur_ver < OLPROTO_VER_LOWEST:     # the other's current version is too low
            return selected        
        if his_cur_ver < OLPROTO_VER_CURRENT and \
           his_cur_ver not in SupportedVersions:   # the other's current version is not supported (peer of this version is abondoned)
            return selected
        
    selected = min(his_cur_ver,OLPROTO_VER_CURRENT)
    return selected

def decode_auth_listen_port(peerid):
    bin = peerid[14:16]
    tup = unpack('<H', bin)
    return tup[0]

def ip_and_port2str(ip,port):
    return ip+':'+str(port)
