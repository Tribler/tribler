from datetime import datetime

from pony import orm
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.OrmBindings.metadata import EMPTY_SIG
from Tribler.Core.Modules.MetadataStore.serialization import MetadataTypes, TorrentMetadataPayload, time2float, \
    float2time
from Tribler.pyipv8.ipv8.messaging.serialization import Serializer


def define_binding(db):
    class TorrentMetadata(db.Metadata):
        _discriminator_ = MetadataTypes.REGULAR_TORRENT.value
        infohash = orm.Optional(buffer, default='\x00' * 20)
        title = orm.Optional(str, default='')
        size = orm.Optional(int, size=64, default=0)
        tags = orm.Optional(str, default='')
        torrent_date = orm.Optional(datetime)

        def serialized(self, signature=True):
            serializer = Serializer()
            payload = TorrentMetadataPayload(self.type, str(self.public_key), time2float(self.timestamp),
                                             self.tc_pointer, str(self.signature) if signature else EMPTY_SIG,
                                             str(self.infohash), self.size, str(self.title), str(self.tags))
            return serializer.pack_multiple(payload.to_pack_list())[0]

        def get_magnet(self):
            return "magnet:?xt=urn:btih:%s&dn=%s" % (
                str(self.infohash).encode('hex'), str(self.title).encode('utf8'))

        @classmethod
        def search_keyword(cls, query, entry_type=None, lim=100):
            # Requires FTS5 table "FtsIndex" to be generated and populated.
            # FTS table is maintained automatically by SQL triggers.
            # BM25 ranking is embedded in FTS5.

            # Sanitize FTS query
            if not query:
                return []
            if query.endswith("*"):
                query = "\"" + query[:-1] + "\"" + "*"
            else:
                query = "\"" + query + "\""

            metadata_type = entry_type or cls._discriminator_
            sql_search_fts = "type = %d AND rowid IN (SELECT rowid FROM FtsIndex WHERE " \
                             "FtsIndex MATCH $query ORDER BY bm25(FtsIndex) LIMIT %d)" % (metadata_type, lim)
            return cls.select(lambda x: orm.raw_sql(sql_search_fts))[:]

        @classmethod
        def get_auto_complete_terms(cls, keyword, max_terms, limit=100):
            with db_session:
                result = cls.search_keyword(keyword + "*", lim=limit)
            titles = [g.title.lower() for g in result]

            # Copy-pasted from the old DBHandler (almost) completely
            all_terms = set()
            for line in titles:
                if len(all_terms) >= max_terms:
                    break
                i1 = line.find(keyword)
                i2 = line.find(' ', i1 + len(keyword))
                all_terms.add(line[i1:i2] if i2 >= 0 else line[i1:])

            if keyword in all_terms:
                all_terms.remove(keyword)

            return list(all_terms)

        @classmethod
        def from_payload(cls, payload):
            metadata_dict = {
                "type": payload.metadata_type,
                "public_key": payload.public_key,
                "timestamp": float2time(payload.timestamp),
                "tc_pointer": payload.tc_pointer,
                "signature": payload.signature,
                "infohash": payload.infohash,
                "size": payload.size,
                "title": payload.title,
                "tags": payload.tags
            }
            return cls(**metadata_dict)

    return TorrentMetadata
