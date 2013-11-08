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


    def add_peer(self, overlap, ip, port, last_connected=None):
        if isinstance(overlap, list):
            overlap = ",".join(map(str, overlap))
            overlap = buffer(overlap)
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
            peers[i][1] = str(peers[i][1])
        return peers
