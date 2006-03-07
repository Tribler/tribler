# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information

""" 
- The middle layer between OverlaySwarm and BuddyCast/DownloadHelp 
- A high level module, like buddycast or dlhelp, calls SecureOverlay.addTask,
and then SecureOverlay will handle the task.
- There is only one task for secure overlay: Send message (the message can be None)
- But each time before sending a message, secure overlay must connect the target's
overlay.
- If the message is None, secure overlay only creates an overlay connection.
- Each time after an normal connection is created and if the other peer supports
overlay swarm, it will always create a task without message
- After overlay connection is created, secure overlay will update the (permid, (ip, port))
in local cache.
- The target can be either permid or (ip, port)
- If the target is permid, the task much check if target's permid matches
the task's permid
- If the target is (ip, port), connect directly and record the peer's permid later on.
"""

from time import time, ctime
from socket import inet_aton, gethostbyname
from traceback import print_exc, print_stack
from threading import RLock, currentThread
import sys

from BitTornado.BT1.MessageID import CANCEL, getMessageName
from Tribler.CacheDB.CacheDBHandler import PeerDBHandler, MyDBHandler
from Tribler.utilities import *
from Tribler.__init__ import GLOBAL
from Tribler.Statistics.Logger import OverlayLogger



try:
    True
except:
    True = 1
    False = 0

DEBUG = True

Length_of_permid = 0    # 0: no restriction

def isValidDNS(dns):
    if isinstance(dns, tuple) and len(dns)==2 and \
       validIP(dns[0]) and isValidPort(dns[1]):
           return True
    return False
    

class DNSOverlayTask:
    """ 
    Basic task to connect peer's overlay swarm by dns and send message by Secure Overlay.
    It is an observer class in Observer Pattern.
    """
    
    def __init__(self, secure_overlay, subject_manager, dns, message=None, timeout=15):
        self.subject_manager = subject_manager
        self.dns = dns
        self.message_to_send = message
        self.callback = None    # used by update
        self.secure_overlay = secure_overlay
        self.subject = None
        self.expire = int(time() + timeout)
        self.registered = False
        
    def isExpired(self, now=0):
        if now == 0:
            now = time()
        return now > self.expire
        
    def register(self, dns):    # register a subject
        if self.registered or not dns:
            return
        self.subject = self.subject_manager.getSubject(dns)    # register a subject or get an old subject
        self.subject.attachObserver(self)
        self.registered = True

    def unregister(self, reason='done'):    # TODO: count and record the fail reason
#        if DEBUG:
#            print >> sys.stderr, "secover: task on %s %s" % (self.dns, reason)
        if self.registered:
            if self.subject:
                self.subject.detachObserver(self, reason)
        self.registered = False
            
    def setCallback(self, callback):    # it must be set before start
        self.callback = callback
        
    def start(self):    # phase 1: find or make overlay connection
        if self.isExpired():
            self.unregister('expired')
        elif self.findConnection():    # if connection exists, send message now
            self.sendMessage()    
        else:
            self.register(self.dns)    # otherwise make overlay connection
            self.makeConnection()
            return 1    # make a new connecting attempt
        return 0
                
    def update(self):    # phase 2: overlay connection has been made; send msg now
#        if DEBUG:
#            print >> sys.stderr,"secover: overlay task update", self.dns, id(self)
        if not self.registered:
            return
        # to improve performance, don't remove expired tasks at this point
        if self.callback:    # used by other task
            reason = self.callback()
            if reason != 'done':
                self.unregister(reason)
        else:
            self.sendMessage()
        
    def sendMessage(self):
        if self.message_to_send != None:
            if not self.permid:
                self.permid = self.secure_overlay.findPermidByDNS(self.dns)
            self.secure_overlay.sendMessage(self.permid, self.message_to_send)
            if DEBUG:
                print >> sys.stderr,"secover: dns task send message", getMessageName(self.message_to_send[0]), self.dns
            self.message_to_send = None
        self.unregister('done')
        
    def makeConnection(self):
        self.secure_overlay.connectPeer(self.dns)
        
    def findConnection(self):
        # if connection is created, secure overlay must have the permid
        self.permid = self.secure_overlay.findPermidByDNS(self.dns)
        return self.permid


