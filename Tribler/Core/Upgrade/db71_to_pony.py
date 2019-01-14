import re
import urlparse
from binascii import unhexlify

import apsw

from Tribler.Core.Modules.MetadataStore.OrmBindings.metadata import LEGACY_ENTRY
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url, parse_tracker_url
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto

select_channels_sql = "Select name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam " \
                      + "FROM Channels " \
                      + "WHERE nr_torrents >= 3 " \
                      + "AND name not NULL;"

select_torrents_sql = "SELECT dispersy_cid, infohash, timestamp"


class DispersyToPonyMigration(object):

    def __init__(self, tribler_db, dispersy_db, metadata_store):
        self.tribler_db = tribler_db
        self.dispersy_db = dispersy_db
        self.mds = metadata_store

    def get_old_channels(self):
        connection = apsw.Connection(self.tribler_db)
        cursor = connection.cursor()

        channels = []
        for channel_id, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam in cursor.execute(
                select_channels_sql):
            channels.append({"old_id": channel_id,
                             "title": name,
                             "public_key": dispersy_cid,
                             "timestamp": modified,
                             "version": nr_torrents,
                             "votes": nr_favorite,
                             "xxx": nr_spam})
        return channels

    select_trackers_sql = "select tracker_id, tracker, last_check, failures, is_alive from TrackerInfo"

    def get_old_trackers(self):
        connection = apsw.Connection(self.tribler_db)
        cursor = connection.cursor()

        trackers = {}
        for tracker_id, tracker, last_check, failures, is_alive in cursor.execute(self.select_trackers_sql):
            try:
                tracker_url_sanitized = get_uniformed_tracker_url(tracker)
                if not tracker_url_sanitized:
                    continue
            except:
                # Skip malformed trackers
                continue
            trackers[tracker_id] = ({"tracker": tracker_url_sanitized,
                                     "last_check": last_check,
                                     "failures": failures,
                                     "is_alive": is_alive})
        return trackers

    def get_old_torrents(self):
        connection = apsw.Connection(self.tribler_db)
        cursor = connection.cursor()

        torrents = []
        for infohash, length, creation_date, name, dispersy_cid, torrent_id, category, num_seeders, num_leechers, tracker_url in cursor.execute(
                select_channels_sql):
            # num_seeders
            # num_leechers
            # last_tracker_check
            torrents.append({
                "status": LEGACY_ENTRY,
                "infohash": unhexlify(infohash),
                "timestamp": 0,
                "size": length,
                "torrent_date": creation_date,
                "title": name,
                "tags": category,
                "tracker_info": tracker_url,
                "id_": torrent_id,
                "origin_id": 0,
                "public_key": dispersy_cid,
                "signature": 0,
                "xxx": int(category == u'xxx')})
            return torrents


if __name__ == "__main__":
    my_key = default_eccrypto.generate_key(u"curve25519")
    mds = MetadataStore(":memory:", "/tmp", my_key)
    d = DispersyToPonyMigration("/tmp/tribler.sdb", "/tmp/dispersy.sdb", mds)
    # old_channels = d.get_old_channels()
    d.get_old_trackers()

"""
select Torrent.infohash, Torrent.length, Torrent.name, Torrent.creation_date, ChannelTorrents.torrent_id, Torrent.category
from ChannelTorrents, Channels, Torrent
where ChannelTorrents.torrent_id = Torrent.torrent_id AND Channels.id = ChannelTorrents.channel_id 
select Torrent.infohash, Torrent.num_seeders, Torrent.num_leechers, Torrent.last_tracker_check
from ChannelTorrents, Channels, Torrent
where ChannelTorrents.torrent_id = Torrent.torrent_id AND Channels.id = ChannelTorrents.channel_id

"""

# 1 - Move Trackers (URLs)
# 2 - Move torrent Infohashes
# 3 - Move Infohash-Tracker relationships
# 4 - Move Metadata, based on Infohashes
# 5 - Move Channels
