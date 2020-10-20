import threading
from asyncio import get_event_loop

from pony import orm
from pony.orm import db_session, desc, raw_sql, select

from tribler_core.modules.metadata_store.orm_bindings.channel_node import LEGACY_ENTRY, TODELETE
from tribler_core.modules.metadata_store.orm_bindings.torrent_metadata import NULL_KEY_SUBST
from tribler_core.modules.metadata_store.serialization import METADATA_NODE, MetadataNodePayload
from tribler_core.utilities.unicode import hexlify


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
        num_entries = orm.Optional(int, size=64, default=0, index=True)

        # Special class-level properties
        _payload_class = MetadataNodePayload
        payload_arguments = _payload_class.__init__.__code__.co_varnames[
            : _payload_class.__init__.__code__.co_argcount
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
            txt_filter=None,
            subscribed=None,
            category=None,
            attribute_ranges=None,
            infohash=None,
            id_=None,
        ):
            """
            This method implements REST-friendly way to get entries from the database. It is overloaded by the higher
            level classes to add some more conditions to the query.
            :return: PonyORM query object corresponding to the given params.
            """
            # Warning! For Pony magic to work, iteration variable name (e.g. 'g') should be the same everywhere!

            pony_query = cls.search_keyword(txt_filter, lim=1000) if txt_filter else select(g for g in cls)

            if metadata_type is not None:
                try:
                    pony_query = pony_query.where(lambda g: g.metadata_type in metadata_type)
                except TypeError:
                    pony_query = pony_query.where(lambda g: g.metadata_type == metadata_type)

            pony_query = (
                pony_query.where(public_key=(b"" if channel_pk == NULL_KEY_SUBST else channel_pk))
                if channel_pk is not None
                else pony_query
            )

            if attribute_ranges is not None:
                for attr, left, right in attribute_ranges:
                    getattr(cls, attr)  # Check against code injection
                    if left is not None:
                        pony_query = pony_query.where(f"g.{attr} >= left")
                    if right is not None:
                        pony_query = pony_query.where(f"g.{attr} < right")

            # origin_id can be zero, for e.g. root channel
            pony_query = pony_query.where(id_=id_) if id_ is not None else pony_query
            pony_query = pony_query.where(origin_id=origin_id) if origin_id is not None else pony_query
            pony_query = pony_query.where(lambda g: g.subscribed) if subscribed is not None else pony_query
            pony_query = pony_query.where(lambda g: g.tags == category) if category else pony_query
            pony_query = pony_query.where(lambda g: g.status != TODELETE) if exclude_deleted else pony_query
            pony_query = pony_query.where(lambda g: g.xxx == 0) if hide_xxx else pony_query
            pony_query = pony_query.where(lambda g: g.status != LEGACY_ENTRY) if exclude_legacy else pony_query
            pony_query = pony_query.where(lambda g: g.infohash == infohash) if infohash else pony_query

            # Sort the query
            if sort_by == "HEALTH":
                pony_query = (
                    pony_query.sort_by("(desc(g.health.seeders), desc(g.health.leechers))")
                    if sort_desc
                    else pony_query.sort_by("(g.health.seeders, g.health.leechers)")
                )
            elif sort_by == "size" and not issubclass(cls, db.ChannelMetadata):
                # TODO: optimize this check to skip cases where size field does not matter
                # When querying for mixed channels / torrents lists, channels should have priority over torrents
                sort_expression = "desc(g.num_entries), desc(g.size)" if sort_desc else "g.num_entries, g.size"
                pony_query = pony_query.sort_by(sort_expression)
            elif sort_by:
                sort_expression = "g." + sort_by
                sort_expression = desc(sort_expression) if sort_desc else sort_expression
                pony_query = pony_query.sort_by(sort_expression)

            return pony_query

        @classmethod
        async def get_entries_threaded(cls, **kwargs):
            def _get_results():
                result = cls.get_entries(**kwargs)
                if not isinstance(threading.current_thread(), threading._MainThread):
                    db.disconnect()
                return result

            return await get_event_loop().run_in_executor(None, _get_results)

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
            for p in ["first", "last"]:
                kwargs.pop(p, None)
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
