from __future__ import absolute_import

from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.simpledefs import SIGNAL_ON_SEARCH_RESULTS, SIGNAL_SEARCH_COMMUNITY
from Tribler.community.popularity.constants import MSG_TORRENT_HEALTH_RESPONSE, \
    ERROR_UNKNOWN_RESPONSE, ERROR_UNKNOWN_PEER
from Tribler.community.popularity.constants import (SEARCH_TORRENT_REQUEST,
                                                    SEARCH_TORRENT_RESPONSE)
from Tribler.community.popularity.payload import (ContentInfoRequest, ContentInfoResponse, TorrentInfoRequestPayload,
                                                  TorrentInfoResponsePayload, unpack_responses)
from Tribler.community.popularity.payload import TorrentHealthPayload, ContentSubscription
from Tribler.community.popularity.pubsub import PubSubCommunity
from Tribler.community.popularity.repository import ContentRepository
from Tribler.pyipv8.ipv8.peer import Peer


class PopularityCommunity(PubSubCommunity):
    """
    Community for disseminating the content across the network. Follows publish-subscribe model.
    """
    MASTER_PUBLIC_KEY = "3081a7301006072a8648ce3d020106052b8104002703819200040504278d20d6776ce7081ad57d99fe066bb2a93" \
                        "ce7cc92405a534ef7175bab702be557d8c7d3b725ea0eb09c686e798f6c7ad85e8781a4c3b20e54c15ede38077c" \
                        "8f5c801b71d13105f261da7ddcaa94ae14bd177bf1a05a66f595b9bb99117d11f73b4c8d3dcdcdc2b3f838b8ba3" \
                        "5a9f600d2c543e8b3ba646083307b917bbbccfc53fc5ab6ded90b711d7eeda46f5f"

    master_peer = Peer(MASTER_PUBLIC_KEY.decode('hex'))

    def __init__(self, *args, **kwargs):
        self.metadata_store = kwargs.pop('metadata_store', None)
        self.tribler_session = kwargs.pop('session', None)

        super(PopularityCommunity, self).__init__(*args, **kwargs)

        self.content_repository = ContentRepository(self.metadata_store)

        self.decode_map.update({
            chr(MSG_TORRENT_HEALTH_RESPONSE): self.on_torrent_health_response
        })

        self.logger.info('Popular Community initialized (peer mid %s)', self.my_peer.mid.encode('HEX'))

    @inlineCallbacks
    def unload(self):
        self.content_repository.cleanup()
        self.content_repository = None
        yield super(PopularityCommunity, self).unload()

    def on_subscribe(self, source_address, data):
        auth, _, _ = self._ez_unpack_auth(ContentSubscription, data)
        peer = self.get_peer_from_auth(auth, source_address)

        subscribed = super(PopularityCommunity, self).on_subscribe(source_address, data)
        # Publish the latest torrents to the subscriber
        if subscribed:
            self.publish_latest_torrents(peer=peer)

    def on_torrent_health_response(self, source_address, data):
        """
        Message handler for torrent health response. Torrent health response is part of periodic update message from
        the publisher. If the message was from an unknown publisher then we are not interested in it and it is simply
        dropped. In other case, a decision to accept or reject the message is made based on freshness of the message
        and the trustscore (check update_torrent in ContentRepository for the implementation).
        """
        self.logger.debug("Got torrent health response from %s", source_address)
        auth, _, payload = self._ez_unpack_auth(TorrentHealthPayload, data)
        peer = self.get_peer_from_auth(auth, source_address)

        if peer not in self.publishers:
            self.logger.error(ERROR_UNKNOWN_RESPONSE)
            return

        infohash = payload.infohash
        if not self.content_repository.has_torrent(infohash):
            # TODO(Martijn): we should probably try to fetch the torrent info from the other peer
            return

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
        self.logger.debug("Got torrent info request from %s", source_address)
        auth, _, payload = self._ez_unpack_auth(TorrentInfoRequestPayload, data)
        peer = self.get_peer_from_auth(auth, source_address)

        if peer not in self.subscribers:
            self.logger.error(ERROR_UNKNOWN_RESPONSE)
            return

        self.send_torrent_info_response(payload.infohash, peer=peer)

    def on_torrent_info_response(self, source_address, data):
        """
        Message handler for torrent info response.
        """
        self.logger.debug("Got torrent info response from %s", source_address)
        auth, _, payload = self._ez_unpack_auth(TorrentInfoResponsePayload, data)
        peer = self.get_peer_from_auth(auth, source_address)

        if peer not in self.publishers:
            self.logger.error(ERROR_UNKNOWN_RESPONSE)
            return

        self.content_repository.update_torrent_info(payload)

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
        response = unpack_responses(payload.response)

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
            self.logger.debug(ERROR_UNKNOWN_PEER)
            return

        packet = self.create_message_packet(MSG_TORRENT_HEALTH_RESPONSE, payload)
        self.broadcast_message(packet, peer=peer)

    # CONTENT REPOSITORY STUFFS

    def publish_next_content(self):
        """
        Publishes the next content from the queue to the subscribers.
        Does nothing if there are no subscribers.
        Only Torrent health response is published at the moment.
        """
        self.logger.info("Content to publish: %d", self.content_repository.queue_length())
        if not self.subscribers:
            self.logger.info("No subscribers found. Not publishing anything")
            return

        content = self.content_repository.pop_content()
        if content:
            infohash, seeders, leechers, timestamp = content
            payload = TorrentHealthPayload(infohash, seeders, leechers, timestamp)
            self.send_torrent_health_response(payload)

    def publish_latest_torrents(self, peer):
        """
        Publishes the latest torrents in local database to the given peer.
        """
        with db_session:
            torrents = self.content_repository.get_top_torrents()
            self.logger.info("Publishing %d torrents to peer %s", len(torrents), peer)

            to_send = [TorrentHealthPayload(str(torrent.infohash), torrent.health.seeders, torrent.health.leechers,
                                            torrent.health.last_check) for torrent in torrents]
        for payload in to_send:
            self.send_torrent_health_response(payload, peer=peer)

    def queue_content(self, content):
        """
        Basically adds a given content to the queue of content repository.
        """
        self.content_repository.add_content_to_queue(content)
