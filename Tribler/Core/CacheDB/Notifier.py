# Written by Jelle Roozenburg 
# see LICENSE.txt for license information

import threading
import Queue
import thread

from Tribler.Core.simpledefs import *

class Notifier:
    
    SUBJECTS = [NTFY_PEERS, NTFY_TORRENTS, NTFY_YOUTUBE, NTFY_PREFERENCES, NTFY_DOWNLOADS, NTFY_ACTIVITIES, NTFY_REACHABLE]

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
    
    def add_observer(self, func, subject, changeTypes = [NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE], id = None):
        """
        Add observer function which will be called upon certain event
        Example: 
        addObserver(NTFY_PEERS, [NTFY_INSERT,NTFY_DELETE]) -> get callbacks 
                    when peers are added or deleted
        addObserver(NTFY_PEERS, [NTFY_SEARCH_RESULT], 'a_search_id') -> get 
                    callbacks when peer-searchresults of of search
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

