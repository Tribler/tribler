import logging
from copy import copy
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall

from Tribler.Core.simpledefs import SIGNAL_SEARCH_COMMUNITY, SIGNAL_ON_SEARCH_RESULTS
from Tribler.community.popular.constants import MSG_POPULAR_CONTENT_SUBSCRIBE, MSG_POPULAR_CONTENT_SUBSCRIPTION, \
    MSG_TORRENT_HEALTH_RESPONSE, MSG_CHANNEL_HEALTH_RESPONSE, MSG_TORRENT_INFO_REQUEST, MSG_TORRENT_INFO_RESPONSE, \
    MSG_SEARCH_REQUEST, MSG_SEARCH_RESPONSE, MAX_PUBLISHERS, PUBLISH_INTERVAL, MAX_SUBSCRIBERS, \
    ERROR_UNKNOWN_RESPONSE, TORRENT_SEARCH_RESPONSE_TYPE, CHANNEL_SEARCH_RESPONSE_TYPE, TYPE_CHANNEL, \
    MAX_PACKET_PAYLOAD_SIZE, ERROR_UNKNOWN_PEER, ERROR_NO_CONTENT, MASTER_PUBLIC_KEY, MSG_CONTENT_INFO_REQUEST, \
    SEARCH_TORRENT_REQUEST, MSG_CONTENT_INFO_RESPONSE, SEARCH_TORRENT_RESPONSE
from Tribler.community.popular.payload import TorrentHealthPayload, ContentSubscription, TorrentInfoRequestPayload, \
    TorrentInfoResponsePayload, SearchRequestPayload, SearchResponsePayload, SearchResponseItemPayload, \
    ChannelItemPayload, ContentInfoRequest, Pagination, ContentInfoResponse
from Tribler.community.popular.repository import ContentRepository, TYPE_TORRENT_HEALTH
from Tribler.community.popular.request import SearchRequest
from Tribler.pyipv8.ipv8.deprecated.community import Community
from Tribler.pyipv8.ipv8.deprecated.payload_headers import BinMemberAuthenticationPayload, GlobalTimeDistributionPayload
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.requestcache import RequestCache


