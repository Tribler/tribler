from asyncio import get_event_loop
from binascii import unhexlify
from random import sample

from ipv8.community import Community
from ipv8.database import database_blob
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.peer import Peer
from ipv8.requestcache import RequestCache

from pony.orm import CacheIndexError, TransactionIntegrityError, db_session

from tribler_common.simpledefs import CHANNELS_VIEW_UUID, NTFY

from tribler_core.modules.metadata_store.community.payload import SearchRequestPayload, SearchResponsePayload
from tribler_core.modules.metadata_store.community.request import SearchRequestCache
from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import entries_to_chunk
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from tribler_core.modules.metadata_store.store import (
    GOT_NEWER_VERSION,
    UNKNOWN_CHANNEL,
    UNKNOWN_COLLECTION,
    UNKNOWN_TORRENT,
    UPDATED_OUR_VERSION,
)
from tribler_core.utilities.utilities import is_channel_public_key, is_hex_string, is_simple_match_query

minimal_blob_size = 200
maximum_payload_size = 1024
max_entries = maximum_payload_size // minimal_blob_size
max_search_peers = 5

metadata_type_to_v1_field = {
    frozenset((REGULAR_TORRENT, CHANNEL_TORRENT)): "",
    frozenset((CHANNEL_TORRENT,)): "channel",
    frozenset((REGULAR_TORRENT,)): "torrent",
}

v1_md_field_to_metadata_type = {
    "": frozenset((REGULAR_TORRENT, CHANNEL_TORRENT)),
    "channel": frozenset((CHANNEL_TORRENT,)),
    "torrent": frozenset((REGULAR_TORRENT,)),
}


@vp_compile
class RawBlobPayload(VariablePayload):
    format_list = ['raw']
    names = ['raw_blob']


def gen_have_newer_results_blob(md_list):
    with db_session:
        reply_list = [
            md
            for md, result in md_list
            if (md and (md.metadata_type == CHANNEL_TORRENT)) and (result == GOT_NEWER_VERSION)
        ]
        return entries_to_chunk(reply_list, maximum_payload_size)[0] if reply_list else None


