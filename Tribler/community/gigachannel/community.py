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

    master_peer = Peer("3081a7301006072a8648ce3d020106052b81040027038192000400118911f5102bac4fca2d6ee5c3cb41978a4b657"
                       "e9707ce2031685c7face02bb3bf42b74a47c1d2c5f936ea2fa2324af12de216abffe01f10f97680e8fe548b82dedf"
                       "362eb29d3b074187bcfbce6869acb35d8bcef3bb8713c9e9c3b3329f59ff3546c3cd560518f03009ca57895a5421b"
                       "4afc5b90a59d2096b43eb22becfacded111e84d605a01e91a600e2b55a79d".decode('hex'))

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
            channel_l = self.metadata_store.ChannelMetadata.get_random_subscribed_channels(1)[:]
            if not channel_l:
                return
            channel = channel_l[0]
            # TODO: when the health table will be there, send popular torrents instead
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
        self.metadata_store.process_squashed_mdblob(blob)


class GigaChannelTestnetCommunity(GigaChannelCommunity):
    """
    This community defines a testnet for the giga channels, used for testing purposes.
    """
    master_peer = Peer("3081a7301006072a8648ce3d020106052b8104002703819200040726f5b6558151e1b82c3d30c08175c446f5f696b"
                       "e9b005ee23050fe55f7e4f73c1b84bf30eb0a254c350705f89369ba2c6b6795a50f0aa562b3095bfa8aa069747221"
                       "c0fb92e207052b7d03fa8a76e0b236d74ac650de37e5dfa02cbd6b9fe2146147f3555bfa7410b9c499a8ec49a80ac"
                       "84b433fb2bf1740a15e96a5bad2b90b0488bdc791633ee7d829dcd583ee5f".decode('hex'))
