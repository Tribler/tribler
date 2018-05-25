import os
import time
import hashlib

from collections import deque, defaultdict

from twisted.internet.defer import inlineCallbacks, Deferred, fail, DeferredList, returnValue
from twisted.internet.task import LoopingCall
from twisted.python.failure import Failure

from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.requestcache import RandomNumberCache, RequestCache
from Tribler.pyipv8.ipv8.deprecated.payload import IntroductionRequestPayload, IntroductionResponsePayload
from Tribler.pyipv8.ipv8.deprecated.payload_headers import BinMemberAuthenticationPayload
from Tribler.pyipv8.ipv8.deprecated.payload_headers import GlobalTimeDistributionPayload
from Tribler.pyipv8.ipv8.deprecated.community import Community
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto

from Tribler.community.dht.storage import Storage
from Tribler.community.dht.routing import RoutingTable, Node, distance, calc_node_id
from Tribler.community.dht.payload import PingRequestPayload, PingResponsePayload, StoreRequestPayload, \
                                          StoreResponsePayload, FindRequestPayload, FindResponsePayload, \
                                          SignedStrPayload, StrPayload

PING_INTERVAL = 25

DHT_ENTRY_STR = 0
DHT_ENTRY_STR_SIGNED = 1

MAX_ENTRY_SIZE = 155
MAX_ENTRY_AGE = 86400

MAX_FIND_WALKS = 8
MAX_FIND_STEPS = 4

MAX_VALUES_IN_STORE = 9
MAX_VALUES_IN_FIND = 9
MAX_NODES_IN_FIND = 8

# Target number of nodes at which a key-value pair should be stored
TARGET_NODES = 8

MSG_PING = 7
MSG_PONG = 8
MSG_STORE_REQUEST = 9
MSG_STORE_RESPONSE = 10
MSG_FIND_REQUEST = 11
MSG_FIND_RESPONSE = 12


def gatherResponses(deferreds):
    def on_finished(results):
        return [x[1] for x in results if x[0]]
    return DeferredList(deferreds).addCallback(on_finished)


class Request(RandomNumberCache):
    """
    This request cache keeps track of all outstanding requests within the DHTCommunity.
    """
    def __init__(self, community, node, params=None, consume_errors=True):
        super(Request, self).__init__(community.request_cache, u'request')
        self.node = node
        self.params = params
        self.deferred = Deferred()
        self.start_time = time.time()
        self.consume_errors = consume_errors

    @property
    def timeout_delay(self):
        return 5.0

    def on_timeout(self):
        if not self.deferred.called:
            self._logger.warning('Request to %s timed out', self.node)
            self.node.failed += 1
            if not self.consume_errors:
                self.deferred.errback(Failure(RuntimeError('Node %s timeout' % self.node)))

    def on_complete(self):
        self.node.last_response = time.time()
        self.node.failed = 0
        self.node.rtt = time.time() - self.start_time


