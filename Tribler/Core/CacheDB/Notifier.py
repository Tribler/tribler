# Written by Jelle Roozenburg
# see LICENSE.txt for license information

import threading
import logging

from Tribler.Core.simpledefs import (NTFY_MISC, NTFY_PEERS, NTFY_TORRENTS, NTFY_PLAYLISTS, NTFY_COMMENTS,
                                     NTFY_MODIFICATIONS, NTFY_MODERATIONS, NTFY_MARKINGS, NTFY_MYPREFERENCES,
                                     NTFY_ACTIVITIES, NTFY_REACHABLE, NTFY_CHANNELCAST, NTFY_VOTECAST, NTFY_DISPERSY,
                                     NTFY_TRACKERINFO, NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE, NTFY_ANONTUNNEL)


class Notifier(object):

    SUBJECTS = [NTFY_MISC, NTFY_PEERS, NTFY_TORRENTS, NTFY_PLAYLISTS, NTFY_COMMENTS, NTFY_MODIFICATIONS,
                NTFY_MODERATIONS, NTFY_MARKINGS, NTFY_MYPREFERENCES, NTFY_ACTIVITIES, NTFY_REACHABLE, NTFY_CHANNELCAST,
                NTFY_VOTECAST, NTFY_DISPERSY, NTFY_TRACKERINFO, NTFY_ANONTUNNEL]

    # . . .
    # todo: add all datahandler types+other observables
    __single = None

    def __init__(self, pool=None):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.pool = pool

        self.observers = []
        self.observer_cache = {}
        self.observer_timers = {}
        self._lock = threading.Lock()

    def add_observer(self, func, subject, change_types=[NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE], sub_id=None, cache=0):
        """
        Add observer function which will be called upon certain event
        Example:
        addObserver(NTFY_PEERS, [NTFY_INSERT,NTFY_DELETE]) -> get callbacks
                    when peers are added or deleted
        addObserver(NTFY_PEERS, [NTFY_SEARCH_RESULT], 'a_search_id') -> get
                    callbacks when peer-searchresults of of search
                    with id=='a_search_id' come in
        """
        assert isinstance(change_types, list)
        assert subject in self.SUBJECTS, 'Subject %s not in SUBJECTS' % subject

        obs = (func, subject, change_types, sub_id, cache)
        with self._lock:
            self.observers.append(obs)

    def remove_observer(self, func):
        """ Remove all observers with function func
        """
        with self._lock:
            i = 0
            while i < len(self.observers):
                ofunc = self.observers[i][0]
                if ofunc == func:
                    del self.observers[i]
                else:
                    i += 1

    def remove_observers(self):
        with self._lock:
            for timer in self.observer_timers.values():
                timer.cancel()
            self.observer_cache = {}
            self.observer_timers = {}
            self.observers = []

    def notify(self, subject, change_types, obj_id, *args):
        """
        Notify all interested observers about an event with threads from the pool
        """
        tasks = []
        assert subject in self.SUBJECTS, 'Subject %s not in SUBJECTS' % subject

        args = [subject, change_types, obj_id] + list(args)

        self._lock.acquire()
        for ofunc, osubject, ochangeTypes, oid, cache in self.observers:
            try:
                if subject == osubject and change_types in ochangeTypes and (oid is None or oid == obj_id):
                    if not cache:
                        tasks.append(ofunc)
                    else:
                        if ofunc not in self.observer_cache:
                            def do_queue(func):
                                self._lock.acquire()
                                if func in self.observer_cache:
                                    events = self.observer_cache[func]
                                    del self.observer_cache[func]
                                    del self.observer_timers[func]
                                else:
                                    events = []
                                self._lock.release()

                                if events:
                                    if self.pool:
                                        self.pool.queue_task(func, (events,))
                                    else:
                                        func(events)

                            t = threading.Timer(cache, do_queue, (ofunc,))
                            t.setName("Notifier-timer-%s" % subject)
                            t.start()

                            self.observer_cache[ofunc] = []
                            self.observer_timers[ofunc] = t

                        self.observer_cache[ofunc].append(args)
            except:
                self._logger.exception("OIDs were %s %s", repr(oid), repr(obj_id))

        self._lock.release()
        for task in tasks:
            if self.pool:
                self.pool.queue_task(task, args)
            else:
                task(*args)  # call observer function in this thread
