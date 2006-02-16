# Written by Jie Yang
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

from time import time
from socket import inet_aton, gethostbyname
from traceback import print_exc, print_stack
from threading import RLock, currentThread
import copy
import sys

from Tribler.CacheDB.CacheDBHandler import PeerDBHandler
from Tribler.Overlay.permid import show_permid
from BitTornado.BT1.MessageID import CANCEL, getMessageName

try:
    True
except:
    True = 1
    False = 0

DEBUG = True

Length_of_permid = 0    # 0: no restriction

def validIP(ip):
    invalid_ip_heads = [
        '0.',
        '127.0.0.1',
        '192.168.',
        ]
    try:
        ip = gethostbyname(ip)
        inet_aton(ip)
        for iphead in invalid_ip_heads:
            if ip.startswith(iphead):
                raise RuntimeError, "local ip address behind NAT"
    except:
        if DEBUG:
            print >> sys.stderr,"invalid ip", ip
        return False
    return True

def validPermid(permid):
    if not isinstance(permid, str):
        return False
    if Length_of_permid:
        return len(permid) == Length_of_permid
    return True
    
def validDNS(dns):
    if isinstance(dns, tuple) and len(dns)==2 and \
       isinstance(dns[0], str) and isinstance(dns[1], int) and \
       dns[1] > 0 and dns[1] < 65535 and validIP(dns[0]):
           return True
    return False

class OverlayTask:
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
        
    def hasExpired(self):
        return time() > self.expire
        
    def register(self, dns):    # register a subject
        if not dns:
            return
        self.subject = self.subject_manager.getSubject(dns)    
        self.subject.attachObserver(self)

    def unregister(self):
        if self.subject:
            self.subject.detachObserver(self)
            
    def setCallback(self, callback):    # it must be set before start
        self.callback = callback
        
    def start(self):    # phase 1: find or make overlay connection
        if self.hasExpired():
            return
        elif self.findConnection():
            self.sendMessage()    # if connection exists, send message now
        else:
            self.register(self.dns)
            self.makeConnection()
                
    def update(self):    # phase 2: overlay connection has been made; send msg now
        if DEBUG:
            print >> sys.stderr,"secover: task update", self.dns, self
        if self.hasExpired():
            return
        if self.callback:    # used by other task
            self.callback()
        else:
            self.sendMessage()    # TODO: fault recover
        self.unregister()
        
    def sendMessage(self):
        if self.message_to_send != None:
            if not self.permid:
                self.permid = self.secure_overlay.findPermidByDNS(self.dns)
            self.secure_overlay.sendMessage(self.permid, self.message_to_send)
            self.message_to_send = None        
        
    def makeConnection(self):
        self.secure_overlay.connectPeer(self.dns)
        
    def findConnection(self):
        # if connection is created, secure overlay must have the permid
        self.permid = self.secure_overlay.findPermidByDNS(self.dns)
        return self.permid


class PermidOverlayTask:
    """ 
    A task to connect peer's overlay swarm by permid and send message.
    It delegates OverlayTask to do the real stuffs.
    """
    
    def __init__(self, secure_overlay, subject_manager, permid, message=None, timeout=15):
        self.secure_overlay = secure_overlay
        self.permid = permid
        self.dns = self.secure_overlay.findDNSByPermid(self.permid)    # first lookup overlay
        self.peer_db = PeerDBHandler()
        if not self.dns:    # then lookup local cache
            #if DEBUG:
            #    print >> sys.stderr,"secover: PermidOverlayTask: don't know dns for permid",show_permid(permid)
            self.dns = self.findDNSFromCache()
        else:
            #if DEBUG:
            #    print >> sys.stderr,"secover: PermidOverlayTask: dns for permid is known",self.dns
            pass
        if validDNS(self.dns):
            self.task = OverlayTask(secure_overlay, subject_manager, self.dns, message, timeout)
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
            self.task.start()
                
    def update(self):    # phase 2: check permids, and send msg if they match
        if self.dns:
            permid = self.secure_overlay.findPermidByDNS(self.dns)

            #if DEBUG:
            #    print >> sys.stderr,"secover: Think connecting to",show_permid(self.permid)," and connected to",show_permid(permid)

            if self.permid == permid and self.task:
                self.task.sendMessage()
            elif DEBUG and self.permid != permid:
                print >> sys.stderr,"secover: Connection established but permid's do not match!"
                        
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
        
    def detachObserver(self, observer):
        #if DEBUG:
        #    print >> sys.stderr,"secover: subject", self.dns, "detaches observer", observer
        self.observers.remove(observer)
        if self.isEmpty():
            self.subject_manager.unregisterSubject(self.dns)
        
        
