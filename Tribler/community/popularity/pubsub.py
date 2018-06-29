import logging
from abc import abstractmethod
from copy import copy
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall

from Tribler.community.popularity.constants import MSG_SUBSCRIPTION, ERROR_UNKNOWN_PEER, MAX_SUBSCRIBERS, \
    MSG_SUBSCRIBE, MAX_PUBLISHERS, PUBLISH_INTERVAL
from Tribler.community.popularity.payload import ContentSubscription
from Tribler.community.popularity.request import ContentRequest
from Tribler.pyipv8.ipv8.deprecated.community import Community
from Tribler.pyipv8.ipv8.deprecated.payload_headers import BinMemberAuthenticationPayload, GlobalTimeDistributionPayload
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.requestcache import RequestCache


class PubSubCommunity(Community):
    """
    This community is designed as a base community for all othe future communities that desires publish subscribe model
    for content dissemination. It provides a few basic primitives like subscribe/unsubscribe to publisher peers and
    publish/broadcast content to subscriber peers.

    All the derived community should implement publish_next_content() method which is responsible for publishing the
    next available content to all the subscribers.
    """

    def __init__(self, *args, **kwargs):
        super(PubSubCommunity, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.request_cache = RequestCache()

        # Register messages
        self.decode_map.update({
            chr(MSG_SUBSCRIBE): self.on_subscribe,
            chr(MSG_SUBSCRIPTION): self.on_subscription_status
        })

        # A set of publisher and subscriber.
        # Sends data updates to subscribers, and receives updates from subscribers.
        self.subscribers = set()
        self.publishers = set()

    def start(self):
        """
        Starts the community by subscribing to peers, and periodically publishing the content updates to
        the subscribers.
        """
        # Subscribe peers
        self.subscribe_peers()

        def start_publishing():
            # Update the publisher and subscriber list
            self.refresh_peer_list()

            # publish the new cotent from the content repository
            self.publish_next_content()

        self.register_task("start_publishing", LoopingCall(start_publishing)).start(PUBLISH_INTERVAL, False)

    @inlineCallbacks
    def unload(self):
        self.request_cache.clear()
        self.cancel_pending_task("start_publishing")
        yield super(PubSubCommunity, self).unload()

    def subscribe_peers(self):
        """
        Subscribes to the connected peers. First, the peers are sorted based on the trust score on descending order and
        content subscribe request is sent to the top peers.
        This method is called periodically through refresh_peer_list() in start_publishing() loop so it can fill up for
        the disconnected peers by connecting to new peers.
        Note that, existing publisher peers are not disconnected even if we find new peers with higher trust score but
        only fill up the remaining publisher slots with new top peers.
        """
        num_publishers = len(self.publishers)
        num_peers = len(self.get_peers())
        # If we have some free publisher slots and there are peers available
        if num_publishers < MAX_PUBLISHERS and num_publishers < num_peers:
            available_publishers = [peer for peer in self.get_peers() if peer not in self.publishers]
            sorted_peers = sorted(available_publishers,
                                  key=lambda _peer: self.trustchain.get_trust(_peer) if self.trustchain else 1,
                                  reverse=True)
            for peer in sorted_peers[: MAX_PUBLISHERS - num_publishers]:
                self.subscribe(peer, subscribe=True)

    def refresh_peer_list(self):
        """
        Updates the publishers and subscribers list by filtering out the disconnected peers. It also calls subscribe
        peers to replenish the available publisher slots if necessary.
        """
        peers = self.get_peers()
        self.publishers = set([peer for peer in self.publishers if peer in peers])
        self.subscribers = set([peer for peer in self.subscribers if peer in peers])

        # subscribe peers if necessary
        self.subscribe_peers()

    def unsubscribe_peers(self):
        """
        Unsubscribes from the existing publishers by sending content subscribe request with subscribe=False. It then
        clears up its publishers list.
        - Called at community unload.
        """
        for peer in copy(self.publishers):
            self.subscribe(peer, subscribe=False)
        self.publishers.clear()

    def subscribe(self, peer, subscribe=True):
        """
        Method to send content subscribe/unsubscribe message. This message is sent to each individual publisher peer we
        want to subscribe/unsubscribe.
        """
        cache = self.request_cache.add(ContentRequest(self.request_cache, MSG_SUBSCRIBE, None))
        # Remove the publisher peer already if user is trying to unsubscribe
        if not subscribe:
            self.publishers.remove(peer)

        # Create subscription packet and send it
        subscription = ContentSubscription(cache.number, subscribe)
        packet = self.create_message_packet(MSG_SUBSCRIBE, subscription)
        self.broadcast_message(packet, peer=peer)

    def on_subscribe(self, source_address, data):
        """
        Message handler for content subscribe message. It handles both subscribe and unsubscribe requests.
        Upon successful subscription or unsubscription, it send the confirmation subscription message with status.
        In case of subscription, it also publishes a list of recently checked torrents to the subscriber.
        """
        auth, _, payload = self._ez_unpack_auth(ContentSubscription, data)
        peer = self.get_peer_from_auth(auth, source_address)

        # Subscribe or unsubscribe peer
        subscribed = peer in self.subscribers

        if payload.subscribe and not subscribed:
            if len(self.subscribers) < MAX_SUBSCRIBERS:
                self.subscribers.add(peer)
                subscribed = True

        elif not payload.subscribe and subscribed:
            self.subscribers.remove(peer)
            subscribed = False

        # Send subscription response
        self.send_subscription_status(peer, payload.identifier, subscribed=subscribed)

        return subscribed

    def send_subscription_status(self, peer, identifier, subscribed=True):
        """
        Method to send content subscription message. Content subscription message is send in response to content
        subscribe or unsubscribe message.
        """
        if peer not in self.get_peers():
            self.logger.error(ERROR_UNKNOWN_PEER)
            return

        subscription = ContentSubscription(identifier, subscribed)
        packet = self.create_message_packet(MSG_SUBSCRIPTION, subscription)
        self.broadcast_message(packet, peer=peer)

    def on_subscription_status(self, source_address, data):
        """
        Message handler for content subscription message. Content subscription message is sent by the publisher stating
        the status of the subscription in response to subscribe or unsubscribe request.

        If the subscription message has subscribe=True, it means the subscription was successful, so the peer is added
        to the subscriber. In other case, publisher is removed if it is still present in the publishers list.
        """
        auth, _, payload = self._ez_unpack_auth(ContentSubscription, data)
        peer = self.get_peer_from_auth(auth, source_address)

        cache = self.request_cache.pop(u'request', payload.identifier)
        if not cache:
            return

        if payload.subscribe:
            self.publishers.add(peer)
        elif peer in self.publishers:
            self.publishers.remove(peer)

    def create_message_packet(self, message_type, payload):
        """
        Helper method to creates a message packet of given type with provided payload.
        """
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        dist = GlobalTimeDistributionPayload(self.claim_global_time()).to_pack_list()
        payload = payload if isinstance(payload, list) else payload.to_pack_list()
        return self._ez_pack(self._prefix, message_type, [auth, dist, payload])

    def broadcast_message(self, packet, peer=None):
        """
        Helper method to broadcast the message packet to a single peer or all the subscribers.
        """
        if peer is not None:
            self.endpoint.send(peer.address, packet)
            return

        for _peer in self.subscribers:
            self.endpoint.send(_peer.address, packet)

    def get_peer_from_auth(self, auth, source_address):
        """
        Get Peer object from the message and auth and source_address.
        It is used for mocking the peer in test.
        """
        return Peer(auth.public_key_bin, source_address)

    def pack_sized(self, payload_list, fit_size, start_index=0):
        """
        Packs a list of Payload objects to fit into given size limit.
        :param payload_list: List<Payload> list of payload objects
        :param fit_size: The maximum allowed size for payload field to fit into UDP packet.
        :param start_index: Index of list to start packing
        :return: packed string
        """
        assert isinstance(payload_list, list)
        serialized_results = ''
        size = 0
        current_index = start_index
        num_payloads = len(payload_list)
        while current_index < num_payloads:
            item = payload_list[current_index]
            packed_item = self.serializer.pack_multiple(item.to_pack_list())
            packed_item_length = len(packed_item)
            if size + packed_item_length > fit_size:
                break
            else:
                size += packed_item_length
                serialized_results += packed_item
            current_index += 1
        return serialized_results, current_index, current_index - start_index

    @abstractmethod
    def publish_next_content(self):
        """ Method responsible for publishing content during periodic push """
        pass