class PermidOverlayTask:
    """ 
    A task to connect peer's overlay swarm by permid and send message.
    It delegates DNSOverlayTask to do the real stuffs.
    """
    
    def __init__(self, secure_overlay, subject_manager, permid, message=None, timeout=15):
        self.secure_overlay = secure_overlay
        self.permid = permid
        self.dns = self.secure_overlay.findDNSByPermid(self.permid)    # first lookup overlay
        self.peer_db = secure_overlay.peer_db
        if not self.dns:    # then lookup local cache
            #if DEBUG:
            #    print >> sys.stderr,"secover: PermidOverlayTask: don't know dns for permid",show_permid(permid)
            self.dns = self.findDNSFromCache()
        else:
            #if DEBUG:
            #    print >> sys.stderr,"secover: PermidOverlayTask: dns for permid is known",self.dns
            pass
        if isValidDNS(self.dns):
            if GLOBAL.overlay_log:
                write_overlay_log('CONN_TRY', permid, dns=self.dns)
            self.task = DNSOverlayTask(secure_overlay, subject_manager, self.dns, message, timeout)
        else:
            self.task = None
        
    def findDNSFromCache(self):
        #if DEBUG:
        #    return ('1.2.3.4', 80)
        peer = self.peer_db.getPeer(self.permid)
        if peer:
            return (peer['ip'], int(peer['port']))
        
    def start(self):    # phase 1: start basic overlay task
        if self.task:
            self.task.setCallback(self.update)
            ret = self.task.start()
            if ret == 1:
                self.secure_overlay.addTryTimes(self.permid)
            
    def update(self):    # phase 2: check permids, and send msg if they match
#        if DEBUG:
#            print >> sys.stderr,"secover: permid task update", self.dns
        
        if self.dns:
            permid = self.secure_overlay.findPermidByDNS(self.dns)

            #if DEBUG:
            #    print >> sys.stderr,"secover: Think connecting to",show_permid(self.permid)," and connected to",show_permid(permid)

            if self.permid == permid and self.task:
                self.task.sendMessage()
                return 'done'
            elif DEBUG and self.permid != permid:
                print >> sys.stderr,"secover: Connection established but permid does not match!"
                return 'wrong_permid'
    
                        
class Subject:
    """ A subject class in Observer Pattern """
    
    def __init__(self, dns, subject_manager):
        self.dns = dns    # dns = (ip, port)
        self.observers = []    # tasks
        self.subject_manager = subject_manager
        
    def isEmpty(self):
        return len(self.observers) == 0
        
    def notify(self):
        for observer in self.observers:
            #if DEBUG:
            #    print >> sys.stderr,"secover: subject", self.dns, "notifies observer", observer
            observer.update()
            
    def attachObserver(self, observer):
        if observer not in self.observers:
            self.observers.append(observer)
            #if DEBUG:
            #    print >> sys.stderr,"secover: subject", self.dns, "attaches observer", self.observers
        
    def detachObserver(self, observer, reason):
#        if DEBUG:
#            print >> sys.stderr,"secover: subject", self.dns, "detaches observer", observer
        
        self.observers.remove(observer)
        
        if self.isEmpty():
            self.subject_manager.unregisterSubject(self.dns, reason)
        
        
class SubjectManager:
    """ Command Pattern. Used for sending overlay message. """
    
    def __init__(self):
        self.subjects = {}    # (ip,port): Subject
    
    def registerSubject(self, dns):
        #if DEBUG:
        #    print >> sys.stderr,"secover: register subject", dns
        if not self.subjects.has_key(dns):
            self.subjects[dns] = Subject(dns, self)
                
    def unregisterSubject(self, dns, reason):
        if self.subjects.has_key(dns) and self.subjects[dns].isEmpty():
            if DEBUG:
                print >> sys.stderr,"secover: unregister subject", dns, reason
            sbj = self.subjects.pop(dns)
            del sbj
            
    
    def getSubject(self, dns):
        self.registerSubject(dns)    # ensure the subject exists
        return self.subjects[dns]        
            
    def notifySubject(self, dns):    # notify the connection is made
        #if DEBUG:
        #    print >> sys.stderr,"secover: notify subject", dns
        if dns and self.subjects.has_key(dns):
            subject = self.subjects[dns]
            subject.notify()

    def scanTasks(self):    # remove outdate subjects
        now = time()
        for dns in self.subjects.keys():
            expired = True
            sbj_obs = self.subjects[dns].observers
            for obs in sbj_obs[:]:
                if not obs.isExpired(now):
                    expired = False    # don't remove a subject if one of its observer is not expired
                else:
                    l = len(self.subjects[dns].observers)
                    obs.unregister('expired')
                    del obs

