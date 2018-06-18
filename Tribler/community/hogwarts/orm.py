


"""
    with db_session:

        parser = xml.sax.make_parser()                              # create an XMLReader
        parser.setFeature(xml.sax.handler.feature_namespaces, 0)    # turn off namepsaces
        Handler = TorHandler()                                      # override the default ContextHandler
        parser.setContentHandler( Handler )

        from pony.orm import select
        print(select (t for t in Torrent)[:])
        db.commit()
"""


from ser import TorrentMetadataObj
from datetime import datetime
from pony.orm import *

db = Database('sqlite', 'hogwarts.db', create_db=True)


class TorrentMetadataORM(db.Entity, TorrentMetadataObj):
    infohash = PrimaryKey(buffer, auto=False)
    size = Optional(int, size=64)
    date = Optional(datetime)
    title = Optional(str)
    parent = Optional(buffer)
    tags = Optional(str)

db.generate_mapping(create_tables=True)
