import sys
import os
import cPickle
import thread

DEBUG = False


class UserDownloadChoice:
    _singleton = None
    _singleton_lock = thread.allocate_lock()

    @classmethod
    def get_singleton(cls, *args, **kargs):
        if cls._singleton is None:
            cls._singleton_lock.acquire()
            try:
                if cls._singleton is None:
                    cls._singleton = cls(*args, **kargs)
            finally:
                cls._singleton_lock.release()
        return cls._singleton

    def __init__(self, session_dir=None):
        assert self._singleton is None
        self._storage_file = None
        self._choices = {"download_state": {}}

        if not session_dir is None:
            self.set_session_dir(session_dir)

    def set_session_dir(self, session_dir):
        self._storage_file = os.path.join(session_dir, "user_download_choice.pickle")
        if DEBUG:
            print >> sys.stderr, "UserDownloadChoice: Using file:", self._storage_file

        try:
            self._choices = cPickle.Unpickler(open(self._storage_file, "r")).load()
        except:
            self._choices = {}

        # Ensure that there is a "download_state" dictionary. It
        # should contain infohash/state tuples.
        if not "download_state" in self._choices:
            self._choices["download_state"] = {}

    def flush(self):
        if not self._storage_file is None:
            if DEBUG:
                print >> sys.stderr, "UserDownloadChoice: flush to", self._storage_file
            cPickle.Pickler(open(self._storage_file, "w")).dump(self._choices)

    def set_download_state(self, infohash, choice, flush=True):
        self._choices["download_state"][infohash] = choice
        if flush:
            self.flush()

    def remove_download_state(self, infohash, flush=True):
        if infohash in self._choices["download_state"]:
            del self._choices["download_state"][infohash]
            if flush:
                self.flush()

    def get_download_state(self, infohash, default=None):
        return self._choices["download_state"].get(infohash, default)

    def get_download_states(self):
        return self._choices["download_state"]
