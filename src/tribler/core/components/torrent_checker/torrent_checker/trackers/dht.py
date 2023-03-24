import asyncio
import logging
import math
import random
import time
from asyncio import Future
from asyncio.exceptions import TimeoutError
from binascii import hexlify
from typing import List, Tuple

import libtorrent as lt
from ipv8.taskmanager import TaskManager

from tribler.core.components.torrent_checker.torrent_checker.dataclasses import TrackerResponse, UdpRequest, HealthInfo
from tribler.core.components.torrent_checker.torrent_checker.socket_manager import UdpSocketManager
from tribler.core.components.torrent_checker.torrent_checker.trackers import Tracker

MAX_NODES_TO_REQUEST = 1000
MAX_RESPONSES_TO_WAIT = 100
DEFAULT_DHT_ROUTERS = [
    ("dht.libtorrent.org", 25401),
    ("router.bittorrent.com", 6881)
]

MAX_INT32 = 2 ** 16 - 1


class DHTTracker(TaskManager, Tracker):
    """
    This class manages BEP33 health requests to the libtorrent DHT.
    """
    def __init__(self, udp_socket_server: UdpSocketManager, proxy=None):
        TaskManager.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.socket_mgr = udp_socket_server
        self.proxy = proxy

        self.lookup_futures = {}  # Map from binary infohash to future
        self.bf_seeders = {}  # Map from infohash to (final) seeders bloomfilter
        self.bf_peers = {}  # Map from infohash to (final) peers bloomfilter
        self.outstanding = {}  # Map from transaction_id to infohash

        self.health_result = {}

        self.tid_to_infohash = dict()
        self.infohash_to_nodes = dict()
        self.infohash_to_responses = dict()

    async def get_health(self, infohash, timeout=15) -> TrackerResponse:
        """
        Lookup the health of a given infohash.
        :param infohash: The 20-byte infohash to lookup.
        :param timeout: The timeout of the lookup.
        """
        if infohash in self.lookup_futures:
            return await self.lookup_futures[infohash]

        lookup_future = Future()
        self.lookup_futures[infohash] = lookup_future
        self.bf_seeders[infohash] = bytearray(256)
        self.bf_peers[infohash] = bytearray(256)

        # Initially send request to one of the default DHT router and get the closest nodes.
        # Then query those nodes and process the Bloom filters from the response.
        await self.send_request_to_dht_router_and_continue(infohash)

        self.register_task(f"lookup_{hexlify(infohash)}", self.finalize_lookup, infohash, delay=timeout)

        return await lookup_future

    async def send_request_to_dht_router_and_continue(self, infohash):
        # Select one of the default router and send the peer request.
        # Routers send nodes in the DHT response.
        # Those nodes will be queried while processing the response.
        router_host, router_port = random.choice(DEFAULT_DHT_ROUTERS)
        print(f"router: ({(router_host, router_port)}")
        await self.send_dht_get_peers_request(router_host, router_port, infohash)

    async def send_dht_get_peers_request(self, node_ip, node_port, infohash):
        dht_request = self.compose_dht_get_peers_request(node_ip, node_port, infohash)
        await self.socket_mgr.send(dht_request, response_callback=self.process_udp_raw_response)

    def compose_dht_get_peers_request(self, host, port, infohash):
        # DHT requests require a unique transaction ID. This transaction ID
        # is returned on the response but not the infohash. So, we have to maintain a
        # map to transaction ID to infohash for associating response to infohash.
        transaction_id = self.generate_unique_transaction_id()
        self.tid_to_infohash[transaction_id] = infohash

        payload = DHTTracker.compose_dht_get_peers_payload(transaction_id, infohash)
        self.requesting_bloomfilters(transaction_id, infohash)

        udp_request = UdpRequest(
            transaction_id=transaction_id,
            receiver=(host, port),
            data=payload,
            socks_proxy=self.proxy,
            response=Future()
        )
        return udp_request

    @staticmethod
    def compose_dht_get_peers_payload(transaction_id: bytes, infohash: bytes):
        target = infohash
        request = {
            't': transaction_id,
            'y': b'q',
            'q': b'get_peers',
            'a': {
                'id': infohash,
                'info_hash': target,
                'noseed': 1,
                'scrape': 1
            }
        }
        payload = lt.bencode(request)
        return payload

    def generate_unique_transaction_id(self):
        while True:
            tx_id = random.randint(1, MAX_INT32).to_bytes(2, 'big')
            if tx_id not in self.tid_to_infohash:
                return tx_id

    async def process_udp_raw_response(self, dht_request: UdpRequest, response: bytes):
        decoded = lt.bdecode(response)
        if not decoded:
            return

        await self.proccess_dht_response(decoded)

    def finalize_lookup(self, infohash):
        """
        Finalize the lookup of the provided infohash and invoke the appropriate deferred.
        :param infohash: The infohash of the lookup we finalize.
        """
        for transaction_id in [key for key, value in self.outstanding.items() if value == infohash]:
            self.outstanding.pop(transaction_id, None)

        if infohash not in self.lookup_futures:
            return

        if self.lookup_futures[infohash].done():
            return

        # Determine the seeders/peers
        bf_seeders = self.bf_seeders.pop(infohash)
        bf_peers = self.bf_peers.pop(infohash)

        seeders = DHTTracker.get_size_from_bloomfilter(bf_seeders)
        peers = DHTTracker.get_size_from_bloomfilter(bf_peers)

        health = HealthInfo(infohash, last_check=int(time.time()), seeders=seeders, leechers=peers, self_checked=True)
        self.health_result[infohash] = health

        tracker_response = TrackerResponse('DHT', [health])
        self.lookup_futures[infohash].set_result(tracker_response)

    def decode_nodes(self, nodes: bytes) -> List[Tuple[str, str, int]]:
        decoded_nodes = []
        for i in range(0, len(nodes), 26):
            node_id = nodes[i:i + 20].hex()
            ip_bytes = nodes[i + 20:i + 24]
            ip_addr = '.'.join(str(byte) for byte in ip_bytes)
            port = int.from_bytes(nodes[i + 24:i + 26], byteorder='big')
            decoded_nodes.append((node_id, ip_addr, port))
        return decoded_nodes

    async def proccess_dht_response(self, decoded):
        if b'r' in decoded:
            transaction_id = decoded[b't']
            infohash = self.tid_to_infohash.pop(transaction_id, None)
            if not infohash:
                return

            dht_response = decoded[b'r']
            if b'nodes' in dht_response:
                b_nodes = dht_response[b'nodes']
                decoded_nodes = self.decode_nodes(b_nodes)
                await self.send_dht_get_peers_request_to_closest_nodes(infohash, decoded_nodes)

            # We received a raw DHT message - decode it and check whether it is a BEP33 message.
            if b'BFsd' in dht_response and b'BFpe' in dht_response:
                received_responses = self.infohash_to_responses.get(infohash, 0)
                self.infohash_to_responses[infohash] = received_responses + 1

                seeders_bloom_filter = dht_response[b'BFsd']
                peers_bloom_filter = dht_response[b'BFpe']
                self.received_bloomfilters(transaction_id,
                                           bytearray(seeders_bloom_filter),
                                           bytearray(peers_bloom_filter))

    async def send_dht_get_peers_request_to_closest_nodes(self, infohash, decoded_nodes):
        sent_nodes = self.infohash_to_nodes.get(infohash, [])
        diff = MAX_NODES_TO_REQUEST - len(sent_nodes)

        if diff <= 0 or self.infohash_to_responses.get(infohash, 0) > MAX_RESPONSES_TO_WAIT:
            return

        requests = []
        for (_node_id, node_ip, node_port) in decoded_nodes[:diff]:
            ip_port_str = f'{node_ip}:{node_port}'
            if ip_port_str not in sent_nodes:
                await asyncio.sleep(0.01)
                await self.send_dht_get_peers_request(node_ip, node_port, infohash)
                sent_nodes.append(ip_port_str)
                self.infohash_to_nodes[infohash] = sent_nodes

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

    def requesting_bloomfilters(self, transaction_id, infohash):
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

    def received_bloomfilters(self, transaction_id, bf_seeds=bytearray(256), bf_peers=bytearray(256)):
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

        if infohash not in self.bf_seeders or infohash not in self.bf_peers:
            self._logger.info("Could not find lookup infohash for incoming BEP33 bloomfilters")
            return

        self.bf_seeders[infohash] = DHTTracker.combine_bloomfilters(self.bf_seeders[infohash], bf_seeds)
        self.bf_peers[infohash] = DHTTracker.combine_bloomfilters(self.bf_peers[infohash], bf_peers)
