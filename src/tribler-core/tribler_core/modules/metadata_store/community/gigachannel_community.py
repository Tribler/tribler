import json
import uuid
from binascii import unhexlify
from dataclasses import dataclass
from random import sample

from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.peerdiscovery.network import Network

from pony.orm import db_session

from tribler_common.simpledefs import CHANNELS_VIEW_UUID, NTFY

from tribler_core.modules.metadata_store.community.remote_query_community import (
    RemoteQueryCommunity,
    RemoteQueryCommunitySettings,
    SelectRequest,
)
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT
from tribler_core.modules.metadata_store.store import UNKNOWN_CHANNEL, UNKNOWN_COLLECTION, UNKNOWN_TORRENT
from tribler_core.utilities.unicode import hexlify

minimal_blob_size = 200
maximum_payload_size = 1024
max_entries = maximum_payload_size // minimal_blob_size
max_search_peers = 5

MAGIC_GIGACHAN_VERSION_MARK = b'\x01'


@vp_compile
class LegacyRemoteSelectPayload(VariablePayload):
    msg_id = 1
    format_list = ['I', 'varlenH']
    names = ['id', 'json']


@vp_compile
class LegacySelectResponsePayload(VariablePayload):
    msg_id = 2
    format_list = ['I', 'raw']
    names = ['id', 'raw_blob']


@dataclass
class GigaChannelCommunitySettings(RemoteQueryCommunitySettings):
    queried_peers_limit: int = 1000


class NonLegacyGigaChannelCommunity(RemoteQueryCommunity):
    community_id = unhexlify('dc43e3465cbd83948f30d3d3e8336d71cce33aa7')

    def create_introduction_response(self, *args, introduction=None, extra_bytes=b'', prefix=None, new_style=False):
        # ACHTUNG! We add extra_bytes here to identify the newer, 7.6+ version RemoteQuery/GigaChannel community
        # dialect, so that other 7.6+ are able to distinguish between the older and newer versions.
        return super().create_introduction_response(
            *args, introduction=introduction, extra_bytes=MAGIC_GIGACHAN_VERSION_MARK, prefix=prefix,
            new_style=new_style
        )

    def __init__(self, my_peer, endpoint, network, metadata_store, **kwargs):
        kwargs["settings"] = kwargs.get("settings", GigaChannelCommunitySettings())
        self.notifier = kwargs.pop("notifier", None)

        # ACHTUNG! We create a separate instance of Network for this community because it
        # walks aggressively and wants lots of peers, which can interfere with other communities
        super().__init__(my_peer, endpoint, Network(), metadata_store, **kwargs)

        # This set contains all the peers that we queried for subscribed channels over time.
        # It is emptied regularly. The purpose of this set is to work as a filter so we never query the same
        # peer twice. If we do, this should happen really rarely
        # TODO: use Bloom filter here instead. We actually *want* it to be all-false-positives eventually.
        self.queried_peers = set()

    def get_random_peers(self, sample_size=None):
        # Randomly sample sample_size peers from the complete list of our peers
        all_peers = self.get_peers()
        if sample_size is not None and sample_size < len(all_peers):
            return sample(all_peers, sample_size)
        return all_peers

    def introduction_response_callback(self, peer, dist, payload):
        if peer.address in self.network.blacklist or peer.mid in self.queried_peers:
            return
        if len(self.queried_peers) >= self.settings.queried_peers_limit:
            self.queried_peers.clear()
        self.queried_peers.add(peer.mid)
        self.send_remote_select_subscribed_channels(peer)

    def send_remote_select_subscribed_channels(self, peer):
        def on_packet_callback(_, processing_results):
            # We use responses for requests about subscribed channels to bump our local channels ratings
            with db_session:
                for c in [md for md, _ in processing_results if md.metadata_type == CHANNEL_TORRENT]:
                    self.mds.vote_bump(c.public_key, c.id_, peer.public_key.key_to_bin()[10:])

            # Notify GUI about the new channels
            new_channels = [md for md, result in processing_results if result == UNKNOWN_CHANNEL and md.origin_id == 0]
            if self.notifier and new_channels:
                self.notifier.notify(
                    NTFY.CHANNEL_DISCOVERED,
                    {"results": [md.to_simple_dict() for md in new_channels], "uuid": str(CHANNELS_VIEW_UUID)},
                )

        request_dict = {
            "metadata_type": [CHANNEL_TORRENT],
            "subscribed": True,
            "attribute_ranges": (("num_entries", 1, None),),
            "complete_channel": True,
        }
        self.send_remote_select(peer, **request_dict, processing_callback=on_packet_callback)

    def send_search_request(self, **kwargs):
        # Send a remote query request to multiple random peers to search for some terms
        request_uuid = uuid.uuid4()

        def notify_gui(_, processing_results):
            search_results = [
                md.to_simple_dict()
                for md, result in processing_results
                if result in (UNKNOWN_TORRENT, UNKNOWN_CHANNEL, UNKNOWN_COLLECTION)
            ]
            self.notifier.notify(NTFY.REMOTE_QUERY_RESULTS, {"uuid": str(request_uuid), "results": search_results})

        for p in self.get_random_peers(self.settings.max_query_peers):
            self.send_remote_select(p, **kwargs, processing_callback=notify_gui)

        return request_uuid


