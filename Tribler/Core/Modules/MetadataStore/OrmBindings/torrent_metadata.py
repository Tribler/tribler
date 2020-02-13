from __future__ import absolute_import

from binascii import unhexlify
from datetime import datetime
from struct import unpack

from ipv8.database import database_blob

from pony import orm
from pony.orm import db_session, desc, raw_sql, select

from six import text_type

from Tribler.Core.Category.Category import default_category_filter
from Tribler.Core.Category.FamilyFilter import default_xxx_filter
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import COMMITTED, LEGACY_ENTRY, NEW, TODELETE, UPDATED
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, EPOCH, REGULAR_TORRENT, \
    TorrentMetadataPayload
from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url
from Tribler.Core.Utilities.unicode import ensure_unicode, hexlify
from Tribler.Core.Utilities.utilities import is_channel_public_key, is_hex_string, is_infohash

NULL_KEY_SUBST = b"\00"


# This function is used to devise id_ from infohash in deterministic way. Used in FFA channels.
def infohash_to_id(infohash):
    return abs(unpack(">q", infohash[:8])[0])


def tdef_to_metadata_dict(tdef):
    """
    Helper function to create a TorrentMetadata-compatible dict from TorrentDef
    """
    # We only want to determine the type of the data. XXX filtering is done by the receiving side
    try:
        tags = default_category_filter.calculateCategory(tdef.metainfo, tdef.get_name_as_unicode())
    except UnicodeDecodeError:
        tags = "Unknown"
    try:
        torrent_date = datetime.fromtimestamp(tdef.get_creation_date())
    except ValueError:
        torrent_date = EPOCH


    return {
        "infohash": tdef.get_infohash(),
        "title": tdef.get_name_as_unicode()[:300],  # TODO: do proper size checking based on bytes
        "tags": tags[:200],  # TODO: do proper size checking based on bytes
        "size": tdef.get_length(),
        "torrent_date": torrent_date if torrent_date >= EPOCH else EPOCH,
        "tracker_info": get_uniformed_tracker_url(ensure_unicode(tdef.get_tracker() or '', 'utf-8')) or ''}


