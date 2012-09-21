# Copyright (C) 2011 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

"""
This module offers the functionality to cache lookup results. Whenever
pymdht.get_peers() is called, controller has the option to return cached
results.

The obvious example is when Tribler does a lookup to gather information about
an infohash, and a few seconds later the user clicks 'download', thus calling
pymdht.get_peers() again.\
"""

import ptime as time

CACHING_NODE = ('0.0.0.0', 0)

class CachedLookup(object):

    def __init__(self, info_hash):
        self.info_hash = info_hash
        self.start_ts = time.time()
        self.peers = set()

    def add_peers(self, peers):
        for peer in peers:
            self.peers.add(peer)
    

class Cache(object):

    def __init__(self, validity_time):
        self.validity_time = validity_time
        self.cached_lookups = []

    def put_cached_lookup(self, cached_lookup):
        # first remove expired chached lookups
        for i in range(len(self.cached_lookups), 0, -1):
            if time.time() > (self.cached_lookups[i-1].start_ts +
                              self.validity_time):
                del self.cached_lookups[i-1]
        self.cached_lookups.append(cached_lookup)
        
    def get_cached_lookup(self, info_hash):
        for cached_lookup in self.cached_lookups:
            if cached_lookup.info_hash == info_hash:
                if time.time() < cached_lookup.start_ts + self.validity_time:
                    return cached_lookup.peers, CACHING_NODE
