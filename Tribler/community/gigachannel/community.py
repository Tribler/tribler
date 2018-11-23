from time import time

from pony.orm import db_session

from Tribler.community.gigachannel.payload import TruncatedChannelPayload, TruncatedChannelPlayloadBlob
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH
from Tribler.pyipv8.ipv8.community import Community
from Tribler.pyipv8.ipv8.lazy_community import lazy_wrapper
from Tribler.pyipv8.ipv8.messaging.payload_headers import BinMemberAuthenticationPayload
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.requestcache import NumberCache, RequestCache


class ChannelDownloadCache(NumberCache):
    """
    Token for channel downloads.

    This token is held for a maximum of 10 seconds or until the current download finishes.
    """

    def __init__(self, request_cache):
        super(ChannelDownloadCache, self).__init__(request_cache, u"channel-download-cache", 0)

    @property
    def timeout_delay(self):
        return 10.0

    def on_timeout(self):
        pass


class GigaChannelCommunity(Community):
    """
    Community to gossip around gigachannels.
    """

    master_peer = Peer("3081a7301006072a8648ce3d020106052b81040027038192000400118911f5102bac4fca2d6ee5c3cb41978a4b657"
                       "e9707ce2031685c7face02bb3bf42b74a47c1d2c5f936ea2fa2324af12de216abffe01f10f97680e8fe548b82dedf"
                       "362eb29d3b074187bcfbce6869acb35d8bcef3bb8713c9e9c3b3329f59ff3546c3cd560518f03009ca57895a5421b"
                       "4afc5b90a59d2096b43eb22becfacded111e84d605a01e91a600e2b55a79d".decode('hex'))

    def __init__(self, my_peer, endpoint, network, tribler_session):
        super(GigaChannelCommunity, self).__init__(my_peer, endpoint, network)
        self.tribler_session = tribler_session
        self.download_queue = []
        self.request_cache = RequestCache()

        self.decode_map.update({
            chr(1): self.on_truncated_blob
        })

    def get_random_entries(self):
        """
        Fetch some random entries from our subscribed channels.

        :return: the truncated payloads to share with other peers
        :rtype: [TruncatedChannelPayload]
        """
        out = []
        with db_session:
            for channel in self.tribler_session.lm.mds.ChannelMetadata.get_random_channels(7):
                out.append(TruncatedChannelPayload(str(channel.infohash), str(channel.title),
                                                   str(channel.public_key[10:]), int(channel.version)))
        return out

    def send_random_to(self, peer):
        """
        Send random entries from our subscribed channels to another peer.

        :param peer: the peer to send to
        :type peer: Peer
        :returs: None
        """
        entries = self.get_random_entries()
        if entries:
            payload = TruncatedChannelPlayloadBlob(entries).to_pack_list()
            auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
            self.endpoint.send(peer.address, self._ez_pack(self._prefix, 1, [auth, payload]))

    @lazy_wrapper(TruncatedChannelPlayloadBlob)
    def on_truncated_blob(self, peer, blob):
        """
        Callback for when a TruncatedChannelPlayloadBlob message comes in.

        :param peer: the peer that sent us the blob
        :type peer: Peer
        :param blob: the truncated channel message
        :type blob: TruncatedChannelPlayloadBlob
        :returns: None
        """
        for truncated_channel in blob.payload_list:
            # The database stores the long format of the keys
            longpk = "LibNaCLPK:" + truncated_channel.public_key
            if truncated_channel.infohash not in self.download_queue:
                with db_session:
                    channel = self.tribler_session.lm.mds.ChannelMetadata.get_channel_with_id(longpk)
                    if not channel:
                        # Insert a new channel entry into the database.
                        # We set the version to 0 so that we receive the up-to-date information later.
                        self.tribler_session.lm.mds.ChannelMetadata.from_dict({
                            'infohash': truncated_channel.infohash,
                            'public_key': longpk,
                            'title': truncated_channel.title,
                            'version': 0
                        })
                        self.download_queue.append(truncated_channel.infohash)
                    elif truncated_channel.version > channel.local_version:
                        # The sent version is newer than the one we have, queue the download.
                        channel.infohash = truncated_channel.infohash
                        self.download_queue.append(truncated_channel.infohash)
                    # We don't update anything if the channel version is older than the one we know.

    def update_from_download(self, download):
        """
        Given a channel download, update the amount of votes.

        :param download: the channel download to inspect
        :type download: LibtorrentDownloadImpl
        :returns: None
        """
        infohash = download.tdef.get_infohash()
        with db_session:
            channel = self.tribler_session.lm.mds.ChannelMetadata.get_channel_with_infohash(infohash)
            if channel:
                channel.votes = download.get_num_connected_seeds_peers()[0]
            else:
                # We have an older version in our list, decide what to do with it
                my_key_hex = str(self.tribler_session.lm.mds.my_key.pub().key_to_bin()).encode('hex')
                dirname = my_key_hex[-CHANNEL_DIR_NAME_LENGTH:]
                if download.tdef.get_name() != dirname or time() - download.tdef.get_creation_date() > 604800:
                    # This is not our channel or more than a week old version of our channel: delete it
                    self.logger.debug("Removing old channel version %s", infohash.encode('hex'))
                    self.tribler_session.remove_download(download)

    def download_completed(self, download):
        """
        Callback for when a channel download finished.

        :param download: the channel download which completed
        :type download: LibtorrentDownloadImpl
        :returns: None
        """
        if self.request_cache.has(u"channel-download-cache", 0):
            self.request_cache.pop(u"channel-download-cache", 0)
        self.update_from_download(download)

    def update_states(self, states_list):
        """
        Callback for when the download states are updated in Tribler.
        We still need to filter out the channel downloads from this list.

        :param states_list: the list of download states
        :type states_list: [DownloadState]
        :returns: None
        """
        for ds in states_list:
            if ds.get_download().dlconfig.get('download_defaults', 'channel_download'):
                self.update_from_download(ds.get_download())

    def fetch_next(self):
        """
        If we have nothing to process right now, start downloading a new channel.

        :returns: None
        """
        if self.request_cache.has(u"channel-download-cache", 0):
            return
        if self.download_queue:
            infohash = self.download_queue.pop(0)
            if not self.tribler_session.has_download(infohash):
                self._logger.info("Starting channel download with infohash %s", infohash.encode('hex'))
                # Reserve the token
                self.request_cache.add(ChannelDownloadCache(self.request_cache))
                # Start downloading this channel
                with db_session:
                    channel = self.tribler_session.lm.mds.ChannelMetadata.get_channel_with_infohash(infohash)
                finished_deferred = self.tribler_session.lm.download_channel(channel)[1]
                finished_deferred.addCallback(self.download_completed)


class GigaChannelTestnetCommunity(GigaChannelCommunity):
    """
    This community defines a testnet for the giga channels, used for testing purposes.
    """
    master_peer = Peer("3081a7301006072a8648ce3d020106052b8104002703819200040726f5b6558151e1b82c3d30c08175c446f5f696b"
                       "e9b005ee23050fe55f7e4f73c1b84bf30eb0a254c350705f89369ba2c6b6795a50f0aa562b3095bfa8aa069747221"
                       "c0fb92e207052b7d03fa8a76e0b236d74ac650de37e5dfa02cbd6b9fe2146147f3555bfa7410b9c499a8ec49a80ac"
                       "84b433fb2bf1740a15e96a5bad2b90b0488bdc791633ee7d829dcd583ee5f".decode('hex'))
