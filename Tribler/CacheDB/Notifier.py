import threading
import Queue
import thread

class Notifier:
    
    # subjects
    
    PEERS = 'peers'
    TORRENTS = 'torrents'
    YOUTUBE = 'youtube'
    PREFERENCES = 'preferences'
    
    # non data handler subjects
    DOWNLOADS = 'downloads'             # a torrent download was added/removed/changed
    ACTIVITIES = 'activities'           # an activity was set (peer met/dns resolved)
    
    SUBJECTS = [PEERS, TORRENTS, YOUTUBE, PREFERENCES, DOWNLOADS, ACTIVITIES]
    
    # changeTypes
    UPDATE = 'update'                   # data is updated
    INSERT = 'insert'                   # new data is inserted
    DELETE = 'delete'                   # data is deleted
    SEARCH_RESULT = 'search_result'     # new search result
    
    
    #. . .
    # todo: add all datahandler types+other observables
    __single = None
    
    def __init__(self, pool = None):
        if Notifier.__single:
            raise RuntimeError, "Notifier is singleton"
        self.pool = pool
        self.observers = []    
        self.observerLock = threading.Lock()
        Notifier.__single = self
        
    def getInstance(*args, **kw):
        if Notifier.__single is None:
            Notifier(*args, **kw)
        return Notifier.__single
    getInstance = staticmethod(getInstance)
    
    def add_observer(self, func, subject, changeTypes = [UPDATE, INSERT, DELETE], id = None):
        """
        Add observer function which will be called upon certain event
        Example: 
        addObserver(PEERS, [INSERT,DELETE]) -> get callbacks when peers are added or deleted
        addObserver(PEERS, [SEARCH_RESULT], 'a_search_id') -> get callbacks when peer-searchresults of of search
                                                              with id=='a_search_id' come in
        """
        assert type(changeTypes) == list
        assert subject in self.SUBJECTS
        
        obs = (func, subject, changeTypes, id)
        self.observerLock.acquire()
        self.observers.append(obs)
        self.observerLock.release()
        
    def remove_observer(self, func):
        """ Remove all observers with function func
        """
        
        self.observerLock.acquire()
        i=0
        while i < len(self.observers):
            ofunc = self.observers[i][0]
            if ofunc == func:
                del self.observers[i]
            else:
                i+=1
        self.observerLock.release()
        
    def notify(self, subject, changeType, obj_id, *args):
        """
        Notify all interested observers about an event with threads from the pool
        """
        tasks = []
        assert subject in self.SUBJECTS
        
        self.observerLock.acquire()
        for ofunc, osubject, ochangeTypes, oid in self.observers:
            if (subject == osubject and
                changeType in ochangeTypes and
                (oid is None or oid == obj_id)):
                tasks.append(ofunc)
        self.observerLock.release()
        args = [subject, changeType, obj_id] + list(args)
        for task in tasks:
            if self.pool:
                self.pool.queueTask(task, args)
            else:
                task(*args) # call observer function in this thread

