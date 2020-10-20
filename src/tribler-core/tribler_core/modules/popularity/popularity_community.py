import random
from binascii import unhexlify

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper

from pony.orm import db_session

from tribler_common.simpledefs import NTFY

from tribler_core.modules.popularity.payload import TorrentsHealthPayload
from tribler_core.utilities.unicode import hexlify

PUBLISH_INTERVAL = 5


class PopularityCommunity(Community):
    """
    Community for disseminating the content across the network. Follows publish-subscribe model.
    """
    community_id = unhexlify('9aca62f878969c437da9844cba29a134917e1648')

    def __init__(self, *args, **kwargs):
        self.metadata_store = kwargs.pop('metadata_store')
        self.torrent_checker = kwargs.pop('torrent_checker', None)
        self.notifier = kwargs.pop('notifier', None)

        super(PopularityCommunity, self).__init__(*args, **kwargs)

        self.add_message_handler(TorrentsHealthPayload, self.on_torrents_health)

        self.logger.info('Popularity Community initialized (peer mid %s)', hexlify(self.my_peer.mid))
        self.register_task("publish", self.gossip_torrents_health, interval=PUBLISH_INTERVAL)

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
        self.logger.info(
            f'Gossip torrent health information for {len(random_torrents_checked)}'
            f' random torrents and {len(popular_torrents_checked)} checked torrents', )
        self.ez_send(random_peer, TorrentsHealthPayload.create(random_torrents_checked, popular_torrents_checked))

    @lazy_wrapper(TorrentsHealthPayload)
    async def on_torrents_health(self, peer, payload):
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
                    self.logger.info(f"{hexlify(infohash)} updated ({seeders},{leechers})")
                elif not torrent_state:
                    self.metadata_store.TorrentState(infohash=infohash, seeders=seeders,
                                                     leechers=leechers, last_check=last_check)
                    self.logger.info(f"{hexlify(infohash)} added ({seeders},{leechers})")
                    if self.notifier:
                        self.notifier.notify(NTFY.POPULARITY_COMMUNITY_ADD_UNKNOWN_TORRENT, peer, infohash)