class IncomingMessageHandler:
    """ a variant of Chain of Responsibility Pattern """
    
    def __init__(self):
        self.handlers = {}
        
    def registerHandler(self, ids, handler):
        for id in ids:
#            if DEBUG:
#                print >> sys.stderr,"secover: Handler registered for",getMessageName(id)
            self.handlers[id] = handler
        
    def handleMessage(self, permid, message):    # connection is type of Conneter.Connection 
        id = message[0]
        handled = False
        if not self.handlers.has_key(id):
            if DEBUG:
                print >> sys.stderr,"secover: No handler found for",getMessageName(id),currentThread().getName()
            return False
        else:
            #if DEBUG:
            #    print >> sys.stderr,"secover: Giving message to handler for",getMessageName(id)
            self.handlers[id].handleMessage(permid, message)
            return True

class SecureOverlay:
    __single = None

    def __init__(self):
        if SecureOverlay.__single:
            raise RuntimeError, "SecureOverlay is Singleton"
        SecureOverlay.__single = self 
        self.subject_manager = SubjectManager()    #???? for outgoing message
        self.incoming_handler = IncomingMessageHandler()    # for incoming message
        self.peer_db = PeerDBHandler()
        self.connection_list = {}    # overlay connections. permid:{'c_conn': Connecter.Connection, 'expire':expire, 'dns':(ip, port)}
        self.timeout = 300    # TODO: adjust it by firewall status. the value is smaller if no firewall
        self.check_interval = 60
        self.my_db = MyDBHandler()
        self.permid = self.my_db.getMyPermid()
        self.ip = self.my_db.getMyIP()
        self.lock = RLock()
        
    def getInstance(*args, **kw):
        if SecureOverlay.__single is None:
            SecureOverlay(*args, **kw)
        return SecureOverlay.__single
    getInstance = staticmethod(getInstance)
    
    def register(self,overlayswarm):
        self.overlayswarm = overlayswarm
        self.overlayswarm.rawserver.add_task(self._auto_close, self.check_interval)
        self.overlayswarm.rawserver.add_task(self._scan_tasks, self.check_interval)

    def registerHandler(self, ids, handler):    
        """ 
          ids is the [ID1, ID2, ..] where IDn is a sort of message ID in overlay swarm. 
          Each ID can only be handled by one handler, but a handler can handle multiple IDs
        """
        # I assume that all handler registration is done before handling, so no
        # concurrency on incoming_handler
        self.incoming_handler.registerHandler(ids, handler)

    def _auto_close(self):
        self.acquire()
        self.overlayswarm.rawserver.add_task(self._auto_close, self.check_interval)
        self._checkConnections()
        self.release()    

    def _scan_tasks(self):
        self.acquire()
        self.overlayswarm.rawserver.add_task(self._scan_tasks, self.check_interval)
        self.subject_manager.scanTasks()
        self.release()    

    def _checkConnections(self):
        for permid in self.connection_list.keys():
            self._checkConnection(permid)

    def _checkConnection(self, permid):
        conn = self.connection_list[permid]['c_conn']
        expire = self.connection_list[permid]['expire']
        expired = time() > expire
        if not conn or conn.closed or expired:
            if expired:
                if DEBUG:                         
                    print >> sys.stderr,"secover: closing expired conn",show_permid2(permid), int(time())
                self._closeConnection(conn, 'TIME_OUT')
            else:
                if DEBUG:                         
                    print >> sys.stderr,"secover: removing closed conn",show_permid2(permid)
                self._closePermidConnection(permid, 'CON_CLOS')
            ret = None
        else:
            ret = conn
        return ret
        
    # the central place to close connection
    def _closeConnection(self, connection, reason):
        self.acquire()
        if connection is not None and not connection.closed:
            permid = connection.permid
            connection.close()
            ## connectionLost callback is called by connection.close() which
            ## will remove the conn from the list, but just to be safe:
            if permid and self.connection_list.has_key(permid):
                if GLOBAL.overlay_log:
                    write_overlay_log('CONN_DEL', permid, reason=reason)
                self.connection_list.pop(permid)
        self.release()        
    
    def _closePermidConnection(self, permid, reason):
        self.acquire()
        if self.connection_list.has_key(permid):
            connection = self.connection_list[permid]['c_conn']
            if connection is not None and not connection.closed:
                connection.close()
            if GLOBAL.overlay_log:
                write_overlay_log('CONN_DEL', permid, reason=reason)
            self.connection_list.pop(permid)
        self.release()        

    def _findConnByPermid(self, permid):
        if self.connection_list.has_key(permid):
            return self._checkConnection(permid)
        else:
            return None
        
    def findPermidByDNS(self, dns):    #find permid from connection_list
        self.acquire()
        ret = None
        for permid, value in self.connection_list.items():
            if value['dns'] == dns and self._checkConnection(permid):
                ret = permid
                break
        self.release()
        return ret

    def findDNSByPermid(self, permid):
        self.acquire()
        ret = None
        if self._findConnByPermid(permid):
            ret = self.connection_list[permid]['dns']
        self.release()
        return ret
        
    # Main function to send messages
    def addTask(self, target, message=None, timeout=15):    # target = [permid|(ip,port)]
        """ Command Pattern """
        
        self.acquire()
        #TODO: priority task queue
        try:
            try:
                if message is None:
                    msg_id = 'None'
                else:
                    msg_id = getMessageName(message[0])
                if msg_id.startswith('Unknown'):
                    return
                if isValidPermid(target) and target != self.permid:
                    if DEBUG:
                        msg = msg_id + ' '+currentThread().getName()
                        if DEBUG:
                            print >> sys.stderr,"secover: add PermidOverlayTask", show_permid_short(target), msg
                    task = PermidOverlayTask(self, self.subject_manager, target, message, timeout)
                elif isValidDNS(target): # and target[0] != self.ip:    # for testing
                    if DEBUG:
                        if message is None:
                            msg = 'None'
                        else:
                            msg = getMessageName(message[0])
                        msg = msg_id + ' '+currentThread().getName()
                        if DEBUG:
                            print >> sys.stderr,"secover: add DNSOverlayTask", target, msg
                    task = DNSOverlayTask(self, self.subject_manager, target, message, timeout)
                else:
                    return
                if task and self.overlayswarm.registered:
                    ## Arno: I don't see the need for letting the rawserver do it.
                    ## Except that it potentially avoids a concurrency problem of
                    ## multiple threads writing to the same socket.
                    if DEBUG:
                        if message:
                            msg_id = getMessageName(message[0])
                        else:
                            msg_id = ''
                        print >> sys.stderr,"secover: add task to rawserver", msg_id, currentThread().getName()
                    self.overlayswarm.rawserver.add_task(task.start, 0)
                    ##task.start()
            except Exception,e:
                print_exc()
        finally:
            self.release()        

    def connectionMade(self, connection):    # OverlayConnecter.Connection
        self.acquire()
        if DEBUG:
            print >> sys.stderr,"secover: *** secure overlay to %s connection made." % show_permid2(connection.permid), connection.get_ip(), int(time())
        #TODO: schedule it on rawserver task queue?
        dns = self._addConnection(connection)
        if dns:
            if GLOBAL.overlay_log:
                write_overlay_log('CONN_ADD', connection.permid)
            self.subject_manager.notifySubject(dns)
        self.release()    
        
    def addTryTimes(self, permid):
        self.peer_db.updateTimes(permid, 'tried_times', 1)
            
    def _addConnection(self, connection):
        dns = connection.dns
        permid = connection.permid
        self.peer_db.updateTimes(permid, 'connected_times', 1)
        auth_listen_port = connection.get_auth_listen_port()
        if DEBUG:
            print >> sys.stderr,"secover: add connection in secure overlay", dns, "auth listen port", auth_listen_port
        #
        # Arno: if DNS is none, this is an incoming connection from another
        # peer. We cannot enter this connection into the table because we don't
        # know the listen port of the peer (and if we would initiate a connection
        # that is the port we look for). However, I encoded the listen port of a peer
        # into its peerID. So now we know the initiating peers listen port and
        # the problem is solved.
        #
        if dns is None:
            dns = ( connection.get_ip(), auth_listen_port )
        else:
            if dns[1] != auth_listen_port:
                if DEBUG:
                    print >> sys.stderr,"secover: WARNING given listen port not equal to authenticated one"

        if isValidPermid(permid) and isValidDNS(dns):
            if self.connection_list.has_key(permid):
                # Conccurency: When a peer starts an overlay connection at
                # the same time, and we start it before the C/R protocol
                # has finished, we'll end up with two connections. In that
                # case we drop the last one established.
                if DEBUG:
                    print >> sys.stderr,"secover: dropping superfluous double connection to",show_permid2(permid)
                connection.close()
                # Don't stop
                return dns

            self._updateDNS(permid, dns)
            expire = int(time() + self.timeout)
            self.connection_list[permid] = {'c_conn':connection, 'dns':dns, 'expire':expire}
            if DEBUG:
                print >> sys.stderr,"secover: permid received is", show_permid2(permid)
            #x = self.peer_db.getPeer(permid)
            #print >> sys.stderr,"secover: old peer is",x
            #self.peer_db.updatePeerIPPort(permid, dns[0], dns[1])
            #y = self.peer_db.getPeer(permid)
            #print >> sys.stderr,"secover: new peer is",y
            return dns
        return None
        
    def _updateDNS(self, permid, dns):
        self.peer_db.updatePeerIPPort(permid, dns[0], dns[1])
        
    def _extendExpire(self, permid):
        self.connection_list[permid]['expire'] = int(time() + self.timeout)
        
    def connectionLost(self, connection):    # OverlayConnecter.Connection
        if DEBUG:
            print >> sys.stderr,"secover: ***** secure overlay connection lost", show_permid2(connection.permid), connection.get_ip(), int(time())
        self.acquire()
        self._closeConnection(connection, 'CON_LOST')
        self.release()

    def connectPeer(self, dns):    # called by task
        self.acquire()
        self.overlayswarm.connectPeer(dns)
        self.release()    

    def sendMessage(self, permid, message):
        if not permid:
            return
        self.acquire()
        connection = self._findConnByPermid(permid)
        if connection:
            if GLOBAL.overlay_log:
                write_overlay_log('SEND_MSG', permid, message)
            self._extendExpire(permid)
            self.overlayswarm.sendMessage(connection, message)
        self.release()

    def gotMessage(self, permid, message):    # connection is type of Connecter.Connection 
        self.acquire()
        try:
            if GLOBAL.overlay_log:
                write_overlay_log('RECV_MSG', permid, message)
            t = message[0]
            if t == CANCEL:    # the only message handled by secure overlay
                self._closePermidConnection(permid, 'CANCELED')
            elif self.incoming_handler.handleMessage(permid, message) == False:
                self._closePermidConnection(permid, 'FAKE_MSG')
            else:
                self._extendExpire(permid)
        except:
            print_exc()
        self.release()

    def acquire(self):
