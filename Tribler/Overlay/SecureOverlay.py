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
from overlayswarm import OverlaySwarm
from Tribler.CacheDB.CacheDBHandler import PeerDBHandler
from socket import inet_aton

DEBUG = True
Length_of_permid = 0    # 0: no restriction

def validIP(ip):
    try:
        inet_aton(ip)
    except:
        print "invalid ip", ip
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
            self.sendMessage()
        else:
            self.register(self.dns)
            self.makeConnection()
                
    def update(self):    # phase 2: overlay connection has been made; send msg now
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
        if not self.dns:    # then lookup local cache
            self.dns = self.findDNSFromCache()
        if validDNS(self.dns):
            self.task = OverlayTask(secure_overlay, subject_manager, self.dns, message, timeout)
        else:
            self.task = None
        
    def findDNSFromCache(self):
        if DEBUG:
            return ('1.2.3.4', 80)
        peer_cache = PeerDBHandler.getInstance()
        peer = peer_cache.getPeer(self.permid)
        if peer:
            return (peer['ip'], int(peer['port']))
        
    def start(self):    # phase 1: start basic overlay task
        if self.task:
            self.task.setCallback(self.update)
            self.task.start()
                
    def update(self):    # phase 2: check permids, and send msg if they match
        if self.dns:
            permid = self.secure_overlay.findPermidByDNS(self.dns)
            if self.permid == permid and self.task:
                self.task.sendMessage()
                        
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
            observer.update()
            
    def attachObserver(self, observer):
        if observer not in self.observers:
            self.observers.append(observer)
        
    def detachObserver(self, observer):
        self.observers.remove(observer)
        if self.isEmpty():
            self.subject_manager.unregisterSubject(self.dns)
        
        
class SubjectManager:
    """ Command Pattern. Used for sending overlay message. """
    
    def __init__(self):
        self.subjects = {}    # (ip,port): Subject
    
    def registerSubject(self, dns):
        if DEBUG:
            print "register subject", dns
        if not self.subjects.has_key(dns):
            self.subjects[dns] = Subject(dns, self)
                
    def unregisterSubject(self, dns):
        if DEBUG:
            print "unregister subject", dns
        if self.subjects[dns].isEmpty():
            self.subjects.pop(dns)
    
    def getSubject(self, dns):
        self.registerSubject(dns)    # ensure the subject exists
        return self.subjects[dns]        
            
    def notifySubject(self, dns):    # notify the connection is made
        print "notify subject", dns
        if self.subjects.has_key(dns):
            subject = self.subjects[dns]
            subject.notify()


class IncomingMessageHandler:
    """ a variant of Chain of Responsibility Pattern """
    
    def __init__(self):
        self.handlers = {}
        
    def registerHandler(self, ids, handler):
        self.handlers[ids] = handler
        
    def handleMessage(self, permid, message):    # connection is type of Conneter.Connection 
        t = message[0]
        handled = False
        for ids in self.handlers.keys():
            if t in ids:
                self.handler[ids].handleMessage(permid, message)
                handled = True
        return handled


class SecureOverlay:
    __single = None

    def __init__(self):
        if SecureOverlay.__single:
            raise RuntimeError, "SecureOverlay is Singleton"
        SecureOverlay.__single = self 
        self.overlayswarm = OverlaySwarm.getInstance()
        self.subject_manager = SubjectManager()    #???? for outgoing message
        self.incoming_handler = IncomingMessageHandler()    # for incoming message
        self.connection_list = {}    # permid:{'c_conn': Connecter.Connection, 'e_conn': Encrypter.Connection, 'dns':(ip, port)}
        self.timeout = 60
        self.check_interval = 15
        #self.add_rawserver_task = self.overlayswarm.rawserver.add_task
        #self.add_rawserver_task(self._autoCheckConnections, self.check_interval)
                            
    def getInstance(*args, **kw):
        if SecureOverlay.__single is None:
            SecureOverlay(*args, **kw)
        return SecureOverlay.__single
    getInstance = staticmethod(getInstance)
    
    def registerHandler(self, ids, handler):    
        """ ids is the [ID1, ID2, ..] where IDn is a sort of message ID in overlay swarm. """
        
        self.incoming_handler.registerHandler(ids, handler)

    def _autoCheckConnections(self):
        self.add_rawserver_task(self._autoCheckConnections, self.check_interval)
        self._checkConnections()
    
    def _checkConnections(self):
        for permid in self.connections:
            self._checkConnection(permid)
        
    def _checkConnection(self, permid):
        conn = self.connection_list[permid]['c_conn']
        expire = self.connection_list[permid]['expire']
        if not conn or conn.closed or time() > expire:
            self._closeConnection(permid)
            return None
        return conn
        
    def _closeConnection(self, permid):
        connection = self._findConnByPermid(permid)
        if connection:
            connection.close()
            self.connection_list.pop(permid)
        
    def _findConnByPermid(self, permid):
        if self.connection_list.has_key(permid):
            return self._checkConnection(permid)
        
    def findPermidByDNS(self, dns):    #find permid from connection_list
        for permid, value in self.connection_list.items():
            if value['dns'] == dns and self._checkConnection(permid):
                return permid
            
    def findDNSByPermid(self, permid):
        if self._findConnByPermid(permid):
            return self.connection_list[permid]['dns']
        
    def addTask(self, target, message=None, timeout=15):    # id = [permid|(ip,port)]
        """ Command Pattern """
        #TODO: priority task queue
        
        if validPermid(target):
            if DEBUG:
                print "add PermidOverlayTask", target, message
            task = PermidOverlayTask(self, self.subject_manager, target, message, timeout)
        elif validDNS(target):
            if DEBUG:
                print "add OverlayTask", target, message
            task = OverlayTask(self, self.subject_manager, target, message, timeout)
        else: return
        task.start()
        
    def connectionMade(self, connection):    # Connecter.Connection
        #TODO: schedule it on rawserver task queue?
        dns = self._addConnection(connection)
        self.subject_manager.notifySubject(dns)

    def _addConnection(self, connection):
        dns = connection.dns
        permid = connection.permid
        if validPermid(permid) and validDNS(dns):
            self._updateDNS(permid, dns)
            expire = int(time() + self.timeout)
            self.connection_list[permid] = {'c_conn':connection, 'dns':dns, 'expire':expire}
        return dns
        
    def _updateDNS(self, permid, dns):
        pass    # TODO: use bsddb
        
    def _extendExpire(self, permid):
        self.connection_list[permid]['expire'] = int(time() + self.timeout)
        
    def connectPeer(self, dns):    # called by task
        self.overlayswarm.connectPeer(dns)
            
    def sendMessage(self, permid, message):    
        if not permid:
            return
        connection = self._findConnByPermid(permid)
        self._extendExpire(permid)
        self.overlayswarm.sendMessage(connection, message)

    def gotMessage(self, permid, message):    # connection is type of Conneter.Connection 
        t = message[0]
        if t == CANCEL:    # the only message handled by secure overlay
            self._closeConnection(permid)
        elif self.incoming_msg_handler.handleMessage(permid, message) == False:
            self._closeConnection(permid)
        else:
            self._extendExpire(permid)


def test():            
    so = SecureOverlay.getInstance()
    so.overlayswarm.secure_overlay = so
    dns = ('4.3.2.1', 1111)
    permid = 'permid1'
    so.addTask(permid)
    so.addTask(dns, message="hello overlay")