class DHTCommunity(Community):
    """
    Community for storing/finding key-value pairs.
    """
    master_peer = Peer('3081a7301006072a8648ce3d020106052b8104002703819200040578cfb7bc3e708df6f1a60b6baaf405c29e6cd0a'
                       '393091b25251bf705b643af53755decbd04ce35886a87c11324d18b93efd44dc120e9559e5439ba008f0365be73a0'
                       'e30f9d963706ea766e9f89974057fda760bbe2bf533979cdccad95b6b9c19e9d4873cefc2669493f904deccc986e2'
                       '0e4a7e60c1b7d7c9ec84fddcb908700df2365325be00596d37c05a72a7c26'.decode('hex'))

    def __init__(self, *args, **kwargs):
        super(DHTCommunity, self).__init__(*args, **kwargs)
        self.routing_table = RoutingTable(self.my_node_id)
        self.storage = Storage()
        self.request_cache = RequestCache()
        self.tokens = {}
        self.token_secrets = deque(maxlen=2)
        self.register_task('ping_all', LoopingCall(self.ping_all)).start(10, now=False)
        self.register_task('value_maintenance', LoopingCall(self.value_maintenance)).start(3600, now=False)
        self.register_task('token_maintenance', LoopingCall(self.token_maintenance)).start(300, now=True)

        # Register messages
        self.decode_map.update({
            chr(MSG_PING): self.on_ping_request,
            chr(MSG_PONG): self.on_ping_response,
            chr(MSG_STORE_REQUEST): self.on_store_request,
            chr(MSG_STORE_RESPONSE): self.on_store_response,
            chr(MSG_FIND_REQUEST): self.on_find_request,
            chr(MSG_FIND_RESPONSE): self.on_find_response,
        })

        self.logger.info('DHT community initialized (peer mid %s)', self.my_peer.mid.encode('HEX'))

    @inlineCallbacks
    def unload(self):
        self.request_cache.clear()
        yield super(DHTCommunity, self).unload()

    @property
    def my_node_id(self):
        return calc_node_id(self.my_peer.address[0], self.my_peer.mid)

    def send_message(self, address, message_id, payload_cls, payload_args):
        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = payload_cls(*payload_args).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()
        packet = self._ez_pack(self._prefix, message_id, [auth, dist, payload])
        return self.endpoint.send(address, packet)

    def on_introduction_request(self, source_address, data):
        super(DHTCommunity, self).on_introduction_request(source_address, data)
        auth, _, _ = self._ez_unpack_auth(IntroductionRequestPayload, data)
        # Filter out trackers
        if source_address not in self.network.blacklist:
            node = Node(auth.public_key_bin, source_address)
            self.on_node_discovered(node)

    def on_introduction_response(self, source_address, data):
        super(DHTCommunity, self).on_introduction_response(source_address, data)
        auth, _, _ = self._ez_unpack_auth(IntroductionResponsePayload, data)
        # Filter out trackers
        if source_address not in self.network.blacklist:
            node = Node(auth.public_key_bin, source_address)
            self.on_node_discovered(node)

    @inlineCallbacks
    def on_node_discovered(self, node):
        existed = self.routing_table.has(node)
        node = self.routing_table.add(node)

        if not existed and node:
            self.logger.info('Added node %s to the routing table', node)
            # Ping the node in order to determine RTT
            yield self.ping(node)

    def ping_all(self):
        self.routing_table.remove_bad_nodes()

        pinged = []
        now = time.time()
        for bucket in self.routing_table.trie.values():
            for node in bucket.nodes.values():
                if node.last_response + PING_INTERVAL <= now:
                    self.ping(node)
                    pinged.append(node)
        return pinged

    def ping(self, node):
        self.logger.info('Pinging node %s', node)

        cache = self.request_cache.add(Request(self, node))
        self.send_message(node.address, MSG_PING, PingRequestPayload, (cache.number,))
        return cache.deferred

    def on_ping_request(self, source_address, data):
        self.logger.debug('Got ping-request from %s', source_address)

        auth, _, payload = self._ez_unpack_auth(PingRequestPayload, data)

        node = Node(auth.public_key_bin, source_address)
        node = self.routing_table.add(node) or node
        node.last_query = time.time()

        self.send_message(source_address, MSG_PONG, PingResponsePayload, (payload.identifier,))

    def on_ping_response(self, source_address, data):
        _, _, payload = self._ez_unpack_auth(PingResponsePayload, data)

        if not self.request_cache.has(u'request', payload.identifier):
            self.logger.error('Got ping-response with unknown identifier, dropping packet')
            return

        self.logger.debug('Got ping-response from %s', source_address)
        cache = self.request_cache.pop(u'request', payload.identifier)
        cache.on_complete()
        cache.deferred.callback(cache.node)

    def serialize_value(self, data, sign=True):
        if sign:
            payload = SignedStrPayload(data, int(time.time()), self.my_peer.public_key.key_to_bin())
            return self._ez_pack('', DHT_ENTRY_STR_SIGNED, [payload.to_pack_list()], sig=True)
        payload = StrPayload(data)
        return self._ez_pack('', DHT_ENTRY_STR, [payload.to_pack_list()], sig=False)

    def unserialize_value(self, value):
        if value[0] == chr(DHT_ENTRY_STR):
            payload = self.serializer.unpack_to_serializables([StrPayload], value[1:])[0]
            return payload.data, None, 0
        elif value[0] == chr(DHT_ENTRY_STR_SIGNED):
            payload = self.serializer.unpack_to_serializables([SignedStrPayload], value[1:])[0]
            ec = ECCrypto()
            public_key = ec.key_from_public_bin(payload.public_key)
            sig_len = ec.get_signature_length(public_key)
            sig = value[-sig_len:]
            if ec.is_valid_signature(public_key, value[:-sig_len], sig):
                return payload.data, payload.public_key, payload.version

    def add_value(self, key, value, max_age=MAX_ENTRY_AGE):
        unserialized = self.unserialize_value(value)
        if unserialized:
            _, public_key, version = unserialized
            id_ = hashlib.sha1(public_key).digest() if public_key else None
            self.storage.put(key, value, id_=id_, version=version, max_age=max_age)
        else:
            self.logger.warning('Failed to store value %s', value.encode('hex'))

    def store_value(self, key, data, sign=False):
        value = self.serialize_value(data, sign=sign)
        return self._store(key, value)

    def _store(self, key, value):
        if len(value) > MAX_ENTRY_SIZE:
            return fail(Failure(RuntimeError('Maximum length exceeded')))

        return self.find_nodes(key).addCallback(lambda nodes, k=key, v=value:
                                                self.store_on_nodes(k, [v], nodes[:TARGET_NODES]))

    def store_on_nodes(self, key, values, nodes):
        if not nodes:
            return fail(Failure(RuntimeError('No nodes found for storing the key-value pairs')))

        values = values[:MAX_VALUES_IN_STORE]

        # Check if we also need to store this key-value pair
        largest_distance = max([distance(node.id, key) for node in nodes])
        if distance(self.my_node_id, key) < largest_distance:
            for value in values:
                self.add_value(key, value)

        deferreds = []
        for node in nodes:
            if node in self.tokens:
                cache = self.request_cache.add(Request(self, node))
                deferreds.append(cache.deferred)
                self.send_message(node.address, MSG_STORE_REQUEST, StoreRequestPayload,
                                  (cache.number, self.tokens[node][1], key, values))
            else:
                self.logger.debug('Not sending store-request to %s (no token available)', node)

        return gatherResponses(deferreds) if deferreds else fail(RuntimeError('Value was not stored'))

    def on_store_request(self, source_address, data):
        self.logger.debug('Got store-request from %s', source_address)

        auth, _, payload = self._ez_unpack_auth(StoreRequestPayload, data)
        node = Node(auth.public_key_bin, source_address)
        node = self.routing_table.add(node) or node
        node.last_query = time.time()

        if any([len(value) > MAX_ENTRY_SIZE for value in payload.values]):
            self.logger.warning('Maximum length of value exceeded, dropping packet.')
            return
        if len(payload.values) > MAX_VALUES_IN_STORE:
            self.logger.warning('Too many values, dropping packet.')
            return
        # Note that even though we are preventing spoofing of source_address (by checking the token),
        # the value that is to be stored isn't checked. This should be done at a higher level.
        if not self.check_token(node, payload.token):
            self.logger.warning('Bad token, dropping packet.')
            return

        # How many nodes (that we know of) are closer to this value?
        num_closer = 0
        for node in self.routing_table.closest_nodes(payload.target, max_nodes=20):
            if distance(node.id, payload.target) < distance(self.my_node_id, payload.target):
                num_closer += 1

        # To prevent over-caching, the expiration time of an entry depends on the number
        # of nodes that are closer than us.
        max_age = MAX_ENTRY_AGE / 2 ** max(0, num_closer - TARGET_NODES + 1)
        for value in payload.values:
            self.add_value(payload.target, value, max_age)

        self.send_message(source_address, MSG_STORE_RESPONSE, StoreResponsePayload, (payload.identifier,))

    def on_store_response(self, source_address, data):
        _, _, payload = self._ez_unpack_auth(StoreResponsePayload, data)

        if not self.request_cache.has(u'request', payload.identifier):
            self.logger.error('Got store-response with unknown identifier, dropping packet')
            return

        self.logger.debug('Got store-response from %s', source_address)
        cache = self.request_cache.pop(u'request', payload.identifier)
        cache.on_complete()
        cache.deferred.callback(cache.node)

    def _send_find_request(self, node, target, force_nodes):
        cache = self.request_cache.add(Request(self, node, [force_nodes]))
        self.send_message(node.address, MSG_FIND_REQUEST, FindRequestPayload,
                          (cache.number, self.my_estimated_lan, target, force_nodes))
        return cache.deferred

    @inlineCallbacks
    def _find(self, target, force_nodes=False):
        nodes_closest = set(self.routing_table.closest_nodes(target, max_nodes=MAX_FIND_WALKS))
        if not nodes_closest:
            returnValue(Failure(RuntimeError('No nodes found in the routing table')))

        nodes_tried = set()
        values = set()
        index = 0
        missed = []

        while nodes_closest:
            # Send closest nodes a find-node-request
            deferreds = [self._send_find_request(node, target, force_nodes) for node in nodes_closest]
            responses = yield gatherResponses(deferreds)

            nodes_tried |= nodes_closest
            nodes_closest.clear()

            # Process responses
            to_puncture = {}
            for sender, response in responses:
                if 'values' in response:
                    values |= set(response['values'])
                else:
                    # Pick a node that we haven't tried yet. Trigger a puncture if needed.
                    node = next((n for n in response['nodes']
                                 if n not in nodes_tried and n not in to_puncture.itervalues()), None)
                    if node:
                        to_puncture[sender] = node
                        nodes_closest.add(node)

                    if not force_nodes:
                        # Store the key-value pair on the most recently visited node that
                        # did not have it (for caching purposes).
                        missed.append(sender)

            # Wait for punctures (if any)...
            deferreds = [self._send_find_request(sender, node.id, force_nodes)
                         for sender, node in to_puncture.iteritems()]
            yield DeferredList(deferreds)

            # Have we exceeded the maximum number of iterations?
            index += 1
            if index > MAX_FIND_STEPS:
                break

            # Ensure we haven't tried these nodes yet
            nodes_closest -= nodes_tried

        if force_nodes:
            returnValue(sorted(nodes_tried, key=lambda n: distance(n.id, target)))

        values = list(values)

        if missed and values:
            # Cache values at the closest node
            self.store_on_nodes(target, values, [missed[-1]])

        returnValue(self.post_process_values(values))

    def post_process_values(self, values):
        # Unpack values and filter out duplicates
        unpacked = defaultdict(list)
        for value in values:
            unserialized = self.unserialize_value(value)
            if unserialized:
                data, public_key, version = unserialized
                unpacked[public_key].append((version, data))
        return [(max(v, key=lambda t: t[0])[1], k) for k, v in unpacked.iteritems() if k is not None] + \
               [(data[1], None) for data in unpacked[None]]

    def find_values(self, target):
        return self._find(target, force_nodes=False)

    def find_nodes(self, target):
        return self._find(target, force_nodes=True)

    def on_find_request(self, source_address, data):
        self.logger.debug('Got find-request from %s', source_address)

        auth, _, payload = self._ez_unpack_auth(FindRequestPayload, data)
        node = Node(auth.public_key_bin, source_address)
        node = self.routing_table.add(node) or node
        node.last_query = time.time()

        nodes = []
        values = self.storage.get(payload.target, limit=MAX_VALUES_IN_FIND) if not payload.force_nodes else []

        if payload.force_nodes or not values:
            nodes = self.routing_table.closest_nodes(payload.target, exclude=node, max_nodes=MAX_NODES_IN_FIND)
            # Send puncture request to the closest node
            if nodes:
                packet = self.create_puncture_request(payload.lan_address, source_address, payload.identifier)
                self.endpoint.send(nodes[0].address, packet)

        self.send_message(source_address, MSG_FIND_RESPONSE, FindResponsePayload,
                          (payload.identifier, self.generate_token(node), values, nodes))

    def on_find_response(self, source_address, data):
        _, _, payload = self._ez_unpack_auth(FindResponsePayload, data)

        if not self.request_cache.has(u'request', payload.identifier):
            self.logger.error('Got find-response with unknown identifier, dropping packet')
            return

        self.logger.debug('Got find-response from %s', source_address)
        cache = self.request_cache.pop(u'request', payload.identifier)
        cache.on_complete()

        self.tokens[cache.node] = (time.time(), payload.token)

        if cache.deferred.called:
            # The errback must already have been called (due to a timeout)
            return
        elif cache.params[0]:
            cache.deferred.callback((cache.node, {'nodes': payload.nodes}))
        else:
            cache.deferred.callback((cache.node, {'values': payload.values} if payload.values else \
                                                 {'nodes': payload.nodes}))

    def value_maintenance(self):
        # Refresh buckets
        now = time.time()
        for bucket in self.routing_table.trie.values():
            if now - bucket.last_changed > 15 * 60:
                self.find_values(bucket.generate_id()).addErrback(lambda _: None)
                bucket.last_changed = now

        # Replicate keys older than one hour
        for key, value in self.storage.items_older_than(3600):
            self._store(key, value).addErrback(lambda _: None)

        # Also republish our own key-value pairs every 24h?

    def token_maintenance(self):
        self.token_secrets.append(os.urandom(16))

        # Cleanup old tokens
        now = time.time()
        for node, (ts, _) in self.tokens.items():
            if now > ts + 600:
                self.tokens.pop(node, None)

    def generate_token(self, node):
        return hashlib.sha1(str(node) + self.token_secrets[-1]).digest()

    def check_token(self, node, token):
        return any([hashlib.sha1(str(node) + secret).digest() == token for secret in self.token_secrets])