class PubSubCommunity(Community):

    def __init__(self, *args, **kwargs):
        super(PubSubCommunity, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.request_cache = RequestCache()

        # Register messages
        self.decode_map.update({
            chr(MSG_POPULAR_CONTENT_SUBSCRIBE): self.on_popular_content_subscribe,
            chr(MSG_POPULAR_CONTENT_SUBSCRIPTION): self.on_popular_content_subscription
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
        yield super(PubSubCommunity, self).unload()

    def subscribe_peers(self):
        """
        Subscribes to the connected peers. First, the peers are sorted based on the trust score on descending order and
        content subscribe request is sent to the top peers.
        This method is called periodically so it can fill up for the disconnected peers by connecting to new peers.
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
                self.send_popular_content_subscribe(peer, subscribe=True)

    def refresh_peer_list(self):
        """
        Updates the publishers and subscribers list by filtering out the disconnected peers. It also calls subscribe
        peers to replenish the available publisher slots if necessary.
        """
        peers = self.get_peers()
        self.logger.info("Num peers: %d", len(peers))
        self.publishers = set([peer for peer in self.publishers if peer in peers])
        self.subscribers = set([peer for peer in self.subscribers if peer in peers])

        # Log the number of subscribers and publishers
        self.logger.info("Publishers: %d, Subscribers: %d", len(self.publishers), len(self.subscribers))

        # subscribe peers if necessary
        self.subscribe_peers()

    def unsubscribe_peers(self):
        """
        Unsubscribes from the existing publishers by sending content subscribe request with subscribe=False. It then
        clears up its publishers list.
        - Called at community unload.
        """
        for peer in copy(self.publishers):
            self.send_popular_content_subscribe(peer, subscribe=False)
        self.publishers.clear()

    def send_popular_content_subscribe(self, peer, subscribe=True):
        """
        Method to send content subscribe/unsubscribe message. This message is sent to each individual publisher peer we
        want to subscribe/unsubscribe.
        """
        if peer not in self.get_peers():
            self.logger.error(ERROR_UNKNOWN_PEER)
            return

        # Add or remove the publisher peer
        if subscribe:
            self.publishers.add(peer)
        else:
            self.publishers.remove(peer)

        # Create subscription packet and send it
        subscription = ContentSubscription(subscribe)
        packet = self.create_message_packet(MSG_POPULAR_CONTENT_SUBSCRIBE, subscription)
        self.broadcast_message(packet, peer=peer)

    def on_popular_content_subscribe(self, source_address, data):
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
        self.send_popular_content_subscription(peer, subscribed=subscribed)

        return subscribed

    def send_popular_content_subscription(self, peer, subscribed=True):
        """
        Method to send content subscription message. Content subscription message is send in response to content
        subscribe or unsubscribe message.
        """
        if peer not in self.get_peers():
            self.logger.error(ERROR_UNKNOWN_PEER)
            return

        subscription = ContentSubscription(subscribed)
        packet = self.create_message_packet(MSG_POPULAR_CONTENT_SUBSCRIPTION, subscription)
        self.broadcast_message(packet, peer=peer)

    def on_popular_content_subscription(self, source_address, data):
        """
        Message handler for content subscription message. Content subscription message is sent by the publisher stating
        the status of the subscription in response to subscribe or unsubscribe request.

        If the subscription message has subscribe=True, it means the subscription was successful, so the peer is added
        to the subscriber. In other case, publisher is removed if it is still present in the publishers list.
        """
        auth, _, payload = self._ez_unpack_auth(ContentSubscription, data)
        peer = self.get_peer_from_auth(auth, source_address)

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

    def add_or_ignore_subscriber(self, peer):
        """
        Helper method to add or ignore new subscriber peer. If we already have max subscriber, the peer is not able to
        subscribe.
        """
        if len(self.subscribers) < MAX_SUBSCRIBERS:
            self.subscribers.add(peer)
            return True
        return False

    def get_peer_from_auth(self, auth, source_address):
        """
        Get Peer object from the message and auth and source_address.
        It is used for mocking the peer in test.
        """
        return Peer(auth.public_key_bin, source_address)

    def pack_sized(self, payload_list, fit_size, start_index=0):
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

    # Abstract methods
    def publish_next_content(self):
        pass


class PopularCommunity(PubSubCommunity):
    """
    Community for disseminating the content across the network. Follows publish-subscribe model.
    """

    master_peer = Peer(MASTER_PUBLIC_KEY.decode('hex'))

    def __init__(self, *args, **kwargs):
        self.torrent_db = kwargs.pop('torrent_db', None)
        self.channel_db = kwargs.pop('channel_db', None)
        self.trustchain = kwargs.pop('trustchain_community', None)
        self.tribler_session = kwargs.pop('session', None)

        super(PopularCommunity, self).__init__(*args, **kwargs)

        # Handles database stuffs
        self.content_repository = ContentRepository(self.torrent_db, self.channel_db)

        # Register messages
        self.decode_map.update({
            chr(MSG_TORRENT_HEALTH_RESPONSE): self.on_torrent_health_response,
            chr(MSG_CHANNEL_HEALTH_RESPONSE): self.on_channel_health_response,
            chr(MSG_TORRENT_INFO_REQUEST): self.on_torrent_info_request,
            chr(MSG_TORRENT_INFO_RESPONSE): self.on_torrent_info_response,
            chr(MSG_SEARCH_REQUEST): self.on_search_request,
            chr(MSG_SEARCH_RESPONSE): self.on_search_response,
            chr(MSG_CONTENT_INFO_REQUEST): self.on_content_info_request,
            chr(MSG_CONTENT_INFO_RESPONSE): self.on_content_info_response
        })

        self.logger.info('Popular Community initialized (peer mid %s)', self.my_peer.mid.encode('HEX'))

    @inlineCallbacks
    def unload(self):
        self.content_repository.cleanup()
        self.content_repository = None
        yield super(PopularCommunity, self).unload()

    def on_popular_content_subscribe(self, source_address, data):
        auth, _, _ = self._ez_unpack_auth(ContentSubscription, data)
        peer = self.get_peer_from_auth(auth, source_address)

        subscribed = super(PopularCommunity, self).on_popular_content_subscribe(source_address, data)
        # Publish the latest torrents to the subscriber
        if subscribed:
            self._publish_latest_torrents(peer=peer)

    def on_torrent_health_response(self, source_address, data):
        """
        Message handler for torrent health response. Torrent health response is part of periodic update message from
        the publisher. If the message was from an unknown publisher then we are not interested in it and it is simply
        dropped. In other case, a decision to accept or reject the message is made based on freshness of the message
        and the trustscore (check update_torrent in ContentRepository for the implementation).
        """
        self.logger.info("Got torrent health response from %s", source_address)
        auth, _, payload = self._ez_unpack_auth(TorrentHealthPayload, data)
        peer = self.get_peer_from_auth(auth, source_address)

        if peer not in self.publishers:
            self.logger.error(ERROR_UNKNOWN_RESPONSE)
            return

        infohash = payload.infohash
        if not self.content_repository.has_torrent(infohash):
            self.send_torrent_info_request(infohash, peer=peer)

        peer_trust = self.trustchain.get_trust(peer) if self.trustchain else 0
        self.content_repository.update_torrent_health(payload, peer_trust)

    def on_channel_health_response(self, source_address, data):
        """
        Message handler for channel health response. Currently, not sure how to handle it.
        """

    def on_torrent_info_request(self, source_address, data):
        """
        Message handler for torrent info request.
        """
        self.logger.info("Got torrent info request from %s", source_address)
        auth, _, payload = self._ez_unpack_auth(TorrentInfoRequestPayload, data)
        peer = self.get_peer_from_auth(auth, source_address)

        if peer not in self.publishers:
            self.logger.error(ERROR_UNKNOWN_RESPONSE)
            return

        self.send_torrent_info_response(str(payload.infohash), peer=peer)

    def on_torrent_info_response(self, source_address, data):
        """
        Message handler for torrent info response.
        """
        self.logger.info("Got torrent info response from %s", source_address)
        auth, _, payload = self._ez_unpack_auth(TorrentHealthPayload, data)
        peer = self.get_peer_from_auth(auth, source_address)

        if peer not in self.publishers:
            self.logger.error(ERROR_UNKNOWN_RESPONSE)
            return

        self.content_repository.update_torrent_info(payload)

    def on_search_request(self, source_address, data):
        """ Message handler for search request """
        self.logger.info("Got search request from %s", source_address)
        auth, _, payload = self._ez_unpack_auth(SearchRequestPayload, data)
        peer = self.get_peer_from_auth(auth, source_address)
        self.logger.info("Search query:%s", payload.query)
        self.logger.info("Search type:%s", "torrent" if payload.search_type == 0 else "channel")

        if payload.search_type == TORRENT_SEARCH_RESPONSE_TYPE:
            db_results = self.content_repository.search_torrent(payload.query)
            self.logger.info("Search results: torrents[%s]", len(db_results))
            self.send_search_response(peer, payload.identifier, TORRENT_SEARCH_RESPONSE_TYPE, db_results)

    def on_search_response(self, source_address, data):
        """ Message handlder for search response """
        self.logger.info("Got search response from %s", source_address)
        _, _, payload = self._ez_unpack_auth(SearchResponsePayload, data)

        # get the original search request cache
        identifier = int(payload.identifier)
        cache = self.request_cache.pop(u'request', identifier)
        if cache is None:
            return

        if payload.response_type == TORRENT_SEARCH_RESPONSE_TYPE:
            # De-serialize the response payload results to obtain individual search result items
            item_format = SearchResponseItemPayload.format_list
            (all_items, _) = self.serializer.unpack_multiple_as_list(item_format, payload.results)

            self.content_repository.update_from_torrent_search_results(all_items)
            if self.tribler_session:
                self.tribler_session.notifier.notify(SIGNAL_SEARCH_COMMUNITY, SIGNAL_ON_SEARCH_RESULTS, None, all_items)

            cache.deferred.callback(all_items)
        elif payload.response_type == CHANNEL_SEARCH_RESPONSE_TYPE:
            # De-serialize the response payload results to obtain individual search result items
            item_format = ChannelItemPayload.format_list
            (all_items, _) = self.serializer.unpack_multiple_as_list(item_format, payload.results)

            self.content_repository.update_from_channel_search_results(all_items)
            cache.deferred.callback(all_items)

    def on_content_info_request(self, source_address, data):
        auth, _, payload = self._ez_unpack_auth(ContentInfoRequest, data)
        peer = self.get_peer_from_auth(auth, source_address)

        if payload.content_type == SEARCH_TORRENT_REQUEST:
            db_results = self.content_repository.search_torrent(payload.query_list)
            self.send_content_info_response(peer, payload.identifier, SEARCH_TORRENT_RESPONSE, db_results)

    def on_content_info_response(self, source_address, data):
        _, _, payload = self._ez_unpack_auth(ContentInfoResponse, data)

        identifier = int(payload.identifier)
        if not self.request_cache.has(u'request', identifier):
            return
        cache = self.request_cache.get(u'request', identifier)

        if payload.content_type == SEARCH_TORRENT_RESPONSE:
            self.process_torrent_search_response(cache.query, payload)

        if not payload.pagination.more:
            cache = self.request_cache.pop(u'request', identifier)
            cache.finish()

    def process_torrent_search_response(self, query, payload):
        item_format = SearchResponseItemPayload.format_list
        (response, _) = self.serializer.unpack_multiple_as_list(item_format, payload.response)

        self.content_repository.update_from_torrent_search_results(response)

        result_dict = dict()
        result_dict['keywords'] = query
        result_dict['results'] = response
        result_dict['candidate'] = None

        if self.tribler_session:
            self.tribler_session.notifier.notify(SIGNAL_SEARCH_COMMUNITY, SIGNAL_ON_SEARCH_RESULTS, None,
                                                 result_dict)

    # MESSAGE SENDING FUNCTIONS

    def send_torrent_health_response(self, payload, peer=None):
        """
        Method to send torrent health response. This message is sent to all the subscribers by default but if a
        peer is specified then only that peer receives this message.
        """
        if peer and peer not in self.get_peers():
            self.logger.error(ERROR_UNKNOWN_PEER)
            return

        packet = self.create_message_packet(MSG_TORRENT_HEALTH_RESPONSE, payload)
        self.broadcast_message(packet, peer=peer)

    def send_channel_health_response(self, payload, peer=None):
        """
        Method to send channel health response. This message is sent to all the subscribers by default but if a
        peer is specified then only that peer receives this message.
        """
        if peer and peer not in self.get_peers():
            self.logger.error(ERROR_UNKNOWN_PEER)
            return

        packet = self.create_message_packet(MSG_CHANNEL_HEALTH_RESPONSE, payload)
        self.broadcast_message(packet, peer=peer)

    def send_torrent_info_request(self, infohash, peer):
        """
        Method to request information about a torrent with given infohash to a peer.
        """
        if peer not in self.get_peers():
            self.logger.error(ERROR_UNKNOWN_PEER)
            return

        info_request = TorrentInfoRequestPayload(infohash)
        packet = self.create_message_packet(MSG_TORRENT_INFO_REQUEST, info_request)
        self.broadcast_message(packet, peer=peer)

    def send_torrent_info_response(self, infohash, peer):
        """
        Method to send information about a torrent with given infohash to the requesting peer.
        """
        if peer not in self.get_peers():
            self.logger.error(ERROR_UNKNOWN_PEER)
            return

        db_torrent = self.content_repository.get_torrent(infohash)
        info_response = TorrentInfoResponsePayload(infohash, db_torrent['name'], db_torrent['length'],
                                                   db_torrent['creation_date'], db_torrent['num_files'],
                                                   db_torrent['comment'])
        packet = self.create_message_packet(MSG_TORRENT_INFO_RESPONSE, info_response)
        self.broadcast_message(packet, peer=peer)

    def send_content_info_request(self, content_type, request_list, limit=25, peer=None):
        cache = self.request_cache.add(SearchRequest(self.request_cache, content_type, request_list))
        self.logger.info("Sending search request query:%s, identifier:%s", request_list, cache.number)

        content_request = ContentInfoRequest(cache.number, content_type, request_list, limit)
        packet = self.create_message_packet(MSG_CONTENT_INFO_REQUEST, content_request)

        if peer:
            self.broadcast_message(packet, peer=peer)
        else:
            for connected_peer in self.get_peers():
                self.broadcast_message(packet, peer=connected_peer)

    def send_content_info_response(self, peer, identifier, content_type, response_list):
        num_results = len(response_list)
        current_index = 0
        page_num = 1
        while current_index < num_results:
            serialized_results, current_index, page_size = self.pack_sized(response_list, MAX_PACKET_PAYLOAD_SIZE,
                                                                           start_index=current_index)
            if not serialized_results:
                self.logger.info("Item too big probably to fit into package. Skipping it")
                current_index += 1
            else:
                pagination = Pagination(page_num, page_size, num_results, more=current_index == num_results)
                response_payload = ContentInfoResponse(identifier, content_type, serialized_results, pagination)
                packet = self.create_message_packet(MSG_CONTENT_INFO_RESPONSE, response_payload)
                self.broadcast_message(packet, peer=peer)

    def send_torrent_search_request(self, query):
        self.send_content_info_request(SEARCH_TORRENT_REQUEST, query)

    def send_channel_search_request(self, query):
        self._send_search_request(TYPE_CHANNEL, query)

    def _send_search_request(self, search_type, query):
        query = ''.join(query)
        # Register fetch identifier
        cache = self.request_cache.add(SearchRequest(self.request_cache, search_type, query))
        self.logger.info("Sending search request query:%s, identifier:%s", query, cache.number)

        # Create search request
        search_request_payload = SearchRequestPayload(cache.number, search_type, query)
        packet = self.create_message_packet(MSG_SEARCH_REQUEST, search_request_payload)

        # Send the request to search peers
        for peer in self.get_peers():
            self.broadcast_message(packet, peer=peer)

    def send_search_response(self, peer, identifier, response_type, results):
        # Serialize the results
        size = 0
        serialized_results = ''
        for item in results:
            packed_item = self.serializer.pack_multiple(item.to_pack_list())
            packed_item_length = len(packed_item)
            if size + packed_item_length > MAX_PACKET_PAYLOAD_SIZE:
                break
            else:
                size += packed_item_length
                serialized_results += packed_item

        # Prepare the payload packet and send it to the peer
        search_response_payload = SearchResponsePayload(identifier, response_type, serialized_results)
        packet = self.create_message_packet(MSG_SEARCH_RESPONSE, search_response_payload)
        self.broadcast_message(packet, peer=peer)

    # CONTENT REPOSITORY STUFFS

    def publish_next_content(self):
        """
        Publishes the next content from the queue to the subscribers.
        Does nothing if there are none subscribers.
        Only Torrent health response is published at the moment.
        """
        self.logger.info("Content to publish: %d", self.content_repository.num_content())
        if not self.subscribers:
            self.logger.info("No subscribers found. Not publishing anything")
            return

        content_type, content = self.content_repository.pop_content()
        if content_type is None:
            self.logger.error(ERROR_NO_CONTENT)
            return

        self.logger.info("Publishing content[type:%d]", content_type)
        if content_type == TYPE_TORRENT_HEALTH:
            infohash, seeders, leechers, timestamp = content
            payload = TorrentHealthPayload(infohash, seeders, leechers, timestamp)
            self.send_torrent_health_response(payload)

    def _publish_latest_torrents(self, peer):
        """
        Publishes the latest torrents in local database to the given peer.
        """
        torrents = self.content_repository.get_top_torrents()
        self.logger.info("Publishing %d torrents to peer %s", len(torrents), peer)
        for torrent in torrents:
            infohash, seeders, leechers, timestamp = torrent[:4]
            payload = TorrentHealthPayload(infohash, seeders, leechers, timestamp)
            self.send_torrent_health_response(payload, peer=peer)

    def _queue_content(self, content_type, content):
        """
        Basically addS a given content to the queue of content repository.
        """
        self.content_repository.add_content(content_type, content)
