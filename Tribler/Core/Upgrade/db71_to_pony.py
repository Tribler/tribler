import os

import lz4
import apsw
import lz4.frame


lz4.frame
select_channels_sql = "Select name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam "\
      + "FROM Channels " \
      + "WHERE nr_torrents >= 3 " \
      + "AND "

class DispersyToPonyMigration(object):

    def __init__(self, tribler_db, dispersy_db, metadata_store):
        self.tribler_db = tribler_db
        self.dispersy_db = dispersy_db
        self.mds = metadata_store

    def get_old_channels(self):
        connection = apsw.Connection(self.tribler_db)
        cursor = connection.cursor()

        channels = []
        for name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam in cursor.execute(select_channels_sql):
            channels.append = {"title":name,
                               "public_key":dispersy_cid,
                               "timestamp":modified,
                               "version": nr_torrents,
                               "votes":nr_favorite,
                               "nr_spam)






    def migrate_channels(self):
