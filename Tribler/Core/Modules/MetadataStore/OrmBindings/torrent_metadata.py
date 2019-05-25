from __future__ import absolute_import

from binascii import hexlify, unhexlify
from datetime import datetime

from ipv8.database import database_blob

from pony import orm
from pony.orm import db_session, desc, raw_sql, select

from Tribler.Core.Category.FamilyFilter import default_xxx_filter
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import LEGACY_ENTRY, NEW, TODELETE, UPDATED
from Tribler.Core.Modules.MetadataStore.serialization import REGULAR_TORRENT, TorrentMetadataPayload
from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url
from Tribler.Core.Utilities.utilities import is_channel_public_key, is_hex_string, is_infohash


def define_binding(db):
    class TorrentMetadata(db.ChannelNode):
        _discriminator_ = REGULAR_TORRENT

        # Serializable
        infohash = orm.Required(database_blob)
        size = orm.Optional(int, size=64, default=0)
        torrent_date = orm.Optional(datetime, default=datetime.utcnow)
        title = orm.Optional(str, default='')
        tags = orm.Optional(str, default='')
        tracker_info = orm.Optional(str, default='')

        orm.composite_key(db.ChannelNode.public_key, infohash)

        # Local
        xxx = orm.Optional(float, default=0)
        health = orm.Optional('TorrentState', reverse='metadata')

        _payload_class = TorrentMetadataPayload

        def __init__(self, *args, **kwargs):
            if "health" not in kwargs and "infohash" in kwargs:
                kwargs["health"] = db.TorrentState.get(infohash=kwargs["infohash"]) or db.TorrentState(
                    infohash=kwargs["infohash"])
            if 'xxx' not in kwargs:
                kwargs["xxx"] = default_xxx_filter.isXXXTorrentMetadataDict(kwargs)

            super(TorrentMetadata, self).__init__(*args, **kwargs)

            if 'tracker_info' in kwargs:
                self.add_tracker(kwargs["tracker_info"])

        def add_tracker(self, tracker_url):
            sanitized_url = get_uniformed_tracker_url(tracker_url)
            if sanitized_url:
                tracker = db.TrackerState.get(url=sanitized_url) or db.TrackerState(url=sanitized_url)
                self.health.trackers.add(tracker)

        def before_update(self):
            self.add_tracker(self.tracker_info)

        def get_magnet(self):
            return ("magnet:?xt=urn:btih:%s&dn=%s" %
                    (hexlify(str(self.infohash)), self.title)) + \
                   ("&tr=%s" % self.tracker_info if self.tracker_info else "")

        @classmethod
        def search_keyword(cls, query, lim=100):
            # Requires FTS5 table "FtsIndex" to be generated and populated.
            # FTS table is maintained automatically by SQL triggers.
            # BM25 ranking is embedded in FTS5.

            # Sanitize FTS query
            if not query or query == "*":
                return []

            # TODO: optimize this query by removing unnecessary select nests (including Pony-manages selects)
            fts_ids = raw_sql(
                """SELECT rowid FROM ChannelNode WHERE rowid IN (SELECT rowid FROM FtsIndex WHERE FtsIndex MATCH $query
                ORDER BY bm25(FtsIndex) LIMIT $lim) GROUP BY infohash""")

            # TODO: Check for complex query
            normal_query = query.replace('"', '').replace("*", "")
            if is_hex_string(normal_query) and len(normal_query) % 2 == 0:
                query_blob = database_blob(unhexlify(normal_query))
                if is_channel_public_key(normal_query):
                    return cls.select(lambda g: g.public_key == query_blob or g.rowid in fts_ids)
                if is_infohash(normal_query):
                    return cls.select(lambda g: g.infohash == query_blob or g.rowid in fts_ids)
            return cls.select(lambda g: g.rowid in fts_ids)

        @classmethod
        def get_auto_complete_terms(cls, keyword, max_terms, limit=10):
            if not keyword:
                return []

            with db_session:
                result = cls.search_keyword("\"" + keyword + "\"*", lim=limit)[:]
            titles = [g.title.lower() for g in result]

            # Copy-pasted from the old DBHandler (almost) completely
            all_terms = set()
            for line in titles:
                if len(all_terms) >= max_terms:
                    break
                i1 = line.find(keyword)
                i2 = line.find(' ', i1 + len(keyword))
                term = line[i1:i2] if i2 >= 0 else line[i1:]
                if term != keyword:
                    all_terms.add(term)
            return list(all_terms)

        @classmethod
        @db_session
        def get_random_torrents(cls, limit):
            """
            Return some random torrents from the database.
            """
            return TorrentMetadata.select(
                lambda g: g.metadata_type == REGULAR_TORRENT and g.status != LEGACY_ENTRY).random(limit)

        @classmethod
        @db_session
        def get_entries_query(cls, sort_by=None, sort_asc=True, query_filter=None):
            """
            Get some metadata entries. Optionally sort the results by a specific field, or filter the channels based
            on a keyword/whether you are subscribed to it.
            :return: A tuple. The first entry is a list of ChannelMetadata entries. The second entry indicates
                     the total number of results, regardless the passed first/last parameter.
            """
            # Warning! For Pony magic to work, iteration variable name (e.g. 'g') should be the same everywhere!
            # Filter the results on a keyword or some keywords
            pony_query = cls.search_keyword(query_filter, lim=1000) if query_filter else select(g for g in cls)

            # Sort the query
            sort_expression = None
            if sort_by:
                if sort_by == "HEALTH":
                    pony_query = pony_query.sort_by("(g.health.seeders, g.health.leechers)") if sort_asc else \
                        pony_query.sort_by("(desc(g.health.seeders), desc(g.health.leechers))")
                else:
                    sort_expression = "g." + sort_by
                    sort_expression = sort_expression if sort_asc else desc(sort_expression)
                    pony_query = pony_query.sort_by(sort_expression)
            # Workaround to always show legacy entries last
            pony_query = pony_query.order_by(lambda g: (desc(g.status != LEGACY_ENTRY), sort_expression)) \
                if sort_expression else pony_query.order_by(lambda g: desc(g.status != LEGACY_ENTRY))
            return pony_query


        @classmethod
        @db_session
        def get_entries(cls, first=None, last=None, metadata_type=REGULAR_TORRENT, channel_pk=False,
                        exclude_deleted=False, hide_xxx=False, exclude_legacy=False, **kwargs):
            """
            Get some torrents. Optionally sort the results by a specific field, or filter the channels based
            on a keyword/whether you are subscribed to it.
            :return: A tuple. The first entry is a list of ChannelMetadata entries. The second entry indicates
                     the total number of results, regardless the passed first/last parameter.
            """
            pony_query = cls.get_entries_query(**kwargs)

            if isinstance(metadata_type, list):
                pony_query = pony_query.where(lambda g: g.metadata_type in metadata_type)
            else:
                pony_query = pony_query.where(metadata_type=metadata_type)

            if exclude_deleted:
                pony_query = pony_query.where(lambda g: g.status != TODELETE)
            if hide_xxx:
                pony_query = pony_query.where(lambda g: g.xxx == 0)
            if exclude_legacy:
                pony_query = pony_query.where(lambda g: g.status != LEGACY_ENTRY)

            # Filter on channel
            if channel_pk:
                pony_query = pony_query.where(public_key=channel_pk)

            count = pony_query.count()

            return pony_query[(first or 1) - 1:last] if first or last else pony_query, count

        @db_session
        def to_simple_dict(self, include_trackers=False):
            """
            Return a basic dictionary with information about the channel.
            """
            simple_dict = {
                "id": self.rowid,
                "name": self.title,
                "infohash": hexlify(self.infohash),
                "size": self.size,
                "category": self.tags,
                "num_seeders": self.health.seeders,
                "num_leechers": self.health.leechers,
                "last_tracker_check": self.health.last_check,
                "status": self.status
            }

            if include_trackers:
                simple_dict['trackers'] = [tracker.url for tracker in self.health.trackers]

            return simple_dict

        def metadata_conflicting(self, b):
            # Check if metadata in the given dict has conflicts with this entry
            # WARNING! This does NOT check the INFOHASH
            a = self.to_dict()
            for comp in ["title", "size", "tags", "torrent_date", "tracker_info"]:
                if (comp not in b) or (str(a[comp]) == str(b[comp])):
                    continue
                return True
            return False

        def update_properties(self, update_dict):
            # TODO: generalize this to work for all properties.
            if "status" in update_dict and len(update_dict) > 1:
                self._logger.error("Assigning status along with other properties is not supported yet.")
                raise NotImplementedError

            if set(update_dict) - {"tags", "title", "status"}:
                self._logger.error("Assigning properties other than tags, title and status is not supported yet.")
                raise NotImplementedError

            if "status" in update_dict:
                self.set(**update_dict)
                return

            if (("tags" in update_dict and self.tags != update_dict["tags"]) or
                    ("title" in update_dict and self.title != update_dict["title"])):
                self.set(**update_dict)
                self.status = UPDATED
                self.timestamp = self._clock.tick()
                self.sign()

        @classmethod
        @db_session
        def copy_to_channel(cls, infohash, public_key=None):
            """
            Create a new signed copy of the given torrent metadata
            :param metadata: Metadata to copy
            :return: New TorrentMetadata signed with your key
            """

            existing = cls.get(public_key=public_key, infohash=infohash) if public_key \
                else cls.select(lambda g: g.infohash == database_blob(infohash)).first()

            if not existing:
                return None

            new_entry_dict = {
                "infohash": existing.infohash,
                "title": existing.title,
                "tags": existing.tags,
                "size": existing.size,
                "torrent_date": existing.torrent_date,
                "tracker_info": existing.tracker_info,
                "status": NEW
            }
            return db.TorrentMetadata.from_dict(new_entry_dict)

    return TorrentMetadata
