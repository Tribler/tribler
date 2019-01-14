import base64
import datetime
from binascii import unhexlify

import apsw
from pony.orm import db_session
from six import text_type

from Tribler.Core.Modules.MetadataStore.OrmBindings.metadata import LEGACY_ENTRY
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url
from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto

select_channels_sql = "Select name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam " \
                      + "FROM Channels " \
                      + "WHERE nr_torrents >= 3 " \
                      + "AND name not NULL;"


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

    select_torrents_sql = "SELECT ct.channel_id, tracker_id, ct.name, t.infohash, t.length, t.creation_date, t.torrent_id, t.category, t.num_seeders, t.num_leechers, t.last_tracker_check " \
                          " FROM _ChannelTorrents ct, Torrent t, TorrentTrackerMapping mp WHERE ct.name NOT NULL and t.length>0 AND t.category NOT NULL AND ct.deleted_at IS NULL " \
                          " AND t.torrent_id == ct.torrent_id AND mp.torrent_id == t.torrent_id "

    def get_old_torrents(self, trackers, chunk_size=10000, offset=0):
        connection = apsw.Connection(self.tribler_db)
        cursor = connection.cursor()

        torrents = []
        for channel_id, tracker_id, name, infohash, length, creation_date, torrent_id, category, num_seeders, num_leechers, tracker_url in cursor.execute(
                self.select_torrents_sql + " LIMIT " + str(chunk_size) + " OFFSET " + str(offset)):
            # check if name is valid unicode data
            try:
                name = text_type(name)
            except UnicodeDecodeError:
                continue
            # num_seeders
            # num_leechers
            # last_tracker_check
            try:
                if len(base64.decodestring(infohash)) != 20:
                    continue
            except:
                continue
            infohash = base64.decodestring(infohash)

            torrents.append({
                "status": LEGACY_ENTRY,
                "infohash": infohash,
                "timestamp": torrent_id,
                "size": length,
                "torrent_date": datetime.datetime.utcfromtimestamp(creation_date),
                "title": name,
                "tags": category,
                "id_": torrent_id,
                "origin_id": 0,
                "tracker_info": trackers[tracker_id]['tracker'] if tracker_id in trackers else "",
                "public_key": database_blob(unhexlify(("%X" % channel_id).zfill(128))),
                "signature": database_blob('\x00' * 32),
                "xxx": int(category == u'xxx'),
                "skip_key_check": True})

        return torrents


if __name__ == "__main__":
    my_key = default_eccrypto.generate_key(u"curve25519")
    mds = MetadataStore(":memory:", "/tmp", my_key)
    d = DispersyToPonyMigration("/tmp/tribler.sdb", "/tmp/dispersy.sdb", mds)
    # old_channels = d.get_old_channels()
    old_trackers = d.get_old_trackers()
    with db_session:
        for t in d.get_old_torrents(old_trackers):
            mds.TorrentMetadata(**t)

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