class SubjectManager:
    """ Command Pattern. Used for sending overlay message. """
    
    def __init__(self):
        self.subjects = {}    # (ip,port): Subject
    
    def registerSubject(self, dns):
        #if DEBUG:
        #    print >> sys.stderr,"secover: register subject", dns
        if not self.subjects.has_key(dns):
            self.subjects[dns] = Subject(dns, self)
                
    def unregisterSubject(self, dns):
        #if DEBUG:
        #    print >> sys.stderr,"secover: unregister subject", dns
        if self.subjects[dns].isEmpty():
            self.subjects.pop(dns)
    
    def getSubject(self, dns):
        self.registerSubject(dns)    # ensure the subject exists
        return self.subjects[dns]        
            
    def notifySubject(self, dns):    # notify the connection is made
        #if DEBUG:
        #    print >> sys.stderr,"secover: notify subject", dns
        if dns and self.subjects.has_key(dns):
            subject = self.subjects[dns]
            subject.notify()


class IncomingMessageHandler:
    """ a variant of Chain of Responsibility Pattern """
    
    def __init__(self):
        self.handlers = {}
        
    def registerHandler(self, ids, handler):
        for id in ids:
            if DEBUG:
                print >> sys.stderr,"secover: Handler registered for",getMessageName(id)
            self.handlers[id] = handler
        
    def handleMessage(self, permid, message):    # connection is type of Conneter.Connection 
        id = message[0]
        handled = False
        if not self.handlers.has_key(id):
            if DEBUG:
                print >> sys.stderr,"secover: No handler found for",getMessageName(id)
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
        self.connection_list = {}    # permid:{'c_conn': Connecter.Connection, 'e_conn': Encrypter.Connection, 'dns':(ip, port)}
        self.timeout = 60
        self.check_interval = 15
        self.lock = RLock()
                            
    def getInstance(*args, **kw):
        if SecureOverlay.__single is None:
            SecureOverlay(*args, **kw)
        return SecureOverlay.__single
    getInstance = staticmethod(getInstance)
    
    def register(self,overlayswarm):
        self.overlayswarm = overlayswarm
        self.overlayswarm.rawserver.add_task(self._auto_close, self.check_interval)

    def registerHandler(self, ids, handler):    
        """ ids is the [ID1, ID2, ..] where IDn is a sort of message ID in overlay swarm. """
        # I assume that all handler registration is done before hand, so no
        # concurrency on incoming_handler
        self.incoming_handler.registerHandler(ids, handler)

    def _auto_close(self):
        self.acquire()
        self.overlayswarm.rawserver.add_task(self._auto_close, self.check_interval)
        self._checkConnections()
        self.release()    

    def _checkConnections(self):
        connections = copy.copy(self.connection_list)
        for permid in connections:
            self._checkConnection(permid)

    def _checkConnection(self, permid):
        conn = self.connection_list[permid]['c_conn']
        expire = self.connection_list[permid]['expire']
        expired = time() > expire
        if not conn or conn.closed or expired:
            #self._closeConnection(permid) # don't work due to recursion prob
            if expired:
                if DEBUG:
                    print >> sys.stderr,"secover: closing expired connection to",show_permid(permid)
                conn.close()
            try:
                if DEBUG:
                    print >> sys.stderr,"secover: removing connection to",show_permid(permid)
                self.connection_list.pop(permid)
            except:
                pass
            ret = None
        else:
            ret = conn
        return ret
        
    def _closeConnection(self, permid):
        self.acquire()
        connection = self._findConnByPermid(permid)
        if connection:
            connection.close()
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
            if validPermid(target):
                if DEBUG:
                    if message is None:
                        msg = 'None'
                    else:
                        msg = getMessageName(message[0])
                    msg += ' '+currentThread().getName()
                    print >> sys.stderr,"secover: add PermidOverlayTask", msg
                task = PermidOverlayTask(self, self.subject_manager, target, message, timeout)
            elif validDNS(target):
                if DEBUG:
                    if message is None:
                        msg = 'None'
                    else:
                        msg = getMessageName(message[0])
                    msg += ' '+currentThread().getName()
                    print >> sys.stderr,"secover: add OverlayTask", msg
                task = OverlayTask(self, self.subject_manager, target, message, timeout)
            else:
                self.release() 
                return
            if task and self.overlayswarm.registered:
                ## Arno: I don't see the need for letting the rawserver do it.
                ## Except that it potentially avoids a concurrency problem of
                ## multiple threads writing to the same socket.
                #if DEBUG:
                #    print >> sys.stderr,"secover: addTask, adding task to rawserver",currentThread().getName()
                self.overlayswarm.rawserver.add_task(task.start, 0)
                ##task.start()
        except Exception,e:
            print_exc()

        self.release()        

    def connectionMade(self, connection):    # OverlayConnecter.Connection
        self.acquire()
        if DEBUG:
            print >> sys.stderr,"secover: ***** secure overlay connection made *****", connection.get_ip()
        #TODO: schedule it on rawserver task queue?
        dns = self._addConnection(connection)
        if dns:
            self.subject_manager.notifySubject(dns)
        self.release()    

    def _addConnection(self, connection):
        dns = connection.dns
        permid = connection.permid
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

        if validPermid(permid) and validDNS(dns):
            if self.connection_list.has_key(permid):
                # Conccurency: When a peer starts an overlay connection at
                # the same time, and we start it before the C/R protocol
                # has finished, we'll end up with two connections. In that
                # case we drop the last one established.
                if DEBUG:
                    print >> sys.stderr,"secover: dropping superfluous double connection to",show_permid(permid)
                connection.close()
                # Don't stop
                return dns

            self._updateDNS(permid, dns)
            expire = int(time() + self.timeout)
            self.connection_list[permid] = {'c_conn':connection, 'dns':dns, 'expire':expire}
            #print >> sys.stderr,"secover: permid received is",show_permid(permid)
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
        permid = connection.permid
        self.acquire()
        if DEBUG:
            print >> sys.stderr,"secover: ***** secure overlay connection lost *****", connection.get_ip()
        if self.connection_list.has_key(permid):
            if DEBUG:
                print >> sys.stderr,"secover: removing lost connection from admin"
            dns = self.connection_list[permid]['dns']
            del self.connection_list[permid]
            # TODO: remove subject?
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
            self._extendExpire(permid)
            self.overlayswarm.sendMessage(connection, message)
        self.release()

    def gotMessage(self, permid, message):    # connection is type of Connecter.Connection 
        self.acquire()        
        t = message[0]
        if t == CANCEL:    # the only message handled by secure overlay
            self._closeConnection(permid)
        elif self.incoming_handler.handleMessage(permid, message) == False:
            self._closeConnection(permid)
        else:
            self._extendExpire(permid)
        self.release()

    def acquire(self):
        #if DEBUG:
        #    print >> sys.stderr,"secover: LOCK",currentThread().getName()
        self.lock.acquire()
        
    def release(self):
        #if DEBUG:
        #    print >> sys.stderr,"secover: UNLOCK",currentThread().getName()
        self.lock.release()



def test():            
    so = SecureOverlay.getInstance()
    so.overlayswarm.secure_overlay = so
    dns = ('4.3.2.1', 1111)
    permid = 'permid1'
    so.addTask(permid)
    so.addTask(dns, message="hello overlay")

