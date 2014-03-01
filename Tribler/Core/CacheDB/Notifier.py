# Written by Jelle Roozenburg
# see LICENSE.txt for license information

from threading import Lock, Timer
import logging

from Tribler.Core.simpledefs import NTFY_MISC, NTFY_PEERS, NTFY_TORRENTS, \
    NTFY_PLAYLISTS, NTFY_COMMENTS, NTFY_MODIFICATIONS, NTFY_MODERATIONS, \
    NTFY_MARKINGS, NTFY_MYPREFERENCES, NTFY_ACTIVITIES, NTFY_REACHABLE, \
    NTFY_CHANNELCAST, NTFY_VOTECAST, NTFY_PROXYDOWNLOADER, \
    NTFY_PROXYDISCOVERY, NTFY_DISPERSY, NTFY_TRACKERINFO, \
    NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE
from Tribler.Core.Misc.Singleton import Singleton

class Notifier(Singleton):

    SUBJECTS = [NTFY_MISC, NTFY_PEERS, NTFY_TORRENTS, NTFY_PLAYLISTS,
        NTFY_COMMENTS, NTFY_MODIFICATIONS, NTFY_MODERATIONS, NTFY_MARKINGS,
        NTFY_MYPREFERENCES, NTFY_ACTIVITIES, NTFY_REACHABLE, NTFY_CHANNELCAST,
        NTFY_VOTECAST, NTFY_PROXYDOWNLOADER, NTFY_PROXYDISCOVERY, NTFY_DISPERSY,
        NTFY_TRACKERINFO]

    __single = None

    def __init__(self, pool=None):
        super(Notifier, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self._pool = pool

        self._observer_list = []
        self._observers_cache = {}
        self._observer_timers = {}
        self._observer_lock = Lock()

    def finalize(self):
        """Finalizes this module.
        """
        self.remove_observers()

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
        assert isinstance(changeTypes, list), u"change_types is of type %s" % type(changeTypes)
        assert subject in Notifier.SUBJECTS, u"subject is not in SUBJECTS %s" % subject

        obs = (func, subject, changeTypes, id, cache)
        with self._observer_lock:
            self._observer_list.append(obs)

    def remove_observer(self, func):
        """ Removes an observer with function func
        """
        with self._observer_lock:
            i = 0
            while i < len(self._observer_list):
                ofunc = self._observer_list[i][0]
                if ofunc == func:
                    del self._observer_list[i]
                else:
                    i += 1

    def remove_observers(self):
        with self._observer_lock:
            for timer in self._observer_timers.values():
                timer.cancel()
            self._observers_cache = {}
            self._observer_timers = {}
            self._observer_list = []

    def notify(self, subject, changeType, obj_id, *args):
        """
        Notify all interested observers about an event with threads from the pool
        """
        tasks = []

        args = [subject, changeType, obj_id] + list(args)

        self._observer_lock.acquire()
        for ofunc, osubject, ochangeTypes, oid, cache in self._observer_list:
            try:
                if (subject == osubject and
                    changeType in ochangeTypes and
                        (oid is None or oid == obj_id)):

                    if not cache:
                        tasks.append(ofunc)
                    else:
                        if ofunc not in self._observers_cache:
                            def doQueue(ofunc):
                                self._observer_lock.acquire()
                                if ofunc in self._observers_cache:
                                    events = self._observers_cache[ofunc]
                                    del self._observers_cache[ofunc]
                                    del self._observer_timers[ofunc]
                                else:
                                    events = []
                                self._observer_lock.release()

                                if events:
                                    if self._pool:
                                        self._pool.queueTask(ofunc, (events,))
                                    else:
                                        ofunc(events)

                            t = Timer(cache, doQueue, (ofunc,))
                            t.setName("Notifier-timer-%s" % subject)
                            t.start()

                            self._observers_cache[ofunc] = []
                            self._observer_timers[ofunc] = t

                        self._observers_cache[ofunc].append(args)
            except:
                self._logger.exception(u"OIDs were %s %s", repr(oid), repr(obj_id))

        self._observer_lock.release()
        for task in tasks:
            if self._pool:
                self._pool.queueTask(task, args)
            else:
                task(*args)  # call observer function in this thread
