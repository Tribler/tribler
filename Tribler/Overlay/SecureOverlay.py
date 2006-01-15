""" The middle layer between OverlaySwarm and BuddyCast/DownloadHelp """

from overlayswarm import OverlaySwarm


class Subject:
    """ A subject class in Observer Pattern """
    
    def __init__(self, dns, task_manager):
        self.dns = dns    # dns = (ip, port)
        self.observers = []    # tasks
        self.task_manager = task_manager
        
    def isEmpty(self):
        return len(self.observers) == 0
        
    def notifyObservers(self, content):
        for observer in self.observers:
            observer.update(content)
            
    def attachObserver(self, observer):
        if observer not in self.observers:
            self.observers.append(observer)
        
    def detachObserver(self, observer):
        self.observers.remove(observer)
        if self.isEmpty():
            self.task_manager.unregisterSubject(self.dns)
        
        
class Task:
    def __init__(self, permid=None, dns=None, message=None):
        self.subject = None
        self.permid = permid
        self.dns = dns
        self.message_to_send = message
        self.secure_overlay = SecureOverlay.getInstance()

    def setSubject(self, subject):
        self.subject = subject
        
    def done(self):
        if self.subject:
            self.subject.detachObserver(self)
    
    def update(self, content):
        pass
        
        
class TaskManager:
    """ Used for sending overlay message. """
    
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
            
    def addTask(self, dns, task):
        subject = self.getSubject(dns)    
        subject.attachObserver(task)
        task.setSubject(subject)


class SecureOverlay:
    __single = None

    def __init__(self):
        if SecureOverlay.__single:
            raise RuntimeError, "SecureOverlay is Singleton"
        SecureOverlay.__single = self 
        self.overlayswarm = OverlaySwarm.getInstance()
        self.task_manager = TaskManager()
                    
    def getInstance(*args, **kw):
        if SecureOverlay.__single is None:
            SecureOverlay(*args, **kw)
        return SecureOverlay.__single
    getInstance = staticmethod(getInstance)

    