# Written by Jelle Roozenburg
# see LICENSE.txt for license information

import threading

from Tribler.Core.simpledefs import NTFY_MISC, NTFY_PEERS, NTFY_TORRENTS, \
    NTFY_PLAYLISTS, NTFY_COMMENTS, NTFY_MODIFICATIONS, NTFY_MODERATIONS, \
    NTFY_MARKINGS, NTFY_MYPREFERENCES, NTFY_ACTIVITIES, NTFY_REACHABLE, \
    NTFY_CHANNELCAST, NTFY_VOTECAST, NTFY_DISPERSY, NTFY_TRACKERINFO, \
    NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE, NTFY_ANONTUNNEL

import logging

class Notifier:

    SUBJECTS = [NTFY_MISC, NTFY_PEERS, NTFY_TORRENTS, NTFY_PLAYLISTS,
        NTFY_COMMENTS, NTFY_MODIFICATIONS, NTFY_MODERATIONS, NTFY_MARKINGS,
        NTFY_MYPREFERENCES, NTFY_ACTIVITIES, NTFY_REACHABLE, NTFY_CHANNELCAST,
        NTFY_VOTECAST, NTFY_DISPERSY, NTFY_TRACKERINFO, NTFY_ANONTUNNEL]

    # . . .
    # todo: add all datahandler types+other observables
    __single = None

    def __init__(self, pool=None):
        if Notifier.__single:
            raise RuntimeError("Notifier is singleton")

        self._logger = logging.getLogger(self.__class__.__name__)

        self.pool = pool

        self.observers = []
        self.observerscache = {}
        self.observertimers = {}
        self.observerLock = threading.Lock()

        Notifier.__single = self

    def getInstance(*args, **kw):
        if Notifier.__single is None:
            Notifier(*args, **kw)
        return Notifier.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        if Notifier.__single:
            Notifier.__single.remove_observers()
        Notifier.__single = None
    delInstance = staticmethod(delInstance)

    def add_observer(self, func, subject, changeTypes=[NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE], id=None, cache=0):
        """
        Add observer function which will be called upon certain event
        Example:
        addObserver(NTFY_PEERS, [NTFY_INSERT,NTFY_DELETE]) -> get callbacks
                    when peers are added or deleted
        addObserver(NTFY_PEERS, [NTFY_SEARCH_RESULT], 'a_search_id') -> get
                    callbacks when peer-searchresults of of search
                    with id=='a_search_id' come in
        """
        assert isinstance(changeTypes, list)
        assert subject in self.SUBJECTS, 'Subject %s not in SUBJECTS' % subject

        obs = (func, subject, changeTypes, id, cache)
        self.observerLock.acquire()
        self.observers.append(obs)
        self.observerLock.release()

    def remove_observer(self, func):
        """ Remove all observers with function func
        """
        with self.observerLock:
            i = 0
            while i < len(self.observers):
                ofunc = self.observers[i][0]
                if ofunc == func:
                    del self.observers[i]
                else:
                    i += 1

    def remove_observers(self):
        with self.observerLock:
            for timer in self.observertimers.values():
                timer.cancel()
            self.observerscache = {}
            self.observertimers = {}
            self.observers = []

    def notify(self, subject, changeType, obj_id, *args):
        """
        Notify all interested observers about an event with threads from the pool
        """
        tasks = []
        assert subject in self.SUBJECTS, 'Subject %s not in SUBJECTS' % subject

        args = [subject, changeType, obj_id] + list(args)

        self.observerLock.acquire()
        for ofunc, osubject, ochangeTypes, oid, cache in self.observers:
            try:
                if (subject == osubject and
                    changeType in ochangeTypes and
                        (oid is None or oid == obj_id)):

                    if not cache:
                        tasks.append(ofunc)
                    else:
                        if ofunc not in self.observerscache:
                            def doQueue(ofunc):
                                self.observerLock.acquire()
                                if ofunc in self.observerscache:
                                    events = self.observerscache[ofunc]
                                    del self.observerscache[ofunc]
                                    del self.observertimers[ofunc]
                                else:
                                    events = []
                                self.observerLock.release()

                                if events:
                                    if self.pool:
                                        self.pool.queueTask(ofunc, (events,))
                                    else:
                                        ofunc(events)

                            t = threading.Timer(cache, doQueue, (ofunc,))
                            t.setName("Notifier-timer-%s" % subject)
                            t.start()

                            self.observerscache[ofunc] = []
                            self.observertimers[ofunc] = t

                        self.observerscache[ofunc].append(args)
            except:
                self._logger.exception("OIDs were %s %s", repr(oid), repr(obj_id))

        self.observerLock.release()
        for task in tasks:
            if self.pool:
                self.pool.queueTask(task, args)
            else:
                task(*args)  # call observer function in this thread
