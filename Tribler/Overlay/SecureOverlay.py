""" The middle layer between OverlaySwarm and BuddyCast/DownloadHelp """

from overlayswarm import OverlaySwarm
from time import time


class OverlayTaskP:
    """ 
    A task to connect peer's overlay swarm by permid and send message.
    It is an observer class in Observer Pattern.
    """
    
    def __init__(self, subject_manager, permid=None, dns=None, message=None, timeout=15):
        if permid and dns:
            raise RuntimeError, "Error: both permid and dns are provided"
        if not permid and not dns:
            raise RuntimeError, "Error: neither permid nor dns is provided"
        self.subject_manager = subject_manager
        self.permid = permid
        self.dns = dns
        self.message_to_send = message
        self.secure_overlay = SecureOverlay.getInstance()
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
            
    def start(self):    # phase 1: find or make overlay connection
        if self.hasExpired():
            return
        elif self.findConnection():
            self.sendMessage()
        else:
            self.makeConnection()
            self.register(self.dns)
                
    def update(self):    # phase 2: overlay connection has been made; send msg now
        if not self.hasExpired():
            self.sendMessage()    # TODO: fault recover
        self.unregister()
        
    def sendMessage(self):
        if not self.permid and self.dns:
            self.permid = self.secure_overlay.findPermidByDNS(self.dns)
        if self.message_to_send != None:
            self.secure_overlay.sendMessage(self.permid, self.message_to_send)
            self.message_to_send = None        
        
    def makeConnection(self):
        if self.permid and not self.dns:
            self.dns = self.getDNS(self.permid)
        if self.dns:
            self.secure_overlay.connectPeer(dns)
        
    def getDNS(self, permid):
        pass    #TODO: read bsddb
        
    def findConnection(self):
        if self.permid:
            if self.secure_overlay.findConnByPermid(permid)
            if conn and not conn.closed:
                self.connection = conn
                self.next_func = self.sendMessage
                    

class OverlayTaskD:
    """ 
    A task to connect peer's overlay swarm by (ip, port) and send message.
    It is an observer class in Observer Pattern.
    """
    
    def __init__(self, subject_manager, permid=None, dns=None, message=None, timeout=15):
        if permid and dns:
            raise RuntimeError, "Error: both permid and dns are provided"
        if not permid and not dns:
            raise RuntimeError, "Error: neither permid nor dns is provided"
        self.subject_manager = subject_manager
        self.permid = permid
        self.dns = dns
        self.message_to_send = message
        self.secure_overlay = SecureOverlay.getInstance()
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
            
    def start(self):    # phase 1: find or make overlay connection
        if self.hasExpired():
            return
        elif self.findConnection():
            self.sendMessage()
        else:
            self.makeConnection()
            self.register(self.dns)
                
    def update(self):    # phase 2: overlay connection has been made; send msg now
        if not self.hasExpired():
            self.sendMessage()    # TODO: fault recover
        self.unregister()
        
    def sendMessage(self):
        if not self.permid and self.dns:
            self.permid = self.secure_overlay.findPermidByDNS(self.dns)
        if self.message_to_send != None:
            self.secure_overlay.sendMessage(self.permid, self.message_to_send)
            self.message_to_send = None        
        
    def makeConnection(self):
        if self.permid and not self.dns:
            self.dns = self.getDNS(self.permid)
        if self.dns:
            self.secure_overlay.connectPeer(dns)
        
    def getDNS(self, permid):
        pass    #TODO: read bsddb
        
    def findConnection(self):
        if self.permid:
            if self.secure_overlay.findConnByPermid(permid)
            if conn and not conn.closed:
                self.connection = conn
                self.next_func = self.sendMessage
                    




                         
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
        if not self.subjects.has_key(dns):
            self.subjects[dns] = Subject(dns, self)
                
    def unregisterSubject(self, dns):
        if self.subjects[dns].isEmpty():
            self.subjects.pop(dns)
    
    def getSubject(self, dns):
        self.registerSubject(dns)    # ensure the subject exists
        return self.subject[dns]        
            
    def notifySubject(self, dns):    # notify the connection is made
        if self.subjects.has_key(dns):
            subject = self.subjects[dns]
            subject.notify()


class IncomingMessageHandler:
    
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
        self.add_rawserver_task = self.overlayswarm.rawserver.add_task
        self.subject_manager = SubjectManager()    #???? for outgoing message
        self.incoming_handler = IncomingMessageHandler()    # for incoming message
        self.connection_list = {}    # permid:{'c_conn': Connecter.Connection, 'e_conn': Encrypter.Connection, 'dns':(ip, port)}
        self.timeout = 60
        self.check_interval = 15
        self.add_rawserver_task(self._autoCheckConnections, self.check_interval)
                            
    def getInstance(*args, **kw):
        if SecureOverlay.__single is None:
            SecureOverlay(*args, **kw)
        return SecureOverlay.__single
    getInstance = staticmethod(getInstance)
    
    def registerHandler(self, ids, handler):    
        """ ids is the [ID1, ID2, ..] where IDn is a sort of message ID in overlay swarm. """
        
        self.incoming_handler.registerHandler(ids, handler)

    def gotMessage(self, permid, message):    # connection is type of Conneter.Connection 
        if self.incoming_msg_handler.handleMessage(permid, message) == False:
            connection = self.findConnByPermid(permid)
            self._closeConnection(connection)
            
    def _autoCheckConnections(self):
        self.add_rawserver_task(self._autoCheckConnections, self.check_interval)
        self._checkConnections()
    
    def _checkConnections(self):
        for permid in self.connections:
            self._checkConnection(permid)
        
    def _checkConnection(self, permid):
        conn = self.connection_list[permid]['c_conn']
        expire = self.connection_list[permid]['expire']
        if not conn or conn.closed or time() > expire():
            self.connection_list.pop(permid)
            return None
        return conn
        
    def _closeConnection(self):
        pass
        
    def findConnByPermid(self, permid):
        if self.connection_list.has_key(permid):
            return self._checkConnection(permid)
        
    def findPermidByDNS(self, dns):    #find permid from connection_list
        for permid, value in self.connection_list.items():
            if value['dns'] == dns and self._checkConnection(permid):
                    return permid
        
    def addTask(self, permid=None, dns=None, message=None, timeout=15):
        task = OverlayTask(self.subject_manager, permid, dns, message, timeout)
        task.start()    # TODO: priority task queue
        
    def connectionMade(self, connection):    # Connecter.Connection
        self._addConnection(connection)
        self.subject_manager.notifySubject()

    def _addConnection(self, connection):
        dns = connection.dns
        permid = connection.permid
        self._updateDNS(permid, dns)
        enc_conn = connection.connection    # Encrypter.Connection
        expire = int(time() + self.timeout)
        self.connection_list[permid] = {'c_conn':connection, 'dns':dns, 
                                        'e_conn':enc_conn, 'expire':expire}
        
    def _updateDNS(self, permid, dns):
        pass    # TODO: use bsddb
        
    def connectPeer(self, dns):
        self.overlayswarm.connectPeer(dns)
            
    def _extendExpire(self, permid):
        self.connection_list[permid]['expire'] = int(time() + self.timeout)
        
    def sendMessage(self, permid):    # forbid sending msg using connection as parameter
        if not permid:
            return
        self._extendExpire(permid)
        pass