#        if DEBUG:
#            print >> sys.stderr,"secover: LOCK",currentThread().getName()
        self.lock.acquire()
        
    def release(self):
#        if DEBUG:
#            print >> sys.stderr,"secover: UNLOCK",currentThread().getName()
        self.lock.release()


def write_overlay_log(action, permid, msg=None, dns=None, reason=None):
    """
      SecureOverlay log format:
          TIME - CONN_TRY - IP - PORT - PERMID
          TIME - CONN_ADD - IP - PORT - PERMID 
          TIME - CONN_DEL - IP - PORT - REASON(TIME_OUT, CON_CLOS, CON_LOST, CANCELED, FAKE_MSG) - PERMID
          TIME - SEND_MSG - IP - PORT - MSG_ID - PERMID - MSG 
          TIME - RECV_MSG - IP - PORT - MSG_ID - PERMID - MSG
    """
    
    if dns is not None and permid is not None:
        ip, port = dns
    elif isValidPermid(permid):    # permid, msg
        secure_overlay = SecureOverlay.getInstance()
        dns = secure_overlay.connection_list[permid]['dns']
        ip = dns[0]
        port = dns[1]
    else:    # connection
        permid = 'Permid_None'
        ip = 'None_ip'
        port = 0        
        
    if permid != 'Permid_None':
        permid = show_permid(permid)
    port = str(port)
    sp_log = OverlayLogger.getInstance(GLOBAL.overlay_log)
    if msg:
        msg_name = getMessageName(msg[0])
        sp_log.log(action, ip, port, msg_name, permid, `msg`)    # SEND_MSG, RECV_MSG
    else:
        if reason is not None:
            sp_log.log(action, ip, port, reason, permid)    # CONN_DEL
        else:
            sp_log.log(action, ip, port, permid)    # CONN_TRY, CONN_ADD
    

def test():            
    so = SecureOverlay.getInstance()
    so.overlayswarm.secure_overlay = so
    dns = ('4.3.2.1', 1111)
    permid = 'permid1'
    so.addTask(permid)
    so.addTask(dns, message="hello overlay")

