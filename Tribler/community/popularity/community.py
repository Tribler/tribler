from __future__ import absolute_import

import random
from binascii import hexlify, unhexlify

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.payload_headers import BinMemberAuthenticationPayload
from ipv8.peer import Peer

from pony.orm import db_session

from twisted.internet.task import LoopingCall

from Tribler.community.popularity.payload import TorrentsHealthPayload


PUBLISH_INTERVAL = 5

MSG_TORRENTS_HEALTH = 1


class PopularityCommunity(Community):
    """
    Community for disseminating the content across the network. Follows publish-subscribe model.
    """
    MASTER_PUBLIC_KEY = ("4c69624e61434c504b3a4fcd9aa5256e8859d38509dd53ab93e70b351ac770817acfdccd836cf766ee345ea"
                         "5c7f6659cc410f3447bafaec8472c40032984d197ffd565903c6e799570bc")

    master_peer = Peer(unhexlify(MASTER_PUBLIC_KEY))

    def __init__(self, *args, **kwargs):
        self.metadata_store = kwargs.pop('metadata_store')
        self.torrent_checker = kwargs.pop('torrent_checker', None)

        super(PopularityCommunity, self).__init__(*args, **kwargs)

        self.decode_map.update({
            chr(MSG_TORRENTS_HEALTH): self.on_torrents_health
        })

        self.logger.info('Popularity Community initialized (peer mid %s)', hexlify(self.my_peer.mid))
        self.publish_lc = self.register_task("publish", LoopingCall(self.gossip_torrents_health))
        self.publish_lc.start(PUBLISH_INTERVAL, now=False)

    @db_session
    def gossip_torrents_health(self):
        """
        Gossip torrent health information to another peer.
        """
        if not self.get_peers() or not self.torrent_checker:
            return

        num_torrents_checked = len(self.torrent_checker.torrents_checked)
        random_torrents_checked = random.sample(self.torrent_checker.torrents_checked, min(num_torrents_checked, 5))
        popular_torrents_checked = sorted(self.torrent_checker.torrents_checked - set(random_torrents_checked),
                                          key=lambda tup: tup[1], reverse=True)[:5]

        random_peer = random.choice(self.get_peers())

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = TorrentsHealthPayload(random_torrents_checked, popular_torrents_checked).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_TORRENTS_HEALTH, [auth, payload])
        self.endpoint.send(random_peer.address, packet)

    @lazy_wrapper(TorrentsHealthPayload)
    def on_torrents_health(self, _, payload):
        self.logger.info("Received torrent health information for %d random torrents and %d checked torrents",
                         len(payload.random_torrents), len(payload.torrents_checked))

        all_torrents = payload.random_torrents + payload.torrents_checked
        with db_session:
            for infohash, seeders, leechers, last_check in all_torrents:
                torrent_state = self.metadata_store.TorrentState.get(infohash=infohash)
                if torrent_state and last_check > torrent_state.last_check:
                    # Replace current information
                    torrent_state.seeders = seeders
                    torrent_state.leechers = leechers
                    torrent_state.last_check = last_check
                elif not torrent_state:
                    _ = self.metadata_store.TorrentState(infohash=infohash, seeders=seeders,
                                                         leechers=leechers, last_check=last_check)
