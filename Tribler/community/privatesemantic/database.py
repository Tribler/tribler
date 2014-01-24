from os import path
from time import time

from Tribler.dispersy.database import Database

LATEST_VERSION = 1

schema = u"""
CREATE TABLE peercache(
 ip text,
 port interger,
 overlap text,
 last_connected real,
 connected_times integer DEFAULT 0,
 PRIMARY KEY (ip, port));
 
CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '""" + str(LATEST_VERSION) + """');
"""

class SemanticDatabase(Database):
    if __debug__:
        __doc__ = schema

    def __init__(self, dispersy):
        self._dispersy = dispersy

        if self._dispersy._database._file_path == u":memory:":
            super(SemanticDatabase, self).__init__(u":memory:")
        else:
            super(SemanticDatabase, self).__init__(path.join(dispersy.working_directory, u"sqlite", u"peercache.db"))

    def open(self):
        self._dispersy.database.attach_commit_callback(self.commit)
        return super(SemanticDatabase, self).open()

    def close(self, commit=True):
        self._dispersy.database.detach_commit_callback(self.commit)
        return super(SemanticDatabase, self).close(commit)

    def check_database(self, database_version):
        assert isinstance(database_version, unicode)
        assert database_version.isdigit()
        assert int(database_version) >= 0
        database_version = int(database_version)

        # setup new database with current database_version
        if database_version < 1:
            self.executescript(schema)
            self.commit()

        else:
            # upgrade to version 2
            if database_version < 2:
                # there is no version 2 yet...
                # if __debug__: dprint("upgrade database ", database_version, " -> ", 2)
                # self.executescript(u"""UPDATE option SET value = '2' WHERE key = 'database_version';""")
                # self.commit()
                # if __debug__: dprint("upgrade database ", database_version, " -> ", 2, " (done)")
                pass

        return LATEST_VERSION

    def get_database_stats(self):
        stats_dict = {}

        for tablename, in list(self.execute(u'SELECT name FROM sqlite_master WHERE type = "table"')):
            count, = self.execute(u"SELECT COUNT(*) FROM " + tablename).next()
            stats_dict[str(tablename)] = count
        return stats_dict

    def add_peer(self, overlap, ip, port, last_connected=None):
        assert isinstance(overlap, (list, int, long, float)), type(overlap)
        if isinstance(overlap, list):
            assert all(isinstance(cur_overlap, (int, long, float)) for cur_overlap in overlap), [type(cur_overlap) for cur_overlap in overlap]

        if isinstance(overlap, list):
            overlap = ",".join(map(str, overlap))
            overlap = buffer(overlap)

        import sys
        print >> sys.stderr, "inserting get_peers", overlap, ip, port

        try:
            self.execute(u"INSERT INTO peercache (ip, port, overlap, last_connected) VALUES (?,?,?,?)", (unicode(ip), port, overlap, last_connected or time()))
        except:
            self.execute(u"UPDATE peercache SET overlap = ?, last_connected = ?, connected_times = connected_times + 1 WHERE ip = ? AND port = ?", (overlap, last_connected or time(), unicode(ip), port))

    def get_peers(self):
        peers = list(self.execute(u"SELECT overlap, ip, port FROM peercache"))
        for i in range(len(peers)):
            peers[i] = list(peers[i])
            if isinstance(peers[i][0], buffer):
                peers[i][0] = [long(overlap) for overlap in str(peers[i][0]).split(",") if overlap]
            else:
                peers[i][0] = float(peers[i][0])
            peers[i][1] = str(peers[i][1])

        peers.sort(reverse=True)
        import sys
        print >> sys.stderr, "result of get_peers", peers
        return peers
