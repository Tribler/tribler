from __future__ import absolute_import

from binascii import unhexlify

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload
from ipv8.peer import Peer
from ipv8.requestcache import RequestCache

from pony.orm import CacheIndexError, TransactionIntegrityError, db_session

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import entries_to_chunk
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, REGULAR_TORRENT
from Tribler.Core.Modules.MetadataStore.store import (
    GOT_NEWER_VERSION, UNKNOWN_CHANNEL, UNKNOWN_TORRENT, UPDATED_OUR_VERSION)
from Tribler.Core.Utilities.utilities import is_simple_match_query
from Tribler.Core.simpledefs import (
    NTFY_CHANNEL, NTFY_DISCOVERED, SIGNAL_GIGACHANNEL_COMMUNITY, SIGNAL_ON_SEARCH_RESULTS)
from Tribler.community.gigachannel.payload import SearchRequestPayload, SearchResponsePayload
from Tribler.community.gigachannel.request import SearchRequestCache

minimal_blob_size = 200
maximum_payload_size = 1024
max_entries = maximum_payload_size // minimal_blob_size
max_search_peers = 5


class RawBlobPayload(VariablePayload):
    format_list = ['raw']
    names = ['raw_blob']


class GigaChannelCommunity(Community):
    """
    Community to gossip around gigachannels.
    """

    master_peer = Peer(unhexlify("4c69624e61434c504b3ab5791362b5e98090310c10194e7406a553134e3e2f88bcc5c8a2e1dd249d323"
                                 "ebb20ca9528cb8b1b0db890ef876589a6d6ba80ded85e5ebab33acd57c8ead9db"))

    NEWS_PUSH_MESSAGE = 1
    SEARCH_REQUEST = 2
    SEARCH_RESPONSE = 3

    def __init__(self, my_peer, endpoint, network, metadata_store, notifier=None):
        super(GigaChannelCommunity, self).__init__(my_peer, endpoint, network)
        self.metadata_store = metadata_store
        self.add_message_handler(self.NEWS_PUSH_MESSAGE, self.on_blob)
        self.add_message_handler(self.SEARCH_REQUEST, self.on_search_request)
        self.add_message_handler(self.SEARCH_RESPONSE, self.on_search_response)
        self.request_cache = RequestCache()
        self.notifier = notifier

    @inlineCallbacks
    def unload(self):
        self.request_cache.clear()
        yield super(GigaChannelCommunity, self).unload()

    def send_random_to(self, peer):
        """
        Send random entries from our subscribed channels to another peer.

        :param peer: the peer to send to
        :type peer: Peer
        :returns: None
        """
        # Choose some random entries and try to pack them into maximum_payload_size bytes
        md_list = []
        with db_session:
            # TODO: when the health table will be there, send popular torrents instead
            channel_l = list(
                self.metadata_store.ChannelMetadata.get_random_channels(1, only_subscribed=True, only_downloaded=True))
            if not channel_l:
                return
            md_list.extend(channel_l + list(channel_l[0].get_random_torrents(max_entries - 1)))
            blob = entries_to_chunk(md_list, maximum_payload_size)[0] if md_list else None
        self.endpoint.send(peer.address, self.ezr_pack(self.NEWS_PUSH_MESSAGE, RawBlobPayload(blob)))

    @lazy_wrapper(RawBlobPayload)
    def on_blob(self, peer, blob):
        """
        Callback for when a MetadataBlob message comes in.

        :param peer: the peer that sent us the blob
        :param blob: payload raw data
        """
        try:
            with db_session:
                try:
                    md_list = self.metadata_store.process_compressed_mdblob(blob.raw_blob)
                except (TransactionIntegrityError, CacheIndexError) as err:
                    self._logger.error("DB transaction error when tried to process payload: %s", str(err))
                    return
        # Unfortunately, we have to catch the exception twice, because Pony can raise them both on the exit from
        # db_session, and on calling the line of code
        except (TransactionIntegrityError, CacheIndexError) as err:
            self._logger.error("DB transaction error when tried to process payload: %s", str(err))
            return

        # Update votes counters
        with db_session:
            # This check ensures, in a bit hackish way, that we do not bump responses
            # sent by respond_with_updated_metadata
            # TODO: make the bump decision based on packet type instead when we switch to nested channels!
            if len(md_list) > 1:
                for c in [md for md, _ in md_list if md and (md.metadata_type == CHANNEL_TORRENT)]:
                    self.metadata_store.vote_bump(c.public_key, c.id_, peer.public_key.key_to_bin()[10:])
                    break  # We only want to bump the leading channel entry in the payload, since the rest is content

        # Notify the discovered torrents and channels to the GUI
        self.notify_discovered_metadata(md_list)

        # Check if the guy who send us this metadata actually has an older version of this md than
        # we do, and queue to send it back.
        self.respond_with_updated_metadata(peer, md_list)

    def respond_with_updated_metadata(self, peer, md_list):
        """
        Responds the peer with the updated metadata if present in the metadata list.
        :param peer: responding peer
        :param md_list: Metadata list
        :return: None
        """
        with db_session:
            reply_list = [md for md, result in md_list if
                          (md and (md.metadata_type == CHANNEL_TORRENT)) and (result == GOT_NEWER_VERSION)]
            reply_blob = entries_to_chunk(reply_list, maximum_payload_size)[0] if reply_list else None
        if reply_blob:
            self.endpoint.send(peer.address, self.ezr_pack(self.NEWS_PUSH_MESSAGE, RawBlobPayload(reply_blob)))

    def notify_discovered_metadata(self, md_list):
        """
        Notify about the discovered metadata through event notifier.
        :param md_list: Metadata list
        :return: None
        """
        with db_session:
            new_channels = [(dict(type='channel', **(md.to_simple_dict()))) for md, result in md_list
                            if md and md.metadata_type == CHANNEL_TORRENT and result == UNKNOWN_CHANNEL]

        if self.notifier and new_channels:
            self.notifier.notify(NTFY_CHANNEL, NTFY_DISCOVERED, None, {"results": new_channels})

    def send_search_request(self, query_filter, metadata_type='', sort_by=None, sort_asc=0, hide_xxx=True, uuid=None):
        """
        Sends request to max_search_peers from peer list. The request is cached in request cached. The past cache is
        cleared before adding a new search request to prevent incorrect results being pushed to the GUI.
        Returns: request cache number which uniquely identifies each search request
        """
        sort_by = sort_by or "HEALTH"
        search_candidates = self.get_peers()[:max_search_peers]
        search_request_cache = SearchRequestCache(self.request_cache, uuid, search_candidates)
        self.request_cache.clear()
        self.request_cache.add(search_request_cache)

        search_request_payload = SearchRequestPayload(search_request_cache.number, query_filter.encode('utf8'),
                                                      metadata_type, sort_by, sort_asc, hide_xxx)
        self._logger.info("Started remote search for query:%s", query_filter)

        for peer in search_candidates:
            self.endpoint.send(peer.address, self.ezr_pack(self.SEARCH_REQUEST, search_request_payload))
        return search_request_cache.number

    @lazy_wrapper(SearchRequestPayload)
    def on_search_request(self, peer, request):
        # Caution: SQL injection
        # Since this string 'query_filter' is passed as it is to fetch the results, there could be a chance for
        # SQL injection. But since we use pony which is supposed to be doing proper variable bindings, it should
        # be relatively safe
        query_filter = request.query_filter.decode('utf8')
        # Check if the query_filter is a simple query
        if not is_simple_match_query(query_filter):
            self.logger.error("Dropping a complex remote search query:%s", query_filter)
            return

        metadata_type = {
            "": [REGULAR_TORRENT, CHANNEL_TORRENT],
            "channel": CHANNEL_TORRENT,
            "torrent": REGULAR_TORRENT
        }.get(request.metadata_type, REGULAR_TORRENT)

        request_dict = {
            "first": 1,
            "last": max_entries,
            "sort_by": request.sort_by,
            "sort_asc": request.sort_asc,
            "query_filter": query_filter,
            "hide_xxx": request.hide_xxx,
            "metadata_type": metadata_type,
            "exclude_legacy": True
        }

        result_blob = None
        with db_session:
            db_results, total = self.metadata_store.TorrentMetadata.get_entries(**request_dict)
            if total > 0:
                result_blob = entries_to_chunk(db_results[:max_entries], maximum_payload_size)[0]
        if result_blob:
            self.endpoint.send(peer.address, self.ezr_pack(self.SEARCH_RESPONSE,
                                                           SearchResponsePayload(request.id, result_blob)))

    @lazy_wrapper(SearchResponsePayload)
    def on_search_response(self, peer, response):
        search_request_cache = self.request_cache.get(u"remote-search-request", response.id)
        if not search_request_cache or not search_request_cache.process_peer_response(peer):
            return

        with db_session:
            try:
                metadata_result = self.metadata_store.process_compressed_mdblob(response.raw_blob)
            except (TransactionIntegrityError, CacheIndexError) as err:
                self._logger.error("DB transaction error when tried to process search payload: %s", str(err))
                return

            search_results = [(dict(type={REGULAR_TORRENT: 'torrent', CHANNEL_TORRENT: 'channel'}[md.metadata_type],
                                    **(md.to_simple_dict()))) for (md, action) in metadata_result if
                              (md and (md.metadata_type == CHANNEL_TORRENT or md.metadata_type == REGULAR_TORRENT) and
                               action in [UNKNOWN_CHANNEL, UNKNOWN_TORRENT, UPDATED_OUR_VERSION])]
        if self.notifier and search_results:
            self.notifier.notify(SIGNAL_GIGACHANNEL_COMMUNITY, SIGNAL_ON_SEARCH_RESULTS, None,
                                 {"uuid": search_request_cache.uuid, "results": search_results})

        # Send the updated metadata if any to the responding peer
        self.respond_with_updated_metadata(peer, metadata_result)


class GigaChannelTestnetCommunity(GigaChannelCommunity):
    """
    This community defines a testnet for the giga channels, used for testing purposes.
    """
    master_peer = Peer(unhexlify("4c69624e61434c504b3afbd79020aa61795d1186ea505cf80fe2ac7f42dfc32b830ebade5d78479cbb4"
                                 "35bdbfda7b04e156f5515d1b0bbdafa5c67279e25937201ef6b31f7eeded20423"))
