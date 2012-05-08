from random import random

if __debug__:
    from dprint import dprint

class Cache(object):
    timeout_delay = 10.0
    cleanup_delay = 10.0

    def on_timeout(self):
        raise NotImplementedError()

    def __str__(self):
        return "<%s>" % self.__class__.__name__

class RequestCache(object):
    def __init__(self, callback):
        self._callback = callback
        self._identifiers = dict()

    def claim(self, cache):
        while True:
            identifier = int(random() * 2**16)
            if not identifier in self._identifiers:
                if __debug__: dprint("claiming on ", identifier, " for ", cache)
                break

        self.set(identifier, cache)
        return identifier

    def set(self, identifier, cache):
        assert isinstance(identifier, (int, long, str)), type(identifier)
        assert isinstance(cache, Cache)
        assert isinstance(cache.timeout_delay, float)
        assert cache.timeout_delay > 0.0

        if __debug__: dprint("set ", identifier, " for ", cache, " (", cache.timeout_delay, "s timeout)")
        self._callback.register(self._on_timeout, (identifier,), id_="requestcache-%s" % identifier, delay=cache.timeout_delay)
        self._identifiers[identifier] = cache

    def has(self, identifier, cls):
        assert isinstance(identifier, (int, long, str)), type(identifier)
        assert issubclass(cls, Cache), cls

        if __debug__: dprint("cache contains ", identifier, "? ", identifier in self._identifiers)
        return isinstance(self._identifiers.get(identifier), cls)

    def get(self, identifier, cls):
        assert isinstance(identifier, (int, long, str)), type(identifier)
        assert issubclass(cls, Cache), cls

        cache = self._identifiers.get(identifier)
        if cache and isinstance(cache, cls):
            return cache

    def pop(self, identifier, cls):
        assert isinstance(identifier, (int, long, str)), type(identifier)
        assert issubclass(cls, Cache), cls

        cache = self._identifiers.get(identifier)
        if cache and isinstance(cache, cls):
            assert isinstance(cache.cleanup_delay, float)
            assert cache.cleanup_delay >= 0.0
            if __debug__: dprint("canceling timeout on ", identifier, " for ", cache)

            if cache.cleanup_delay:
                self._callback.replace_register("requestcache-%s" % identifier, self._on_cleanup, (identifier,), delay=cache.cleanup_delay)

            else:
                self._callback.unregister("requestcache-%s" % identifier)
                del self._identifiers[identifier]

            return cache

    def _on_timeout(self, identifier):
        assert identifier in self._identifiers
        cache = self._identifiers.get(identifier)
        if __debug__: dprint("timeout on ", identifier, " for ", cache)
        cache.on_timeout()
        if cache.cleanup_delay:
            self._callback.register(self._on_cleanup, (identifier,), id_="requestcache-%s" % identifier, delay=cache.cleanup_delay)
        else:
            del self._identifiers[identifier]

    def _on_cleanup(self, identifier):
        assert identifier in self._identifiers
        if __debug__: dprint("cleanup on ", identifier, " for ", self._identifiers[identifier])
        del self._identifiers[identifier]
