from random import random

class Cache(object):
    def __init__(self, identifier):
        self._identifier = identifier

    def __hash__(self):
        return self._identifier

    @property
    def identifier(self):
        return self._identifier

class RequestCache(object):
    def __init__(self, callback):
        self._callback_register = callback.register
        self._identifiers = set()

    def claim(self, duration, cls):
        assert isinstance(duration, float)
        assert issubclass(cls, Cache)
        while True:
            identifier = int(random() * 2**16)
            if not identifier in self._identifiers:
                cache = cls(identifier)
                self._identifiers.add(cache)
                self._callback_register(self._identifiers.remove, (cache,), delay=duration)
                return cache

