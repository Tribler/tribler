from __future__ import absolute_import

from binascii import hexlify, unhexlify

from ipv8.database import database_blob

from pony import orm
from pony.orm import db_session, desc, raw_sql, select

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import LEGACY_ENTRY
from Tribler.Core.Modules.MetadataStore.OrmBindings.torrent_metadata import NULL_KEY_SUBST
from Tribler.Core.Modules.MetadataStore.serialization import METADATA_NODE, MetadataNodePayload
from Tribler.Core.Utilities.utilities import is_channel_public_key, is_hex_string
from Tribler.Test.GUI.FakeTriblerAPI.constants import TODELETE


def define_binding(db):
    class MetadataNode(db.ChannelNode):
        """
        This ORM class extends ChannelNode by adding metadata-storing attributes such as "title" and "tags".
        It implements methods for indexed text search based on the "title" field.
        It is not intended for direct use. Instead, other classes should derive from it.
        """

        _discriminator_ = METADATA_NODE

        # Serializable
        title = orm.Optional(str, default='', index=True)
        tags = orm.Optional(str, default='', index=True)

        # FIXME: ACHTUNG! PONY BUG! This is a workaround for Pony not caching attributes from multiple inheritance!
        # Its real home is CollectionNode, but we are forced to put it here so it is loaded by default on all queries.
        # When Pony fixes it, we must move it back to CollectionNode for clarity.
        num_entries = orm.Optional(int, size=64, default=0)

        # Special class-level properties
        _payload_class = MetadataNodePayload
        payload_arguments = _payload_class.__init__.__code__.co_varnames[
            : _payload_class.__init__.func_code.co_argcount
        ][1:]
        nonpersonal_attributes = db.ChannelNode.nonpersonal_attributes + ('title', 'tags')

        @classmethod
        def search_keyword(cls, query, lim=100):
            # Requires FTS5 table "FtsIndex" to be generated and populated.
            # FTS table is maintained automatically by SQL triggers.
            # BM25 ranking is embedded in FTS5.

            # Sanitize FTS query
            if not query or query == "*":
                return []

            # !!! FIXME !!! Fix GROUP BY for entries without infohash !!!
            # TODO: optimize this query by removing unnecessary select nests (including Pony-manages selects)
            fts_ids = raw_sql(
                """SELECT rowid FROM ChannelNode WHERE rowid IN (SELECT rowid FROM FtsIndex WHERE FtsIndex MATCH $query
                ORDER BY bm25(FtsIndex) LIMIT $lim) GROUP BY infohash"""
            )
            return cls.select(lambda g: g.rowid in fts_ids)

        @classmethod
        @db_session
        def get_entries_query(
            cls,
            metadata_type=None,
            channel_pk=None,
            exclude_deleted=False,
            hide_xxx=False,
            exclude_legacy=False,
            origin_id=None,
            sort_by=None,
            sort_desc=True,
            query_filter=None,
            category=None,
        ):
            """
            This method implements REST-friendly way to get entries from the database. It is overloaded by the higher
            level classes to add some more conditions to the query.
            :return: PonyORM query object corresponding to the given params.
            """
            # Warning! For Pony magic to work, iteration variable name (e.g. 'g') should be the same everywhere!
            # Filter the results on a keyword or some keywords

            # FIXME: it is dangerous to mix query attributes. Should be handled by higher level methods instead
            # If we get a hex-encoded public key in the query_filter field, we drop the filter,
            # and instead query by public_key. However, we only do this if there is no
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

            pony_query = cls.search_keyword(query_filter, lim=1000) if query_filter else select(g for g in cls)

            if isinstance(metadata_type, list):
                pony_query = pony_query.where(lambda g: g.metadata_type in metadata_type)
            elif metadata_type:
                pony_query = pony_query.where(lambda g: g.metadata_type == metadata_type)

            pony_query = (
                pony_query.where(public_key=(b"" if channel_pk == NULL_KEY_SUBST else channel_pk))
                if channel_pk is not None
                else pony_query
            )
            # origin_id can be zero, for e.g. root channel
            pony_query = pony_query.where(origin_id=origin_id) if origin_id is not None else pony_query
            pony_query = pony_query.where(lambda g: g.tags == category) if category else pony_query
            pony_query = pony_query.where(lambda g: g.status != TODELETE) if exclude_deleted else pony_query
            pony_query = pony_query.where(lambda g: g.xxx == 0) if hide_xxx else pony_query
            pony_query = pony_query.where(lambda g: g.status != LEGACY_ENTRY) if exclude_legacy else pony_query

            # Sort the query
            if sort_by == "HEALTH":
                pony_query = (
                    pony_query.sort_by("(desc(g.health.seeders), desc(g.health.leechers))")
                    if sort_desc
                    else pony_query.sort_by("(g.health.seeders, g.health.leechers)")
                )
            elif sort_by:
                sort_expression = "g." + sort_by
                sort_expression = desc(sort_expression) if sort_desc else sort_expression
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
            return pony_query[(first or 1) - 1 : last]

        @classmethod
        @db_session
        def get_total_count(cls, **kwargs):
            """
            Get total count of torrents that would be returned if there would be no pagination/limits/sort
            """
            for p in ["first", "last", "sort_by", "sort_desc"]:
                kwargs.pop(p, None)
            return cls.get_entries_query(**kwargs).count()

        @classmethod
        @db_session
        def get_entries_count(cls, **kwargs):
            return cls.get_entries_query(**kwargs).count()

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

        @db_session
        def to_simple_dict(self):
            """
            Return a basic dictionary with information about the channel.
            """
            simple_dict = {
                "type": self._discriminator_,
                "id": self.id_,
                "origin_id": self.origin_id,
                "public_key": hexlify(self.public_key),
                "name": self.title,
                "category": self.tags,
                "status": self.status,
            }

            return simple_dict

    return MetadataNode
