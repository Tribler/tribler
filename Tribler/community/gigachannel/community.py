from __future__ import absolute_import

from binascii import unhexlify

from pony.orm import db_session, TransactionIntegrityError, CacheIndexError

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import entries_to_chunk
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT
from Tribler.Core.Modules.MetadataStore.store import GOT_NEWER_VERSION
from Tribler.pyipv8.ipv8.community import Community
from Tribler.pyipv8.ipv8.lazy_community import lazy_wrapper
from Tribler.pyipv8.ipv8.messaging.lazy_payload import VariablePayload
from Tribler.pyipv8.ipv8.peer import Peer

minimal_blob_size = 200
maximum_payload_size = 1024
max_entries = maximum_payload_size // minimal_blob_size


class RawBlobPayload(VariablePayload):
    format_list = ['raw']
    names = ['raw_blob']


class GigaChannelCommunity(Community):
    """
    Community to gossip around gigachannels.
    """

    master_peer = Peer(unhexlify("3081a7301006072a8648ce3d020106052b8104002703819200040448a078b597b62d3761a061872cd86"
                                 "10f58cb513f1dc21e66dd59f1e01d582f633b182d9ca6e5859a9a34e61eb77b768e5e9202f642fd50c6"
                                 "0b89d8d8b0bdc355cdf8caac262f6707c80da00b1bcbe7bf91ed5015e5163a76a2b2e630afac96925f5"
                                 "daa8556605043c6da4db7d26113cba9f9cbe63fddf74625117598317e05cb5b8cbd606d0911683570ad"
                                 "bb921c91"))

    NEWS_PUSH_MESSAGE = 1

    def __init__(self, my_peer, endpoint, network, metadata_store):
        super(GigaChannelCommunity, self).__init__(my_peer, endpoint, network)
        self.metadata_store = metadata_store
        self.add_message_handler(self.NEWS_PUSH_MESSAGE, self.on_blob)

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
            channel_l = list(self.metadata_store.ChannelMetadata.get_random_channels(1, only_subscribed=True))
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
                except RuntimeError:
                    return
                except (TransactionIntegrityError, CacheIndexError) as err:
                    self._logger.error("DB transaction error when tried to process payload: %s", str(err))
                    return
        # Unfortunately, we have to catch the exception twice, because Pony can raise them both on the exit from
        # db_session, and on calling the line of code
        except (TransactionIntegrityError, CacheIndexError) as err:
            self._logger.error("DB transaction error when tried to process payload: %s", str(err))
            return

        # Check if the guy who send us this metadata actually has an older version of this md than
        # we do, and queue to send it back.
        with db_session:
            reply_list = [md for md, result in md_list if
                          (md and (md.metadata_type == CHANNEL_TORRENT)) and (result == GOT_NEWER_VERSION)]
            reply_blob = entries_to_chunk(reply_list, maximum_payload_size)[0] if reply_list else None
        if reply_blob:
            self.endpoint.send(peer.address, self.ezr_pack(self.NEWS_PUSH_MESSAGE, RawBlobPayload(reply_blob)))


class GigaChannelTestnetCommunity(GigaChannelCommunity):
    """
    This community defines a testnet for the giga channels, used for testing purposes.
    """
    master_peer = Peer(unhexlify("3081a7301006072a8648ce3d020106052b81040027038192000401b9f303778e7727b35a4c26487481f"
                                 "a7011e252cc4a6f885f3756bd8898c9620cf1c32e79dd5e75ae277a56702a47428ce47676d005e262fa"
                                 "fd1a131a2cb66be744d52cb1e0fca503658cb3368e9ebe232e7b8c01e3172ebfdb0620b316467e5b2c4"
                                 "c6809565cf2142e8d4322f66a3d13a8c4bb18059c9ed97975a97716a085a93e3e62b0387e63f0bf389a"
                                 "0e9bffe6"))
