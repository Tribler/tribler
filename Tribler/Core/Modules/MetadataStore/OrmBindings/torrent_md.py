from datetime import datetime

from pony import orm
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.serialization import MetadataTypes


def define_binding(db):
    class TorrentMD(db.SignedGossip):
        _discriminator_ = MetadataTypes.REGULAR_TORRENT.value
        infohash = orm.Optional(buffer)
        title = orm.Optional(str)
        size = orm.Optional(int, size=64, default=0)
        tags = orm.Optional(str)
        torrent_date = orm.Optional(datetime)
        to_delete = orm.Optional(bool, default=False)

        def get_magnet(self):
            return "magnet:?xt=urn:btih:%s&dn=%s" % (
                str(self.infohash).encode('hex'), str(self.title).encode('utf8'))

        @staticmethod
        def from_tdef(key, tdef, extra_info=None):
            return TorrentMD.from_dict(
                key,
                {
                    "infohash": tdef.get_infohash(),
                    "title": tdef.get_name_as_unicode(),
                    "tags": extra_info.get('description', '') if extra_info else '',
                    "size": tdef.get_length(),
                    "torrent_date": datetime.fromtimestamp(tdef.get_creation_date()),
                    "tc_pointer": 0})

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
            sql_search_fts = "type = {type} AND rowid IN (SELECT rowid FROM FtsIndex WHERE \
                    FtsIndex MATCH $query ORDER BY bm25(FtsIndex) LIMIT $lim)".format(
                type=entry_type or cls._discriminator_)
            return cls.select(lambda x: orm.raw_sql(sql_search_fts))[:]

        @classmethod
        def getAutoCompleteTerms(cls, keyword, max_terms, limit=100):
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
            if '' in all_terms:
                all_terms.remove('')

            return list(all_terms)

    return TorrentMD
