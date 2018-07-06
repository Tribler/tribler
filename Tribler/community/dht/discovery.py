import time

from collections import defaultdict

from twisted.internet.defer import fail
from twisted.internet.task import LoopingCall
from twisted.python.failure import Failure

from Tribler.community.dht.community import DHTCommunity, Request, PING_INTERVAL, TARGET_NODES, \
                                            gatherResponses, MAX_NODES_IN_FIND
from Tribler.community.dht.routing import NODE_STATUS_BAD, Node
from Tribler.community.dht.payload import StorePeerRequestPayload, StorePeerResponsePayload, \
                                          ConnectPeerRequestPayload, ConnectPeerResponsePayload, \
                                          PingRequestPayload, PingResponsePayload

MSG_STORE_PEER_REQUEST = 13
MSG_STORE_PEER_RESPONSE = 14
MSG_CONNECT_PEER_REQUEST = 15
MSG_CONNECT_PEER_RESPONSE = 16


class DHTDiscoveryCommunity(DHTCommunity):
    """
    Community for discovering peers that are behind NAT.
    """

    def __init__(self, *args, **kwargs):
        super(DHTDiscoveryCommunity, self).__init__(*args, **kwargs)

        self.store = defaultdict(list)
        self.store_for_me = defaultdict(list)

        self.decode_map.update({
            chr(MSG_STORE_PEER_REQUEST): self.on_store_peer_request,
            chr(MSG_STORE_PEER_RESPONSE): self.on_store_peer_response,
            chr(MSG_CONNECT_PEER_REQUEST): self.on_connect_peer_request,
            chr(MSG_CONNECT_PEER_RESPONSE): self.on_connect_peer_response,
        })

        self.register_task('store_peer', LoopingCall(self.store_peer)).start(30, now=False)

    def on_ping_request(self, source_address, data):
        super(DHTDiscoveryCommunity, self).on_ping_request(source_address, data)
        auth, _, _ = self._ez_unpack_auth(PingRequestPayload, data)
        for _, nodes in self.store.iteritems():
            for node in nodes:
                if node.public_key.key_to_bin() == auth.public_key_bin:
                    node.last_query = time.time()

    def on_ping_response(self, source_address, data):
        super(DHTDiscoveryCommunity, self).on_ping_response(source_address, data)
        auth, _, _ = self._ez_unpack_auth(PingResponsePayload, data)
        for _, nodes in self.store_for_me.iteritems():
            for node in nodes:
                if node.public_key.key_to_bin() == auth.public_key_bin:
                    node.last_response = time.time()

    def store_peer(self):
        # Do we already have enough peers storing our address?
        if len(self.store_for_me) >= TARGET_NODES / 2:
            return

        key = self.my_peer.mid
        return self.find_nodes(key).addCallback(lambda nodes: self.send_store_peer_request(key, nodes[:TARGET_NODES])) \
                                   .addErrback(lambda _: None)

    def send_store_peer_request(self, key, nodes):
        # Create new objects to avoid problem with the nodes also being in the routing table
        nodes = [Node(node.key, node.address) for node in nodes if node not in self.store_for_me[key]]

        if not nodes:
            return fail(Failure(RuntimeError('No nodes found for storing peer')))

        deferreds = []
        for node in nodes:
            if node in self.tokens:
                cache = self.request_cache.add(Request(self, node, [key]))
                deferreds.append(cache.deferred)
                self.send_message(node.address, MSG_STORE_PEER_REQUEST, StorePeerRequestPayload,
                                  (cache.number, self.tokens[node][1], key))
            else:
                self.logger.debug('Not sending store-peer-request to %s (no token available)', node)

        return gatherResponses(deferreds) if deferreds else fail(RuntimeError('Peer was not stored'))

    def connect_peer(self, mid):
        return self.find_nodes(mid).addCallback(lambda nodes, mid=mid:
                                                self.send_connect_peer_request(mid, nodes[:TARGET_NODES]))

    def send_connect_peer_request(self, key, nodes):
        # Create new objects to avoid problem with the nodes also being in the routing table
        nodes = [Node(node.key, node.address) for node in nodes]

        if not nodes:
            return fail(Failure(RuntimeError('No nodes found for connecting to peer')))

        deferreds = []
        for node in nodes:
            cache = self.request_cache.add(Request(self, node))
            deferreds.append(cache.deferred)
            self.send_message(node.address, MSG_CONNECT_PEER_REQUEST,
                              ConnectPeerRequestPayload, (cache.number, self.my_estimated_lan, key))

        return gatherResponses(deferreds).addCallback(lambda node_lists: list(set(sum(node_lists, []))))

    def on_store_peer_request(self, source_address, data):
        self.logger.debug('Got store-peer-request from %s', source_address)

        auth, _, payload = self._ez_unpack_auth(StorePeerRequestPayload, data)
        node = Node(auth.public_key_bin, source_address)
        node.last_query = time.time()

        if not self.check_token(node, payload.token):
            self.logger.warning('Bad token, dropping packet.')
            return

        if node not in self.store[payload.target]:
            self.logger.debug('Storing peer %s (key %s)', node, payload.target.encode('hex'))
            self.store[payload.target].append(node)

        self.send_message(node.address, MSG_STORE_PEER_RESPONSE,
                          StorePeerResponsePayload, (payload.identifier,))

    def on_store_peer_response(self, source_address, data):
        _, _, payload = self._ez_unpack_auth(StorePeerResponsePayload, data)

        if not self.request_cache.has(u'request', payload.identifier):
            self.logger.error('Got store-peer-response with unknown identifier, dropping packet')
            return

        self.logger.debug('Got store-peer-response from %s', source_address)

        cache = self.request_cache.pop(u'request', payload.identifier)

        key = cache.params[0]
        if cache.node not in self.store_for_me[key]:
            self.logger.debug('Peer %s storing us (key %s)', cache.node, key.encode('hex'))
            self.store_for_me[key].append(cache.node)

        cache.deferred.callback(cache.node)

    def on_connect_peer_request(self, source_address, data):
        self.logger.debug('Got connect-peer-request from %s', source_address)

        _, _, payload = self._ez_unpack_auth(ConnectPeerRequestPayload, data)

        nodes = self.store[payload.target][:MAX_NODES_IN_FIND]
        for node in nodes:
            packet = self.create_puncture_request(payload.lan_address, source_address, payload.identifier)
            self.endpoint.send(node.address, packet)

        self.logger.debug('Returning peers %s (key %s)', nodes, payload.target.encode('hex'))
        self.send_message(source_address, MSG_CONNECT_PEER_RESPONSE,
                          ConnectPeerResponsePayload, (payload.identifier, nodes))

    def on_connect_peer_response(self, source_address, data):
        _, _, payload = self._ez_unpack_auth(ConnectPeerResponsePayload, data)

        if not self.request_cache.has(u'request', payload.identifier):
            self.logger.error('Got connect-peer-response with unknown identifier, dropping packet')
            return

        self.logger.debug('Got connect-peer-response from %s', source_address)
        cache = self.request_cache.pop(u'request', payload.identifier)
        cache.deferred.callback(payload.nodes)

    def ping_all(self):
        pinged = super(DHTDiscoveryCommunity, self).ping_all()

        now = time.time()
        for key, nodes in self.store_for_me.iteritems():
            for index in xrange(len(nodes) - 1, -1, -1):
                node = nodes[index]
                if node.status == NODE_STATUS_BAD:
                    del self.store_for_me[key][index]
                    self.logger.debug('Deleting peer %s that stored us (key %s)', node, key.encode('hex'))
                elif node not in pinged and now > node.last_response + PING_INTERVAL:
                    self.ping(node)

        for key, nodes in self.store.iteritems():
            for index in xrange(len(nodes) - 1, -1, -1):
                node = nodes[index]
                if now > node.last_query + 60:
                    self.logger.debug('Deleting peer %s (key %s)', node, key.encode('hex'))
                    del self.store[key][index]
