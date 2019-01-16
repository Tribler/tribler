import base64
import datetime
import os
from binascii import unhexlify

import apsw
from pony import orm
from pony.orm import db_session
from six import text_type

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import LEGACY_ENTRY
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url
from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


class DispersyToPonyMigration(object):

    def __init__(self, tribler_db, dispersy_db, metadata_store):
        self.tribler_db = tribler_db
        self.dispersy_db = dispersy_db
        self.mds = metadata_store


    def dispesy_cid_to_pk(self, dispersy_cid):
        return database_blob(unhexlify(("%X" % dispersy_cid).zfill(128)))

    def pseudo_signature(self):
        return database_blob('\x00' * 32)

    def final_timestamp(self):
        return 1 << 62

    select_channels_sql = "Select id, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam " \
                          + "FROM Channels " \
                          + "WHERE nr_torrents >= 3 " \
                          + "AND name not NULL;"

    def get_old_channels(self):
        connection = apsw.Connection(self.tribler_db)
        cursor = connection.cursor()

        channels = []
        for id_, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam in cursor.execute(
                self.select_channels_sql):
            if nr_torrents and nr_torrents > 0:
                channels.append({"id_": 0,
                                 "infohash": database_blob(os.urandom(20)),
                                 "title": name or '',
                                 "public_key": self.dispesy_cid_to_pk(id_),
                                 "timestamp": self.final_timestamp(),
                                 "votes": int(nr_favorite or 0),
                                 "xxx": float(nr_spam or 0),
                                 "origin_id": 0,
                                 "signature": self.pseudo_signature(),
                                 "skip_key_check": True,
                                 "size": 0,
                                 "local_version": self.final_timestamp(),
                                 "subscribed": False,
                                 "status": LEGACY_ENTRY,
                                 "num_entries": int(nr_torrents or 0)})
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

    select_torrents_sql = "SELECT ti.tracker, ct.channel_id, ct.name, t.infohash, t.length, t.creation_date, t.torrent_id, t.category, t.num_seeders, t.num_leechers, t.last_tracker_check " + \
                          " FROM _ChannelTorrents ct, Torrent t, TorrentTrackerMapping mp, TrackerInfo ti WHERE ct.name NOT NULL and t.length>0 AND t.category NOT NULL AND ct.deleted_at IS NULL " + \
                          " AND t.torrent_id == ct.torrent_id AND t.infohash NOT NULL AND mp.torrent_id == t.torrent_id AND ti.tracker_id == mp.tracker_id AND ti.tracker!='DHT' AND ti.tracker!='no-DHT' group by infohash ORDER BY ti.is_alive desc, ti.failures, ti.last_check desc "

    def get_old_torrents(self, chunk_size=10000, offset=0):
        connection = apsw.Connection(self.tribler_db)
        cursor = connection.cursor()

        torrents = []
        health = []
        for tracker_url, channel_id, name, infohash, length, creation_date, torrent_id, category, num_seeders, num_leechers, last_tracker_check in cursor.execute(
                self.select_torrents_sql + " LIMIT " + str(chunk_size) + " OFFSET " + str(offset)):
            # check if name is valid unicode data
            try:
                name = text_type(name)
            except UnicodeDecodeError:
                continue

            try:
                if len(base64.decodestring(infohash)) != 20:
                    continue
            except:
                continue
            infohash = base64.decodestring(infohash)

            torrents.append(
                ({
                     "status": LEGACY_ENTRY,
                     "infohash": infohash,
                     "timestamp": int(torrent_id or 0),
                     "size": int(length or 0),
                     "torrent_date": datetime.datetime.utcfromtimestamp(creation_date or 0),
                     "title": name or '',
                     "tags": category or '',
                     "id_": torrent_id or 0,
                     "origin_id": 0,
                     "tracker_info": tracker_url,
                     "public_key": self.dispesy_cid_to_pk(channel_id),
                     "signature": self.pseudo_signature(),
                     "xxx": int(category == u'xxx'),
                     "skip_key_check": True},
                 {
                     "seeders": int(num_seeders or 0),
                     "leechers": int(num_leechers or 0),
                     "last_check": int(last_tracker_check or 0)}))

        return torrents


if __name__ == "__main__":
    my_key = default_eccrypto.generate_key(u"curve25519")
    mds = MetadataStore("/tmp/metadata.sdb", "/tmp", my_key)
    d = DispersyToPonyMigration("/tmp/tribler.sdb", "/tmp/dispersy.sdb", mds)
    # old_channels = d.get_old_channels()
    old_trackers = d.get_old_trackers()



    x = 0
    chunk_size = 1000
    while True:
        old_torrents = d.get_old_torrents(chunk_size=chunk_size, offset=x)
        if not old_torrents:
            break
        with db_session:
            for (t, h) in old_torrents:
                m = mds.TorrentMetadata(**t)
                if h["last_check"] > 0:
                    m.health.set(**h)
        x += chunk_size
        break
        print x
        print len(old_torrents)

    with db_session:
        old_channels = d.get_old_channels()
        for c in old_channels:
            c = mds.ChannelMetadata(**c)
            c.num_entries = c.contents_len


    with db_session:
        mds.ChannelMetadata
        for c in mds.ChannelMetadata.select()[:]:
            print c.contents_list




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
