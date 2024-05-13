from __future__ import annotations

import math
from asyncio import Future
from binascii import hexlify
from typing import Awaitable

import libtorrent as lt
from ipv8.taskmanager import TaskManager

from tribler.core.torrent_checker.dataclasses import HealthInfo


class DHTHealthManager(TaskManager):
    """
    This class manages BEP33 health requests to the libtorrent DHT.
    """

    def __init__(self, lt_session: lt.session) -> None:
        """
        Initialize the DHT health manager.

        :param lt_session: The session used to perform health lookups.
        """
        TaskManager.__init__(self)
        self.lookup_futures: dict[bytes, Future[HealthInfo]] = {}  # Map from binary infohash to future
        self.bf_seeders: dict[bytes, bytearray] = {}  # Map from infohash to (final) seeders bloomfilter
        self.bf_peers: dict[bytes, bytearray] = {}  # Map from infohash to (final) peers bloomfilter
        self.outstanding: dict[str, bytes] = {}  # Map from transaction_id to infohash
        self.lt_session = lt_session

    def get_health(self, infohash: bytes, timeout: float = 15) -> Awaitable[HealthInfo]:
        """
        Lookup the health of a given infohash.

        :param infohash: The 20-byte infohash to lookup.
        :param timeout: The timeout of the lookup.
        """
        if infohash in self.lookup_futures:
            return self.lookup_futures[infohash]

        lookup_future: Future[HealthInfo] = Future()
        self.lookup_futures[infohash] = lookup_future
        self.bf_seeders[infohash] = bytearray(256)
        self.bf_peers[infohash] = bytearray(256)

        # Perform a get_peers request. This should result in get_peers responses with the BEP33 bloom filters.
        self.lt_session.dht_get_peers(lt.sha1_hash(bytes(infohash)))

        self.register_task(f"lookup_{hexlify(infohash).decode}", self.finalize_lookup, infohash, delay=timeout)

        return lookup_future

    def finalize_lookup(self, infohash: bytes) -> None:
        """
        Finalize the lookup of the provided infohash and invoke the appropriate deferred.

        :param infohash: The infohash of the lookup we finialize.
        """
        for transaction_id in [key for key, value in self.outstanding.items() if value == infohash]:
            self.outstanding.pop(transaction_id, None)

        if infohash not in self.lookup_futures:
            return

        # Determine the seeders/peers
        bf_seeders = self.bf_seeders.pop(infohash)
        bf_peers = self.bf_peers.pop(infohash)
        seeders = DHTHealthManager.get_size_from_bloomfilter(bf_seeders)
        peers = DHTHealthManager.get_size_from_bloomfilter(bf_peers)
        if not self.lookup_futures[infohash].done():
            health = HealthInfo(infohash, seeders=seeders, leechers=peers)
            self.lookup_futures[infohash].set_result(health)

        self.lookup_futures.pop(infohash, None)

    @staticmethod
    def combine_bloomfilters(bf1: bytearray, bf2: bytearray) -> bytearray:
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
    def get_size_from_bloomfilter(bf: bytearray) -> int:
        """
        Return the estimated number of items in the bloom filter.

        :param bf: The bloom filter of which we estimate the size.
        :return: A rounded integer, approximating the number of items in the filter.
        """

        def tobits(s: bytes) -> list[int]:
            result = []
            for num in s:
                bits = bin(num)[2:]
                bits = "00000000"[len(bits):] + bits
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

    def requesting_bloomfilters(self, transaction_id: str, infohash: bytes) -> None:
        """
        Tne libtorrent DHT has sent a get_peers query for an infohash we may be interested in.
        If so, keep track of the transaction and node IDs.

        :param transaction_id: The ID of the query
        :param infohash: The infohash for which the query was sent.
        """
        if infohash in self.lookup_futures:
            self.outstanding[transaction_id] = infohash
        elif transaction_id in self.outstanding:
            # Libtorrent is reusing the transaction_id, and is now using it for a infohash that we're not interested in.
            self.outstanding.pop(transaction_id, None)

    def received_bloomfilters(self, transaction_id: str, bf_seeds: bytearray = bytearray(256),  # noqa: B008
                              bf_peers: bytearray = bytearray(256)) -> None:  # noqa: B008
        """
        We have received bloom filters from the libtorrent DHT. Register the bloom filters and process them.

        :param transaction_id: The ID of the query for which we are receiving the bloom filter.
        :param bf_seeds: The bloom filter indicating the IP addresses of the seeders.
        :param bf_peers: The bloom filter indicating the IP addresses of the peers (leechers).
        """
        infohash = self.outstanding.get(transaction_id)
        if not infohash:
            self._logger.info("Could not find lookup infohash for incoming BEP33 bloomfilters")
            return

        self.bf_seeders[infohash] = DHTHealthManager.combine_bloomfilters(self.bf_seeders[infohash], bf_seeds)
        self.bf_peers[infohash] = DHTHealthManager.combine_bloomfilters(self.bf_peers[infohash], bf_peers)