def define_binding(db):
    class TorrentMetadata(db.ChannelNode):
        _discriminator_ = REGULAR_TORRENT

        # Serializable
        infohash = orm.Required(database_blob, index=True)
        size = orm.Optional(int, size=64, default=0, index=True)
        torrent_date = orm.Optional(datetime, default=datetime.utcnow, index=True)
        title = orm.Optional(str, default='', index=True)
        tags = orm.Optional(str, default='', index=True)
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
                    (hexlify(self.infohash), self.title)) + \
                   ("&tr=%s" % self.tracker_info if self.tracker_info else "")

        @classmethod
        @db_session
        def add_ffa_from_dict(cls, ffa_dict):
            # To produce a relatively unique id_ we take some bytes of the infohash and convert these to a number.
            # abs is necessary as the conversion can produce a negative value, and we do not support that.
            id_ = infohash_to_id(ffa_dict["infohash"])
            # Check that this torrent is yet unknown to GigaChannel, and if there is no duplicate FFA entry.
            # Test for a duplicate id_+public_key is necessary to account for a (highly improbable) situation when
            # two entries have different infohashes but the same id_. We do not want people to exploit this.
            ih_blob = database_blob(ffa_dict["infohash"])
            pk_blob = database_blob(b"")
            if cls.exists(lambda g: (g.infohash == ih_blob) or (
                    g.id_ == id_ and g.public_key == pk_blob)):
                return None
            # Add the torrent as a free-for-all entry if it is unknown to GigaChannel
            return cls.from_dict(dict(ffa_dict, public_key=b'', status=COMMITTED, id_=id_))

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
        def get_entries_query(cls, metadata_type=None, channel_pk=None,
                              exclude_deleted=False, hide_xxx=False, exclude_legacy=False, origin_id=None,
                              sort_by=None, sort_asc=True, query_filter=None, infohash=None):
            # Warning! For Pony magic to work, iteration variable name (e.g. 'g') should be the same everywhere!
            # Filter the results on a keyword or some keywords

            # FIXME: it is dangerous to mix query attributes. Should be handled by higher level methods instead
            # If we get a hex-encoded public key or infohash in the query_filter field, we drop the filter,
            # and instead query by public_key or infohash field. However, we only do this if there is no
            # channel_pk or origin_id attributes set, because we only want this special treatment of query_filter
            # argument for global search queries. In other words, named arguments have priority over hacky shenaningans
            if query_filter:
                normal_filter = query_filter.replace('"', '').replace("*", "")
                if is_hex_string(normal_filter) and len(normal_filter) % 2 == 0:
                    query_blob = database_blob(unhexlify(normal_filter))
                    if is_channel_public_key(normal_filter):
                        if (origin_id is None) and not channel_pk:
                            channel_pk = query_blob
                            query_filter = None
                    elif is_infohash(normal_filter):
                        infohash = query_blob
                        query_filter = None

            pony_query = cls.search_keyword(query_filter, lim=1000) if query_filter else select(g for g in cls)

            if isinstance(metadata_type, list):
                pony_query = pony_query.where(lambda g: g.metadata_type in metadata_type)
            else:
                pony_query = pony_query.where(
                    metadata_type=metadata_type if metadata_type is not None else cls._discriminator_)

            # Note that origin_id and channel_pk can be 0 and "" respectively, for, say, root channel and FFA entry
            pony_query = pony_query.where(public_key=(b"" if channel_pk == NULL_KEY_SUBST else channel_pk))\
                if channel_pk is not None else pony_query
            pony_query = pony_query.where(origin_id=origin_id) if origin_id is not None else pony_query
            pony_query = pony_query.where(lambda g: g.status != TODELETE) if exclude_deleted else pony_query
            pony_query = pony_query.where(lambda g: g.xxx == 0) if hide_xxx else pony_query
            pony_query = pony_query.where(lambda g: g.status != LEGACY_ENTRY) if exclude_legacy else pony_query
            pony_query = pony_query.where(lambda g: g.infohash == infohash) if infohash else pony_query

            # Sort the query
            if sort_by == "HEALTH":
                pony_query = pony_query.sort_by("(g.health.seeders, g.health.leechers)") if sort_asc else \
                    pony_query.sort_by("(desc(g.health.seeders), desc(g.health.leechers))")
            elif sort_by:
                sort_expression = "g." + sort_by
                sort_expression = sort_expression if sort_asc else desc(sort_expression)
                pony_query = pony_query.sort_by(sort_expression)

            return pony_query

        @classmethod
        @db_session
        def get_entries(cls, first=1, last=None, **kwargs):
            """
            Get some torrents. Optionally sort the results by a specific field, or filter the channels based
            on a keyword/whether you are subscribed to it.
            :return: A list of class members
            """
            pony_query = cls.get_entries_query(**kwargs)
            return pony_query[(first or 1) - 1:last]

        @classmethod
        @db_session
        def get_entries_count(cls, **kwargs):
            return cls.get_entries_query(**kwargs).count()

        @db_session
        def to_simple_dict(self, include_trackers=False):
            """
            Return a basic dictionary with information about the channel.
            """
            epoch = datetime.utcfromtimestamp(0)
            simple_dict = {
                "id": self.id_,
                "public_key": hexlify(self.public_key or NULL_KEY_SUBST),
                "name": self.title,
                "infohash": hexlify(self.infohash),
                "size": self.size,
                "category": self.tags,
                "num_seeders": self.health.seeders,
                "num_leechers": self.health.leechers,
                "last_tracker_check": self.health.last_check,
                "updated": int((self.torrent_date - epoch).total_seconds()),
                "status": self.status,
                "type": {REGULAR_TORRENT: 'torrent', CHANNEL_TORRENT: 'channel'}[self.metadata_type]
            }

            if include_trackers:
                simple_dict['trackers'] = [tracker.url for tracker in self.health.trackers]

            return simple_dict

        def metadata_conflicting(self, b):
            # Check if metadata in the given dict has conflicts with this entry
            # WARNING! This does NOT check the INFOHASH
            a = self.to_dict()
            for comp in ["title", "size", "tags", "torrent_date", "tracker_info"]:
                if (comp not in b) or (text_type(a[comp]) == text_type(b[comp])):
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

            if "status" in update_dict and update_dict["status"] != self.status:
                self.set(**update_dict)
                return update_dict["status"] != COMMITTED

            if (("tags" in update_dict and self.tags != update_dict["tags"]) or
                    ("title" in update_dict and self.title != update_dict["title"])):
                self.set(**update_dict)
                self.status = UPDATED
                self.timestamp = self._clock.tick()
                self.sign()
                return True

        @classmethod
        @db_session
        def copy_to_channel(cls, infohash, channel_id, public_key=None):
            """
            Create a new signed copy of the given torrent metadata
            :param infohash:
            :param public_key:
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
                "status": NEW,
                "origin_id": channel_id
            }
            return db.TorrentMetadata.from_dict(new_entry_dict)

        @classmethod
        @db_session
        def get_with_infohash(cls, infohash):
            return cls.select(lambda g: g.infohash == database_blob(infohash)).first()

        @classmethod
        @db_session
        def get_torrent_title(cls, infohash):
            md = cls.get_with_infohash(infohash)
            return md.title if md else None

    return TorrentMetadata
