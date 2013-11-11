import sys
import os
import json
import thread
import cPickle

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

    def __init__(self, config=None):
        assert self._singleton is None
        self._config = None
        self._choices = {"download_state": {}}

        if config:
            self.set_config(config)

    def set_config(self, config, state_dir):
        self._config = config

        self._choices = {}

        try:
            self._choices = json.loads(config.Read("user_download_choice"))
        except:
            oldcfgfilename = os.path.join(state_dir, 'user_download_choice.pickle')
            if os.path.exists(oldcfgfilename):
                self._choices = cPickle.Unpickler(open(oldcfgfilename, "r")).load()
                self.flush()
                self._config.Flush()
                os.remove(oldcfgfilename)

        # Ensure that there is a "download_state" dictionary. It
        # should contain infohash/state tuples.
        if not "download_state" in self._choices:
            self._choices["download_state"] = {}

    def flush(self):
        if self._config:
            if DEBUG:
                print >> sys.stderr, "UserDownloadChoice: saving to config file"
            self._config.Write("user_download_choice", json.dumps(self._choices))

    def set_download_state(self, infohash, choice, flush=True):
        infohash = infohash.encode('hex')
        self._choices["download_state"][infohash] = choice
        if flush:
            self.flush()

    def remove_download_state(self, infohash, flush=True):
        infohash = infohash.encode('hex')
        if infohash in self._choices["download_state"]:
            del self._choices["download_state"][infohash]
            if flush:
                self.flush()

    def get_download_state(self, infohash, default=None):
        infohash = infohash.encode('hex')
        return self._choices["download_state"].get(infohash, default)

    def get_download_states(self):
        return dict((k.decode('hex'), v) for k, v in self._choices["download_state"].iteritems())
