from __future__ import absolute_import, division

import math

from ipv8.dht.routing import distance, id_to_binary_string
from ipv8.taskmanager import TaskManager

import libtorrent as lt

from twisted.internet import reactor
from twisted.internet.defer import Deferred

from Tribler.Core.Utilities.unicode import hexlify


class DHTHealthManager(TaskManager):
    """
    This class manages BEP33 health requests to the libtorrent DHT.
    """

    def __init__(self, lt_session):
        """
        Initialize the DHT health manager.
        :param lt_session: The session used to perform health lookups.
        """
        TaskManager.__init__(self)
        self.lookup_deferreds = {}  # Map from binary infohash to deferred
        self.bf_seeders = {}        # Map from infohash to (final) seeders bloomfilter
        self.bf_peers = {}          # Map from infohash to (final) peers bloomfilter
        self.lt_session = lt_session

    def get_health(self, infohash, timeout=15):
        """
        Lookup the health of a given infohash.
        :param infohash: The 20-byte infohash to lookup.
        :param timeout: The timeout of the lookup.
        :return: A Deferred that fires with a tuple, indicating the number of seeders and peers respectively.
        """
        if infohash in self.lookup_deferreds:
            return self.lookup_deferreds[infohash]

        lookup_deferred = Deferred()
        self.lookup_deferreds[infohash] = lookup_deferred
        self.bf_seeders[infohash] = bytearray(256)
        self.bf_peers[infohash] = bytearray(256)

        # Perform a get_peers request. This should result in get_peers responses with the BEP33 bloom filters.
        self.lt_session.dht_get_peers(lt.sha1_hash(bytes(infohash)))

        self.register_task("lookup_%s" % hexlify(infohash), reactor.callLater(timeout, self.finalize_lookup, infohash))

        return lookup_deferred

    def finalize_lookup(self, infohash):
        """
        Finalize the lookup of the provided infohash and invoke the appropriate deferred.
        :param infohash: The infohash of the lookup we finialize.
        """
        if infohash not in self.lookup_deferreds:
            return

        # Determine the seeders/peers
        bf_seeders = self.bf_seeders.pop(infohash)
        bf_peers = self.bf_peers.pop(infohash)
        seeders = DHTHealthManager.get_size_from_bloomfilter(bf_seeders)
        peers = DHTHealthManager.get_size_from_bloomfilter(bf_peers)
        self.lookup_deferreds[infohash].callback({
            "DHT": [{
                "infohash": hexlify(infohash),
                "seeders": seeders,
                "leechers": peers
            }]
        })

        self.lookup_deferreds.pop(infohash, None)

    @staticmethod
    def combine_bloomfilters(bf1, bf2):
        """
        Combine two given bloom filters by ORing the bits.
        :param bf1: The first bloom filter to combine.
        :param bf2: The second bloom filter to combine.
        :return: A bytearray with the combined bloomfilter.
        """
        final_bf_len = min(len(bf1), len(bf2))
        final_bf = bytearray(final_bf_len)
        for bf_index in range(final_bf_len):
            final_bf[bf_index] = bf1[bf_index] | bf2[bf_index]
        return final_bf

    @staticmethod
    def get_size_from_bloomfilter(bf):
        """
        Return the estimated number of items in the bloom filter.
        :param bf: The bloom filter of which we estimate the size.
        :return: A rounded integer, approximating the number of items in the filter.
        """
        def tobits(s):
            result = []
            for c in s:
                num = ord(c) if isinstance(c, str) else c
                bits = bin(num)[2:]
                bits = '00000000'[len(bits):] + bits
                result.extend([int(b) for b in bits])
            return result

        bits_array = tobits(bytes(bf))
        total_zeros = 0
        for bit in bits_array:
            if bit == 0:
                total_zeros += 1

        if total_zeros == 0:
            return 6000  # The maximum capacity of the bloom filter used in BEP33

        m = 256 * 8
        c = min(m - 1, total_zeros)
        return int(math.log(c / float(m)) / (2 * math.log(1 - 1 / float(m))))

    def received_bloomfilters(self, node_id, bf_seeds=bytearray(256), bf_peers=bytearray(256)):
        """
        We have received bloom filters from the libtorrent DHT. Register the bloom filters and process them.
        :param node_id: The ID of the node that sent the bloom filter.
        :param bf_seeds: The bloom filter indicating the IP addresses of the seeders.
        :param bf_peers: The bloom filter indicating the IP addresses of the peers (leechers).
        """
        min_distance = -1
        closest_infohash = None

        # We do not know to which infohash the received get_peers response belongs so we have to manually go through
        # the infohashes and find the infohash that is the closest to the node id that sent us the message.
        for infohash in self.lookup_deferreds:
            infohash_bin = id_to_binary_string(infohash)
            node_id_bin = id_to_binary_string(node_id)
            ih_distance = distance(infohash_bin, node_id_bin)
            if ih_distance < min_distance or min_distance == -1:
                min_distance = ih_distance
                closest_infohash = infohash

        if not closest_infohash:
            self._logger.info("Could not find lookup infohash for incoming BEP33 bloomfilters")
            return

        self.bf_seeders[closest_infohash] = DHTHealthManager.combine_bloomfilters(
            self.bf_seeders[closest_infohash], bf_seeds)
        self.bf_peers[closest_infohash] = DHTHealthManager.combine_bloomfilters(
            self.bf_peers[closest_infohash], bf_peers)
