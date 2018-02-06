import time

from twisted.internet.defer import inlineCallbacks, Deferred, fail, DeferredList, returnValue
from twisted.python.failure import Failure
from twisted.internet.task import LoopingCall

from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.requestcache import RandomNumberCache, RequestCache
from Tribler.pyipv8.ipv8.deprecated.payload import IntroductionRequestPayload, IntroductionResponsePayload
from Tribler.pyipv8.ipv8.deprecated.payload_headers import BinMemberAuthenticationPayload
from Tribler.pyipv8.ipv8.deprecated.payload_headers import GlobalTimeDistributionPayload
from Tribler.pyipv8.ipv8.deprecated.community import Community

from Tribler.community.dht.storage import Storage
from Tribler.community.dht.routing import RoutingTable, Node, distance, calc_node_id
from Tribler.community.dht.payload import PingRequestPayload, PingResponsePayload, StoreRequestPayload, \
                                          StoreResponsePayload, FindRequestPayload, FindResponsePayload

PING_INTERVAL = 55

MAX_ENTRY_SIZE = 128
MAX_ENTRY_AGE = 86400

MAX_FIND_WALKS = 8
MAX_FIND_STEPS = 4

MAX_VALUES_IN_STORE = 10
MAX_VALUES_IN_FIND = 10
MAX_NODES_IN_FIND = 8

# Target number of nodes at which a key-value pair should be stored
TARGET_NODES = 8


def gatherResponses(deferreds):
    def on_finished(results):
        return [x[1] for x in results if x[0]]
    return DeferredList(deferreds).addCallback(on_finished)