class GigaChannelCommunity(Community):
    """
    Community to gossip around gigachannels.
    """

    community_id = unhexlify('dce2e4e31c57b7b54600251ce3bc8945ee31b7eb')

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

        self.gossip_blob = None
        self.gossip_blob_personal_channel = None

        # We regularly regenerate the gossip blobs to account for changes in the local DB
        self.register_task("Renew channel gossip cache", self.prepare_gossip_blob_cache, interval=600)

    async def unload(self):
        await self.request_cache.shutdown()
        await super(GigaChannelCommunity, self).unload()

    def _prepare_gossip_blob_cache(self):
        # Choose some random entries and try to pack them into maximum_payload_size bytes
        with db_session:
            # Generate and cache the gossip blob for the personal channel
            personal_channels = list(
                self.metadata_store.ChannelMetadata.get_my_channels().where(lambda g: g.num_entries > 0).random(1)
            )
            personal_channel = personal_channels[0] if personal_channels else None
            md_list = (
                [personal_channel] + list(personal_channel.get_random_contents(max_entries - 1))
                if personal_channel
                else None
            )
            self.gossip_blob_personal_channel = (
                entries_to_chunk(md_list, maximum_payload_size)[0] if md_list and len(md_list) > 1 else None
            )

            # Generate and cache the gossip blob for a subscribed channel
            # TODO: when the health table will be there, send popular torrents instead
            channel_l = list(
                self.metadata_store.ChannelMetadata.get_random_channels(1, only_subscribed=True, only_downloaded=True)
            )
            md_list = channel_l + list(channel_l[0].get_random_contents(max_entries - 1)) if channel_l else None
            self.gossip_blob = entries_to_chunk(md_list, maximum_payload_size)[0] if md_list else None
        self.metadata_store.disconnect_thread()

    async def prepare_gossip_blob_cache(self):
        await get_event_loop().run_in_executor(None, self._prepare_gossip_blob_cache)

    def send_random_to(self, peer):
        """
        Send random entries from our subscribed channels to another peer.

        To speed-up propagation of original content, we send two distinct packets on each walk step:
        the first packet contains user's personal channel, the second one contains a random subscribed channel.

        :param peer: the peer to send to
        :type peer: Peer
        :returns: None
        """

        # Send personal channel
        if self.gossip_blob_personal_channel:
            self.endpoint.send(
                peer.address, self.ezr_pack(self.NEWS_PUSH_MESSAGE, RawBlobPayload(self.gossip_blob_personal_channel))
            )

        # Send subscribed channel
        if self.gossip_blob:
            self.endpoint.send(peer.address, self.ezr_pack(self.NEWS_PUSH_MESSAGE, RawBlobPayload(self.gossip_blob)))

    def _update_db_with_blob(self, raw_blob):
        result = None
        try:
            with db_session:
                try:
                    result = self.metadata_store.process_compressed_mdblob(raw_blob)
                except (TransactionIntegrityError, CacheIndexError) as err:
                    self._logger.error("DB transaction error when tried to process payload: %s", str(err))
        # Unfortunately, we have to catch the exception twice, because Pony can raise them both on the exit from
        # db_session, and on calling the line of code
        except (TransactionIntegrityError, CacheIndexError) as err:
            self._logger.error("DB transaction error when tried to process payload: %s", str(err))
        finally:
            self.metadata_store.disconnect_thread()
        return result

    @lazy_wrapper(RawBlobPayload)
    async def on_blob(self, peer, blob):
        """
        Callback for when a MetadataBlob message comes in.

        :param peer: the peer that sent us the blob
        :param blob: payload raw data
        """

        def _process_received_blob():
            md_results = self._update_db_with_blob(blob.raw_blob)
            if not md_results:
                self.metadata_store.disconnect_thread()
                return None, None
            # Update votes counters
            with db_session:
                # This check ensures, in a bit hackish way, that we do not bump responses
                # sent by respond_with_updated_metadata
                if len(md_results) > 1:
                    for c in [md for md, _ in md_results if md and (md.metadata_type == CHANNEL_TORRENT)]:
                        self.metadata_store.vote_bump(c.public_key, c.id_, peer.public_key.key_to_bin()[10:])
                        # We only want to bump the leading channel entry in the payload, since the rest is content
                        break

            with db_session:
                # Get the list of new channels for notifying the GUI
                new_channels = [
                    md.to_simple_dict()
                    for md, result in md_results
                    if md
                    and md.metadata_type == CHANNEL_TORRENT
                    and result == UNKNOWN_CHANNEL
                    and md.origin_id == 0
                    and md.num_entries > 0
                ]
            result = gen_have_newer_results_blob(md_results), new_channels
            self.metadata_store.disconnect_thread()
            return result

        reply_blob, new_channels = await get_event_loop().run_in_executor(None, _process_received_blob)

        # Notify the discovered torrents and channels to the GUI
        if self.notifier and new_channels:
            self.notifier.notify(NTFY.CHANNEL_DISCOVERED, {"results": new_channels, "uuid": str(CHANNELS_VIEW_UUID)})

        # Check if the guy who send us this metadata actually has an older version of this md than
        # we do, and queue to send it back.
        self.respond_with_updated_metadata(peer, reply_blob)

    def respond_with_updated_metadata(self, peer, reply_blob):
        if reply_blob:
            self.endpoint.send(peer.address, self.ezr_pack(self.NEWS_PUSH_MESSAGE, RawBlobPayload(reply_blob)))

    def send_search_request(self, txt_filter, metadata_type=None, sort_by=None, sort_asc=0, hide_xxx=True, uuid=None):
        """
        Sends request to max_search_peers from peer list. The request is cached in request cached. The past cache is
        cleared before adding a new search request to prevent incorrect results being pushed to the GUI.
        Returns: request cache number which uniquely identifies each search request
        """
        sort_by = sort_by or "HEALTH"
        peers = self.get_peers()
        search_candidates = sample(peers, max_search_peers) if len(peers) > max_search_peers else peers
        search_request_cache = SearchRequestCache(self.request_cache, uuid, search_candidates)
        self.request_cache.clear()
        self.request_cache.add(search_request_cache)

        search_request_payload = SearchRequestPayload(
            search_request_cache.number,
            txt_filter.encode('utf8'),
            metadata_type_to_v1_field.get(metadata_type, "").encode('utf8'),  # Compatibility with v1.0
            sort_by.encode('utf8'),
            sort_asc,
            hide_xxx,
        )
        self._logger.info("Started remote search for query:%s", txt_filter)

        for peer in search_candidates:
            self.endpoint.send(peer.address, self.ezr_pack(self.SEARCH_REQUEST, search_request_payload))
        return search_request_cache.number

    @lazy_wrapper(SearchRequestPayload)
    async def on_search_request(self, peer, request):
        # Caution: beware of potential SQL injection!
        # Since this string 'txt_filter' is passed as it is to fetch the results, there could be a chance for
        # SQL injection. But since we use Pony which is supposed to be doing proper variable bindings, it should
        # be relatively safe.
        txt_filter = request.txt_filter.decode('utf8')

        # Check if the txt_filter is a simple query
        if not is_simple_match_query(txt_filter):
            self.logger.error("Dropping a complex remote search query:%s", txt_filter)
            return

        metadata_type = v1_md_field_to_metadata_type.get(
            request.metadata_type.decode('utf8'), frozenset((REGULAR_TORRENT, CHANNEL_TORRENT))
        )
        # If we get a hex-encoded public key in the txt_filter field, we drop the filter,
        # and instead query by public_key. However, we only do this if there is no channel_pk or
        # origin_id attributes set, because it is only for support of GigaChannel v1.0 channel preview requests.
        channel_pk = None
        normal_filter = txt_filter.replace('"', '').replace("*", "")
        if (
            metadata_type == frozenset((REGULAR_TORRENT, COLLECTION_NODE))
            and is_hex_string(normal_filter)
            and len(normal_filter) % 2 == 0
            and is_channel_public_key(normal_filter)
        ):
            channel_pk = database_blob(unhexlify(normal_filter))
            txt_filter = None

        request_dict = {
            "first": 1,
            "last": max_entries,
            "sort_by": request.sort_by.decode('utf8'),
            "sort_desc": not request.sort_asc if request.sort_asc is not None else None,
            "txt_filter": txt_filter,
            "hide_xxx": request.hide_xxx,
            "metadata_type": metadata_type,
            "exclude_legacy": True,
            "channel_pk": channel_pk,
        }

        def _get_search_results():
            with db_session:
                db_results = self.metadata_store.MetadataNode.get_entries(**request_dict)
                result = entries_to_chunk(db_results[:max_entries], maximum_payload_size)[0] if db_results else None
            self.metadata_store.disconnect_thread()
            return result

        result_blob = await get_event_loop().run_in_executor(None, _get_search_results)

        if result_blob:
            self.endpoint.send(
                peer.address, self.ezr_pack(self.SEARCH_RESPONSE, SearchResponsePayload(request.id, result_blob))
            )

    @lazy_wrapper(SearchResponsePayload)
    async def on_search_response(self, peer, response):
        search_request_cache = self.request_cache.get(u"remote-search-request", response.id)
        if not search_request_cache or not search_request_cache.process_peer_response(peer):
            return

        def _process_received_blob():
            md_results = self._update_db_with_blob(response.raw_blob)
            if not md_results:
                self.metadata_store.disconnect_thread()
                return None, None

            # it is incorrect to call md.simple_dict() for metadata objects from md_results
            # as previous db_session is already over, so we are going to fetch them again in a new db_session
            md_ids = [
                md.rowid for md, action in md_results
                if md
                   and (md.metadata_type in [CHANNEL_TORRENT, REGULAR_TORRENT])
                   and action in [UNKNOWN_CHANNEL, UNKNOWN_TORRENT, UPDATED_OUR_VERSION, UNKNOWN_COLLECTION]
            ]

            with db_session:
                md_list = self.metadata_store.ChannelNode.select(lambda md: md.rowid in md_ids)[:]
                result = (
                    [md.to_simple_dict() for md in md_list],
                    gen_have_newer_results_blob(md_results),
                )
            self.metadata_store.disconnect_thread()
            return result

        search_results, reply_blob = await get_event_loop().run_in_executor(None, _process_received_blob)

        if self.notifier and search_results:
            self.notifier.notify(
                NTFY.REMOTE_QUERY_RESULTS, {"uuid": search_request_cache.uuid, "results": search_results}
            )

        # Send the updated metadata if any to the responding peer
        self.respond_with_updated_metadata(peer, reply_blob)


class GigaChannelTestnetCommunity(GigaChannelCommunity):
    """
    This community defines a testnet for the giga channels, used for testing purposes.
    """

    community_id = unhexlify('f58df52d10f7339ff6e2888322011489e9ab3d59')
