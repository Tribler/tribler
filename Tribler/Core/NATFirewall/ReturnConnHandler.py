# Written by Arno Bakker, Bram Cohen, Jie Yang
# see LICENSE.txt for license information
#
# This class receives all connections and messages destined for 
# infohash = 0x00 0x00 ... 0x01
# The peer sends a DIALBACK_REPLY message, we send no reply.
#

import sys
from struct import pack,unpack
from time import time
from sets import Set
from cStringIO import StringIO
from threading import currentThread
from socket import gethostbyname
from traceback import print_exc,print_stack

from Tribler.Core.BitTornado.__init__ import createPeerID
from Tribler.Core.BitTornado.BT1.MessageID import protocol_name,option_pattern,getMessageName
from Tribler.Core.BitTornado.BT1.convert import tobinary,toint


DEBUG = False

#
# Public definitions
#
dialback_infohash = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01'

#
# Private definitions
#

# States for overlay connection
STATE_INITIAL = 0
STATE_HS_FULL_WAIT = 1
STATE_HS_PEERID_WAIT = 2
STATE_DATA_WAIT = 4
STATE_CLOSED = 5

# Misc
EXPIRE_THRESHOLD =      30    # seconds::  keep consistent with sockethandler
EXPIRE_CHECK_INTERVAL = 60     # seconds


