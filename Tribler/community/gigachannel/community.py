from binascii import unhexlify

from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import entries_to_chunk
from Tribler.pyipv8.ipv8.community import Community
from Tribler.pyipv8.ipv8.lazy_community import PacketDecodingError
from Tribler.pyipv8.ipv8.messaging.payload_headers import BinMemberAuthenticationPayload
from Tribler.pyipv8.ipv8.peer import Peer


class GigaChannelCommunity(Community):
    """
    Community to gossip around gigachannels.
    """

    master_peer = Peer(unhexlify("3081a7301006072a8648ce3d020106052b8104002703819200040448a078b597b62d3761a061872cd86"
                                 "10f58cb513f1dc21e66dd59f1e01d582f633b182d9ca6e5859a9a34e61eb77b768e5e9202f642fd50c6"
                                 "0b89d8d8b0bdc355cdf8caac262f6707c80da00b1bcbe7bf91ed5015e5163a76a2b2e630afac96925f5"
                                 "daa8556605043c6da4db7d26113cba9f9cbe63fddf74625117598317e05cb5b8cbd606d0911683570ad"
                                 "bb921c91"))

    def __init__(self, my_peer, endpoint, network, metadata_store):
        super(GigaChannelCommunity, self).__init__(my_peer, endpoint, network)
        self.metadata_store = metadata_store

        self.decode_map.update({
            chr(1): self.on_blob
        })

    def send_random_to(self, peer):
        """
        Send random entries from our subscribed channels to another peer.

        :param peer: the peer to send to
        :type peer: Peer
        :returns: None
        """
        minimal_blob_size = 200
        maximum_payload_size = 1024
        max_entries = maximum_payload_size / minimal_blob_size

        # Choose some random entries and try to pack them into maximum_payload_size bytes
        md_list = []
        with db_session:
            # TODO: when the health table will be there, send popular torrents instead
            channel_l = self.metadata_store.ChannelMetadata.get_random_channels(1, only_subscribed=True)[:]
            if not channel_l:
                return
            channel = channel_l[0]
            md_list.append(channel)
            md_list.extend(list(channel.get_random_torrents(max_entries - 1)))
            blob = entries_to_chunk(md_list, maximum_payload_size)[0] if md_list else None

        # Send chosen entries to peer
        if md_list:
            auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
            ersatz_payload = [('raw', blob)]
            self.endpoint.send(peer.address, self._ez_pack(self._prefix, 1, [auth, ersatz_payload]))

    def on_blob(self, source_address, data):
        """
        Callback for when a MetadataBlob message comes in.

        :param source_address: the peer that sent us the blob
        :param data: payload raw data
        """
        auth, remainder = self.serializer.unpack_to_serializables([BinMemberAuthenticationPayload, ], data[23:])
        signature_valid, remainder = self._verify_signature(auth, data)
        blob = remainder[23:]

        if not signature_valid:
            raise PacketDecodingError("Incoming packet %s has an invalid signature" % str(self.__class__))
        self.metadata_store.process_compressed_mdblob(blob)


class GigaChannelTestnetCommunity(GigaChannelCommunity):
    """
    This community defines a testnet for the giga channels, used for testing purposes.
    """
    master_peer = Peer(unhexlify("3081a7301006072a8648ce3d020106052b81040027038192000401b9f303778e7727b35a4c26487481f"
                                 "a7011e252cc4a6f885f3756bd8898c9620cf1c32e79dd5e75ae277a56702a47428ce47676d005e262fa"
                                 "fd1a131a2cb66be744d52cb1e0fca503658cb3368e9ebe232e7b8c01e3172ebfdb0620b316467e5b2c4"
                                 "c6809565cf2142e8d4322f66a3d13a8c4bb18059c9ed97975a97716a085a93e3e62b0387e63f0bf389a"
                                 "0e9bffe6"))