class Request(RandomNumberCache):
    """
    This request cache keeps track of all outstanding requests within the DHTCommunity.
    """
    def __init__(self, community, node, params=None):
        super(Request, self).__init__(community.request_cache, u'request')
        self.node = node
        self.params = params
        self.deferred = Deferred()
        self.start_time = time.time()

    @property
    def timeout_delay(self):
        return 5.0

    def on_timeout(self):
        if not self.deferred.called:
            self._logger.error('Request to %s timed out', self.node.address)
            self.node.failed += 1
            self.deferred.errback(Failure(RuntimeError("Node timeout")))

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
        self.register_task('maintenance', LoopingCall(self.maintenance)).start(3600, now=False)
        self.register_task('ping_all', LoopingCall(self.ping_all)).start(10, now=False)

        # Register messages
        self.decode_map.update({
            chr(7): self.on_ping_request,
            chr(8): self.on_ping_response,
            chr(9): self.on_store_request,
            chr(10): self.on_store_response,
            chr(11): self.on_find_request,
            chr(12): self.on_find_response,
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
        if not self.routing_table.has(node):
            node = self.routing_table.add(node)

            if node:
                self.logger.info('Added node %s to the routing table', node.address)

                # Ping the node in order to determine RTT
                yield self.ping(node)

                # Check if we need to move data to the new node
                for key, values in self.storage.data.iteritems():
                    if distance(key, self.my_node_id) > distance(key, node.id):
                        self.store_on_nodes(key, [v for _, _, v in values], [node])

    def ping_all(self):
        deferreds = []
        now = time.time()
        for bucket in self.routing_table.trie.values():
            for node in bucket.nodes.values():
                if node.last_response + PING_INTERVAL <= now:
                    deferreds.append(self.ping(node).addErrback(lambda _: None))
        return DeferredList(deferreds)

    def ping(self, node):
        self.logger.info('Pinging node %s', node.address)

        cache = self.request_cache.add(Request(self, node))
        self.send_message(node.address, 7, PingRequestPayload, (cache.number,))
        return cache.deferred

    def on_ping_request(self, source_address, data):
        self.logger.debug('Got ping-request from %s', source_address)

        auth, _, payload = self._ez_unpack_auth(PingRequestPayload, data)
        node = self.routing_table.add(Node(auth.public_key_bin, source_address))
        if node:
            node.last_query = time.time()
        self.send_message(source_address, 8, PingResponsePayload, (payload.identifier,))

    def on_ping_response(self, source_address, data):
        _, _, payload = self._ez_unpack_auth(PingResponsePayload, data)

        if not self.request_cache.has(u'request', payload.identifier):
            self.logger.error('Got ping-response with unknown identifier, dropping packet')
            return

        self.logger.debug('Got ping-response from %s', source_address)
        cache = self.request_cache.pop(u'request', payload.identifier)
        cache.on_complete()
        cache.deferred.callback(cache.node)

    def store(self, key, value):
        if len(value) > MAX_ENTRY_SIZE:
            return fail(Failure(RuntimeError("Maximum length exceeded")))

        return self.find_nodes(key).addCallback(lambda nodes, k=key, v=value:
                                                self.store_on_nodes(k, [v], nodes[:TARGET_NODES]))

    def store_on_nodes(self, key, values, nodes):
        if not nodes:
            return fail(Failure(RuntimeError("No nodes found for storing the key-value pairs")))

        values = values[:MAX_VALUES_IN_STORE]

        # Check if we also need to store this key-value pair
        largest_distance = max([distance(node.id, key) for node in nodes])
        if distance(self.my_node_id, key) < largest_distance:
            for value in values:
                self.storage.put(key, value, MAX_ENTRY_AGE)

        deferreds = []
        for node in nodes:
            cache = self.request_cache.add(Request(self, node))
            deferreds.append(cache.deferred)
            # TODO: add token?
            self.send_message(node.address, 9, StoreRequestPayload, (cache.number, key, values))

        return gatherResponses(deferreds)

    def on_store_request(self, source_address, data):
        self.logger.debug('Got store-request from %s', source_address)

        auth, _, payload = self._ez_unpack_auth(StoreRequestPayload, data)
        node = self.routing_table.add(Node(auth.public_key_bin, source_address))

        if any([len(value) > MAX_ENTRY_SIZE for value in payload.values]):
            self.logger.error('Maximum length of value exceeded, dropping packet.')
            return
        if len(payload.values) > MAX_VALUES_IN_STORE:
            self.logger.error('Too many values, dropping packet.')
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
            self.storage.put(payload.target, value, max_age)

        if node:
            node.last_query = time.time()

        self.send_message(source_address, 10, StoreResponsePayload, (payload.identifier,))

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
        self.send_message(node.address, 11, FindRequestPayload,
                          (cache.number, self.my_estimated_lan, target, force_nodes))
        return cache.deferred

    @inlineCallbacks
    def find(self, target, force_nodes=False):
        nodes_closest = set(self.routing_table.closest_nodes(target, max_nodes=MAX_FIND_WALKS))
        if not nodes_closest:
            returnValue(Failure(RuntimeError("No nodes found in the routing table")))

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

        if missed:
            # Cache this value at the closest node
            self.store_on_nodes(target, values, [missed[-1]])

        returnValue(values)

    def find_values(self, target):
        return self.find(target, force_nodes=False)

    def find_nodes(self, target):
        return self.find(target, force_nodes=True)

    def on_find_request(self, source_address, data):
        self.logger.debug('Got find-request from %s', source_address)

        auth, _, payload = self._ez_unpack_auth(FindRequestPayload, data)
        node = self.routing_table.add(Node(auth.public_key_bin, source_address))
        if node:
            node.last_query = time.time()

        nodes = []
        values = self.storage.get(payload.target)[:MAX_VALUES_IN_FIND] if not payload.force_nodes else []

        if payload.force_nodes or not values:
            nodes = self.routing_table.closest_nodes(payload.target, exclude=node, max_nodes=MAX_NODES_IN_FIND)
            # Send puncture request to the closest node
            if nodes:
                packet = self.create_puncture_request(payload.lan_address, source_address, payload.identifier)
                self.endpoint.send(nodes[0].address, packet)

        self.send_message(source_address, 12, FindResponsePayload, (payload.identifier, values, nodes))

    def on_find_response(self, source_address, data):
        _, _, payload = self._ez_unpack_auth(FindResponsePayload, data)

        if not self.request_cache.has(u'request', payload.identifier):
            self.logger.error('Got find-response with unknown identifier, dropping packet')
            return

        self.logger.debug('Got find-response from %s', source_address)
        cache = self.request_cache.pop(u'request', payload.identifier)
        cache.on_complete()
        if cache.deferred.called:
            # The errback must already have been called (due to a timeout)
            return
        elif cache.params[0]:
            cache.deferred.callback((cache.node, {'nodes': payload.nodes}))
        else:
            cache.deferred.callback((cache.node, {'values': payload.values} if payload.values else \
                                                 {'nodes': payload.nodes}))

    def maintenance(self):
        # Refresh buckets
        now = time.time()
        for bucket in self.routing_table.trie.values():
            if now - bucket.last_changed > 15 * 60:
                self.find_values(bucket.generate_id())
                bucket.last_changed = now

        # Replicate keys older than one hour
        for key, value in self.storage.items_older_than(3600):
            self.store(key, value)

        # Also republish our own key-value pairs every 24h?
