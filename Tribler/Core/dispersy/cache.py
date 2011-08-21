class CacheDict(object):
    """
    A poke based cache dictionary.

    Every time an entry is retrieved using self[key] the associated key is poked and an internal
    poke counter is incremented by one.  This counter represents how important this key is, and
    hence a high counter makes it less likely for this key to be removed from the cache.

    Periodially the self.cleanup() method must be called.  The cleanup will reduce the poke counter
    for every key by value V, where V is determined by the number of pokes performed since the last
    cleanup.

    When max_caches is reached, the poke counters that reach zero or less are removed first (without
    any defined order), if we need to remove more items the items with the least pokes are removed
    first.

    TODO: it can be unfair to recently created caches, we can add a 'grace' counter that ensures
    that a cache is not eligable for cleanup until it has received at least 'grace' pokes.
    """
    def __init__(self, initial_poke_count=16, max_caches=256):
        assert isinstance(initial_poke_count, int)
        assert initial_poke_count > 0
        assert isinstance(max_caches, int)
        assert max_caches > 0
        self._initial_poke_count = initial_poke_count
        self._max_caches = max_caches
        self._pokes = 0
        self._dict = dict()

    def __len__(self):
        return self._dict.__len__()

    def __getitem__(self, key):
        cache = self._dict.__getitem__(key)
        cache.__poke_count += 1
        self._pokes += 1
        return cache

    def __setitem__(self, key, value):
        assert isinstance(value, object)
        value.__poke_count = self._initial_poke_count
        return self._dict.__setitem__(key, value)

    def __delitem__(self, key):
        return self._dict.__delitem__(key)

    def __contains__(self, key):
        return self._dict.__contains__(key)

    def get(self, key, value=None):
        cache = self._dict.get(key)
        if cache:
            cache.__poke_count += 1
            self._pokes += 1
            return cache
        else:
            return value

    def cleanup(self):
        """
        Yields a list of (key, Cache) tuples that are eligable for cleanup.
        """
        size = len(self._dict)
        delta = self._pokes / size
        self._pokes -= delta * size
        if delta:
            def peek(cache):
                cache.__poke_count -= delta
                return cache.__poke_count
            map(peek, self._dict.itervalues)

        if size > self._max_caches:
            cleanup_counter = size - self._max_caches
            caches = [(cache.__poke_count, key, cache) for key, cache in self._dict.iteritems()]

            # yield all caches that have expired (regardless of ordering)
            for poke_count, key, cache in caches:
                if poke_count <= 0:
                    self._dict.__delitem__(key)
                    yield key, cache

                    cleanup_counter -= 1
                    if cleanup_counter == 0:
                        return

            # yield all caches that have not yet expired (based on poke ordering)
            caches = [(key, cache) for poke_count, key, cache in caches if poke_count > 0]
            for key, cache in sorted(caches):
                    self._dict.__delitem__(key)
                    yield key, cache

                    cleanup_counter -= 1
                    if cleanup_counter == 0:
                        return

    def __str__(self):
        return "\n".join("%d -> %s" % (cache.__poke_count, key) for key, cache in self._dict.iteritems())

if __debug__:
    if __name__ == "__main__":
        class Cache(object):
            def __init__(self, value):
                self.value = value
        c = CacheDict(10, 2)
        c["foo"] = foo = Cache("foo")
        c["bar"] = bar = Cache("bar")
        l = list(c.cleanup())
        assert l == [], l

        c["moo"] = moo = Cache("moo")
        c["foo"]
        print c
        l = list(c.cleanup())
        assert l == [("bar", bar)], l
        print
        print c