class ReturnConnHandler:
    __single = None

    def __init__(self):
        if ReturnConnHandler.__single:
            raise RuntimeError, "ReturnConnHandler is Singleton"
        ReturnConnHandler.__single = self 

    #
    # Interface for upper layer
    #
    def getInstance(*args, **kw):
        if ReturnConnHandler.__single is None:
            ReturnConnHandler(*args, **kw)
        return ReturnConnHandler.__single
    getInstance = staticmethod(getInstance)

    def register(self,rawserver,multihandler,mylistenport,max_len):
        self.rawserver = rawserver
        self.sock_hand = self.rawserver.sockethandler
        self.multihandler = multihandler
        self.dialback_rawserver = multihandler.newRawServer(dialback_infohash, 
                                              self.rawserver.doneflag,
                                              protocol_name)
        self.myid = create_my_peer_id(mylistenport)
        self.max_len = max_len
        self.iplport2oc = {}    # (IP,listen port) -> ReturnConnection
        self.usermsghandler = None
        self.userconnhandler = None

    def resetSingleton(self):
        """ For testing purposes """
        ReturnConnHandler.__single = None 

    def start_listening(self):
        self.dialback_rawserver.start_listening(self)

    def connect_dns(self,dns,callback):
        """ Connects to the indicated endpoint. Non-blocking.
            
            Pre: "dns" must be an IP address, not a hostname.
            
            Network thread calls "callback(exc,dns)" when the connection
            is established or when an error occurs during connection 
            establishment. In the former case, exc is None, otherwise
            it contains an Exception.

            The established connection will auto close after EXPIRE_THRESHOLD
            seconds of inactivity.
        """
        if DEBUG:
            print >> sys.stderr,"dlbreturn: connect_dns",dns
        # To prevent concurrency problems on sockets the calling thread 
        # delegates to the network thread.
        task = Task(self._connect_dns,dns,callback)
        self.rawserver.add_task(task.start, 0)


    def send(self,dns,msg,callback):
        """ Sends a message to the indicated dns. Non-blocking.
            
            Pre: connection to permid must have been established successfully.

            Network thread calls "callback(exc,dns)" when the message is sent
            or when an error occurs during sending. In the former case, exc 
            is None, otherwise it contains an Exception.
        """
        # To prevent concurrency problems on sockets the calling thread 
        # delegates to the network thread.
        task = Task(self._send,dns,msg,callback)
        self.rawserver.add_task(task.start, 0)



    def close(self,dns):
        """ Closes any connection to indicated permid. Non-blocking.
            
            Pre: connection to permid must have been established successfully.

            Network thread calls "callback(exc,permid,selver)" when the connection
            is closed.
        """
        # To prevent concurrency problems on sockets the calling thread 
        # delegates to the network thread.
        task = Task(self._close,dns)
        self.rawserver.add_task(task.start, 0)


    def register_recv_callback(self,callback):
        """ Register a callback to be called when receiving a message from 
            any permid. Non-blocking.

            Network thread calls "callback(exc,permid,selver,msg)" when a message 
            is received. The callback is not called on errors e.g. remote 
            connection close.
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
                print >> sys.stderr,"dlbreturn: actual connect_dns",dns
            iplport = ip_and_port2str(dns[0],dns[1])
            oc = None
            try:
                oc = self.iplport2oc[iplport]
            except KeyError:
                pass
            if oc is None:
                oc = self.start_connection(dns)
                self.iplport2oc[iplport] = oc
                oc.queue_callback(dns,callback)
            else:
                callback(None,dns)
        except Exception,exc:
            if DEBUG:
                print_exc(file=sys.stderr)
            callback(exc,dns)

    def _send(self,dns,message,callback):
        try:
            iplport = ip_and_port2str(dns[0],dns[1])
            oc = None
            try:
                oc = self.iplport2oc[iplport]
            except KeyError:
                pass
            if oc is None:
                callback(KeyError('Not connected to dns'),dns)
            else:
                oc.send_message(message)
                callback(None,dns)
        except Exception,exc:
            if DEBUG:
                print_exc(file=sys.stderr)
            callback(exc,dns)


    def _close(self,dns):
        if DEBUG:
            print >> sys.stderr,"dlbreturn: actual close",dns
        try:
            iplport = ip_and_port2str(dns[0],dns[1])
            oc = None
            try:
                oc = self.iplport2oc[iplport]
            except KeyError:
                pass
            if oc is None:
                if DEBUG:
                    print >> sys.stderr,"dlbreturn: error - actual close, but no connection to peer in admin"
            else:
                oc.close()
        except Exception,e:
            print_exc(file=sys.stderr)

    #
    # Interface for SocketHandler
    #
    def external_connection_made(self,singsock):
        """ incoming connection (never used) """
        if DEBUG:
            print >> sys.stderr,"dlbreturn: external_connection_made",singsock.get_ip(),singsock.get_port()
        oc = ReturnConnection(self,singsock,self.rawserver)
        singsock.set_handler(oc)

    def connection_flushed(self,singsock):
        """ sockethandler flushes connection """
        if DEBUG:
            print >> sys.stderr,"dlbreturn: connection_flushed",singsock.get_ip(),singsock.get_port()
        pass

    #
    # Interface for ServerPortHandler
    #
    def externally_handshaked_connection_made(self, singsock, options, msg_remainder):
        """ incoming connection, handshake partially read to identity 
            as an it as overlay connection (used always)
        """
        if DEBUG:
            print >> sys.stderr,"dlbreturn: externally_handshaked_connection_made",\
                singsock.get_ip(),singsock.get_port()
        oc = ReturnConnection(self,singsock,self.rawserver,ext_handshake = True, options = options)
        singsock.set_handler(oc)
        if msg_remainder:
            oc.data_came_in(singsock,msg_remainder)
        return True


    #
    # Interface for ReturnConnection
    #
    def got_connection(self,oc):
        
        if DEBUG:
            print >>sys.stderr,"dlbreturn: Got connection from",oc.get_ip(),"listen",oc.get_listen_port()
        
        ret = True
        iplport = ip_and_port2str(oc.get_ip(),oc.get_listen_port())
        known = iplport in self.iplport2oc
        if not known:
            self.iplport2oc[iplport] = oc
        elif known and not oc.is_locally_initiated():
            # Locally initiated connections will already be registered,
            # so if it's not a local connection and we already have one 
            # we have a duplicate, and we close the new one.
            if DEBUG:
                print >> sys.stderr,"dlbreturn: got_connection:", \
                    "closing because we already have a connection to",iplport
            self.cleanup_admin_and_callbacks(oc,
                     Exception('closing because we already have a connection to peer'))
            ret = False
            
        if ret:
            oc.dequeue_callbacks()
            if self.userconnhandler is not None:
                try:
                    self.userconnhandler(None,(oc.get_ip(),oc.get_listen_port()),oc.is_locally_initiated())
                except:
                    # Catchall
                    print_exc(file=sys.stderr)
        return ret

    def local_close(self,oc):
        """ our side is closing the connection """
        if DEBUG:
            print >> sys.stderr,"dlbreturn: local_close"
        self.cleanup_admin_and_callbacks(oc,Exception('local close'))

    def connection_lost(self,oc):
        """ overlay connection telling us to clear admin """
        if DEBUG:
            print >> sys.stderr,"dlbreturn: connection_lost"
        self.cleanup_admin_and_callbacks(oc,Exception('connection lost'))

    def got_message(self,dns,message):
        """ received message from peer, pass to upper layer """
        if DEBUG:
            print >> sys.stderr,"dlbreturn: got_message",getMessageName(message[0])
        if self.usermsghandler is None:
            if DEBUG:
                print >> sys.stderr,"dlbreturn: User receive callback not set"
            return
        try:
            ret = self.usermsghandler(dns,message)
            if ret is None:
                if DEBUG:
                    print >> sys.stderr,"dlbreturn: INTERNAL ERROR:", \
                        "User receive callback returned None, not True or False"
                ret = False
            return ret
        except:
            # Catch all
            print_exc(file=sys.stderr)
            return False


    def get_max_len(self):
        return self.max_len
   
    def get_my_peer_id(self):
        return self.myid
    
    def measurefunc(self,length):
        pass

    def start_connection(self,dns):
        if DEBUG:
            print >> sys.stderr,"dlbreturn: Attempt to connect to",dns
        singsock = self.sock_hand.start_connection(dns)
        oc = ReturnConnection(self,singsock,self.rawserver,
                               locally_initiated=True,specified_dns=dns)
        singsock.set_handler(oc)
        return oc

    def cleanup_admin_and_callbacks(self,oc,exc):
        oc.cleanup_callbacks(exc)
        self.cleanup_admin(oc)
        if self.userconnhandler is not None:
            self.userconnhandler(exc,(oc.get_ip(),oc.get_listen_port()),oc.is_locally_initiated())

    def cleanup_admin(self,oc):
        iplports = []
        d = 0
        for key in self.iplport2oc.keys():
            #print "***** iplport2oc:", key, self.iplport2oc[key]
            if self.iplport2oc[key] == oc:
                del self.iplport2oc[key]
                #print "*****!!! del", key, oc
                d += 1
        

class Task:
    def __init__(self,method,*args, **kwargs):
        self.method = method
        self.args = args
        self.kwargs = kwargs

    def start(self):
        if DEBUG:
            print >> sys.stderr,"dlbreturn: task: start",self.method
            #print_stack(file=sys.stderr)
        self.method(*self.args,**self.kwargs)
    

class ReturnConnection:
    def __init__(self,handler,singsock,rawserver,locally_initiated = False,
                 specified_dns = None, ext_handshake = False,options = None):
        self.handler = handler        
        self.singsock = singsock # for writing
        self.rawserver = rawserver
        self.buffer = StringIO()
        self.cb_queue = []
        self.listen_port = None
        self.options = None
        self.locally_initiated = locally_initiated
        self.specified_dns = specified_dns
        self.last_use = time()

        self.state = STATE_INITIAL
        self.write(chr(len(protocol_name)) + protocol_name + 
                option_pattern + dialback_infohash + self.handler.get_my_peer_id())
        if ext_handshake:
            self.state = STATE_HS_PEERID_WAIT
            self.next_len = 20
            self.next_func = self.read_peer_id
            self.set_options(options)
        else:
            self.state = STATE_HS_FULL_WAIT
            self.next_len = 1
            self.next_func = self.read_header_len
            
        # Leave autoclose here instead of ReturnConnHandler, as that doesn't record
        # remotely-initiated ReturnConnections before authentication is done.
        self.rawserver.add_task(self._dlbconn_auto_close, EXPIRE_CHECK_INTERVAL)

    #
    # Interface for SocketHandler
    #
    def data_came_in(self, singsock, data):
        """ sockethandler received data """
        # now we got something we can ask for the peer's real port
        dummy_port = singsock.get_port(True)

        if DEBUG:
            print >> sys.stderr,"dlbconn: data_came_in",singsock.get_ip(),singsock.get_port()
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
                #if DEBUG:
                #    print >> sys.stderr,"dlbconn: Trying to read",self.next_len,"using",self.next_func
                x = self.next_func(m)
            except:
                self.next_len, self.next_func = 1, self.read_dead
                if DEBUG:
                    print_exc(file=sys.stderr)
                raise
            if x is None:
                if DEBUG:
                    print >> sys.stderr,"dlbconn: next_func returned None",self.next_func
                self.close()
                return
            self.next_len, self.next_func = x

    def connection_lost(self,singsock):
        """ kernel or socket handler reports connection lost """
        if DEBUG:
            print >> sys.stderr,"dlbconn: connection_lost",singsock.get_ip(),singsock.get_port(),self.state
        if self.state != STATE_CLOSED:
            self.state = STATE_CLOSED
            self.handler.connection_lost(self)

    def connection_flushed(self,singsock):
        """ sockethandler flushes connection """
        pass

    # 
    # Interface for ReturnConnHandler
    #
    def send_message(self,message):
        self.last_use = time()
        s = tobinary(len(message))+message
        if DEBUG:
            print >> sys.stderr,"dlbconn: Sending message",len(message)
        self.write(s)

    def is_locally_initiated(self):
        return self.locally_initiated

    def get_ip(self):
        return self.singsock.get_ip()

    def get_port(self):
        return self.singsock.get_port()

    def get_listen_port(self):
        return self.listen_port

    def queue_callback(self,dns,callback):
        if callback is not None:
            self.cb_queue.append(callback)

    def dequeue_callbacks(self):
        try:
            for callback in self.cb_queue:
                callback(None,self.specified_dns)
            self.cb_queue = []
        except Exception,e:
            print_exc(file=sys.stderr)


    def cleanup_callbacks(self,exc):
        if DEBUG:
            print >> sys.stderr,"dlbconn: cleanup_callbacks: #callbacks is",len(self.cb_queue)
        try:
            for callback in self.cb_queue:
                ## Failure connecting
                if DEBUG:
                   print >> sys.stderr,"dlbconn: cleanup_callbacks: callback is",callback
                callback(exc,self.specified_dns)
        except Exception,e:
            print_exc(file=sys.stderr)

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
            print >> sys.stderr,"dlbconn: Reserved bits:", `s`
        self.set_options(s)
        return 20, self.read_download_id

    def read_download_id(self, s):
        if s != dialback_infohash:
            return None
        return 20, self.read_peer_id

    def read_peer_id(self, s):
        self.unauth_peer_id = s
        self.listen_port = decode_listen_port(self.unauth_peer_id)
        self.state = STATE_DATA_WAIT
        if not self.got_connection():
            self.close()
            return
        return 4, self.read_len
    
    
    def got_connection(self):
        return self.handler.got_connection(self)

    def read_len(self, s):
        l = toint(s)
        if l > self.handler.get_max_len():
            return None
        return l, self.read_message

    def read_message(self, s):
        
        if DEBUG:
            print >>sys.stderr,"dlbconn: read_message len",len(s),self.state
        
        if s != '':
            if self.state == STATE_DATA_WAIT:
                if not self.handler.got_message((self.get_ip(),self.get_listen_port()),s):
                    return None
            else:
                if DEBUG:
                    print >> sys.stderr,"dlbconn: Received message while in illegal state, internal error!"
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
            print >> sys.stderr,"dlbconn: we close()",self.get_ip(),self.get_port()
        self.state_when_error = self.state
        if self.state != STATE_CLOSED:
            self.state = STATE_CLOSED
            self.handler.local_close(self)
            self.singsock.close()
        return

    def _dlbconn_auto_close(self):
        if (time() - self.last_use) > EXPIRE_THRESHOLD:
            self.close()
        else:
            self.rawserver.add_task(self._dlbconn_auto_close, EXPIRE_CHECK_INTERVAL)

def create_my_peer_id(my_listen_port):
    myid = createPeerID()
    myid = myid[:14] + pack('<H', my_listen_port) + myid[16:]
    return myid

def decode_listen_port(peerid):
    bin = peerid[14:16]
    tup = unpack('<H', bin)
    return tup[0]

def ip_and_port2str(ip,port):
    return ip+':'+str(port)