class GigaChannelCommunity(NonLegacyGigaChannelCommunity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Register legacy payload
        self.add_message_handler(LegacySelectResponsePayload, self.legacy_on_remote_select_response)

        self.new_style_peers = set()

    def legacy_send_remote_select_subscribed_channels(self, peer):
        def on_packet_callback(_, processing_results):
            # We use responses for requests about subscribed channels to bump our local channels ratings
            with db_session:
                for c in [md for md, _ in processing_results if md.metadata_type == CHANNEL_TORRENT]:
                    self.mds.vote_bump(c.public_key, c.id_, peer.public_key.key_to_bin()[10:])

            # Notify GUI about the new channels
            new_channels = [md for md, result in processing_results if result == UNKNOWN_CHANNEL and md.origin_id == 0]
            if self.notifier and new_channels:
                self.notifier.notify(
                    NTFY.CHANNEL_DISCOVERED,
                    {"results": [md.to_simple_dict() for md in new_channels], "uuid": str(CHANNELS_VIEW_UUID)},
                )

        request_dict = {
            "metadata_type": [CHANNEL_TORRENT],
            "subscribed": True,
            "attribute_ranges": (("num_entries", 1, None),),
        }
        self.legacy_send_remote_select(peer, **request_dict, processing_callback=on_packet_callback)

    def legacy_send_remote_select(self, peer, processing_callback=None, **kwargs):

        request = SelectRequest(self.request_cache, hexlify(peer.mid), kwargs, processing_callback)
        self.request_cache.add(request)

        self.logger.info(f"Select to {hexlify(peer.mid)} with ({kwargs})")
        self.ez_send(peer, LegacyRemoteSelectPayload(request.number, json.dumps(kwargs).encode('utf8')))

    @lazy_wrapper(LegacySelectResponsePayload)
    async def legacy_on_remote_select_response(self, peer, response_payload):
        """
        Match the the response that we received from the network to a query cache
        and process it by adding the corresponding entries to the MetadataStore database.
        This processes both direct responses and pushback (updates) responses
        """
        self.logger.info(f"Legacy response from {hexlify(peer.mid)}")

        # ACHTUNG! the returned request cache can be either a SelectRequest or PushbackWindow
        request = self.request_cache.get(hexlify(peer.mid), response_payload.id)
        if request is None:
            self.logger.info("No request for response")
            return

        # Check for limit on the number of packets per request
        if request.packets_limit > 1:
            request.packets_limit -= 1
        else:
            self.request_cache.pop(hexlify(peer.mid), response_payload.id)

        processing_results = await self.mds.process_compressed_mdblob_threaded(response_payload.raw_blob)
        self.logger.info(f"Response result: {processing_results}")

        # Query back the sender for preview contents for the new channels
        if self.settings.channel_query_back_enabled:
            new_channels = [md for md, result in processing_results if result in (UNKNOWN_CHANNEL, UNKNOWN_COLLECTION)]
            for channel in new_channels:
                request_dict = {
                    # FIXME: This is a dirty hack, since this is exploitable
                    "origin_id": channel.id_,
                    "first": 0,
                    "last": self.settings.max_channel_query_back,
                }
                self.legacy_send_remote_select(peer=peer, **request_dict)

        if isinstance(request, SelectRequest) and request.processing_callback:
            request.processing_callback(request, processing_results)

    def introduction_response_callback(self, peer, dist, payload):
        if peer.address in self.network.blacklist or peer.mid in self.queried_peers:
            return
        if len(self.queried_peers) >= self.settings.queried_peers_limit:
            self.new_style_peers.clear()
            self.queried_peers.clear()
        self.queried_peers.add(peer.mid)

        if not payload.extra_bytes:
            # We were introduced to a legacy peer, so send old-style channel request to it
            self.legacy_send_remote_select_subscribed_channels(peer)
        elif payload.extra_bytes == MAGIC_GIGACHAN_VERSION_MARK:
            self.send_remote_select_subscribed_channels(peer)
            self.new_style_peers.add(peer)

    def get_random_peers(self, sample_size=None):
        # Randomly sample sample_size peers from the complete list of our peers excluding legacy peers
        all_peers = set(self.get_peers()).intersection(self.new_style_peers)
        if sample_size is not None and sample_size < len(all_peers):
            return sample(all_peers, sample_size)
        return all_peers


class GigaChannelTestnetCommunity(GigaChannelCommunity):
    """
    This community defines a testnet for the giga channels, used for testing purposes.
    """

    community_id = unhexlify('ad8cece0dfdb0e03344b59a4d31a38fe9812da9d')
