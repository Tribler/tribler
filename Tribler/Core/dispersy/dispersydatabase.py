"""
This module provides an interface to the Dispersy database.

@author: Boudewijn Schoon
@organization: Technical University Delft
@contact: dispersy@frayja.com
"""

from socket import gethostbyname
from hashlib import sha1
from os import path

from database import Database

schema = u"""
CREATE TABLE user(
 id INTEGER PRIMARY KEY AUTOINCREMENT,          -- local counter for database optimization
 mid BLOB,                                      -- member identifier (sha1 of public_key)
 public_key BLOB,                               -- member key (public part)
 host TEXT DEFAULT '',
 port INTEGER DEFAULT -1,
 tags INTEGER DEFAULT 0,
 UNIQUE(mid));

CREATE TABLE tag(
 key INTEGER,
 value TEXT,
 UNIQUE(value));

INSERT INTO tag (key, value) VALUES (1, 'store');
INSERT INTO tag (key, value) VALUES (2, 'ignore');
INSERT INTO tag (key, value) VALUES (4, 'drop');
INSERT INTO tag (key, value) VALUES (1, 'in-order');
INSERT INTO tag (key, value) VALUES (2, 'out-order');
INSERT INTO tag (key, value) VALUES (3, 'random-order');

CREATE TABLE identity(
 user INTEGER REFERENCES user(id),
 community INTEGER REFERENCES community(id),
 packet BLOB,
 UNIQUE(user, community));

CREATE TABLE community(
 id INTEGER PRIMARY KEY AUTOINCREMENT,          -- local counter for database optimization
 user INTEGER REFERENCES user(id),              -- my member that is used to sign my messages
 cid BLOB,                                      -- community identifier (sha1 of public_key)
 public_key BLOB,                               -- community master key (public part)
 UNIQUE(user, cid));

CREATE TABLE key(
 public_key BLOB,                               -- public part
 private_key BLOB,                              -- private part
 UNIQUE(public_key, private_key));

CREATE TABLE routing(
 community INTEGER REFERENCES community(id),
 host TEXT,                                     -- IP address
 port INTEGER,                                  -- port number
 incoming_time TEXT,                            -- time when received data
 outgoing_time TEXT,                            -- time when data send
 UNIQUE(community, host, port));

CREATE TABLE name(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 value TEXT);

CREATE TABLE reference_user_sync(
 user INTEGER REFERENCES user(id),
 sync INTEGER REFERENCES sync(id),
 UNIQUE(user, sync));

CREATE TABLE sync(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 name INTEGER REFERENCES name(id),
 global_time INTEGER,
 synchronization_direction INTEGER REFERENCES tag(key),
 distribution_sequence INTEGER DEFAULT 0,       -- used for the sync-distribution policy
 destination_cluster INTEGER DEFAULT 0,         -- used for the similarity-destination policy
 packet BLOB);

CREATE TABLE similarity(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 user INTEGER REFERENCES user(id),
 cluster INTEGER,
 similarity BLOB,
 packet BLOB,
 UNIQUE(community, user, cluster));

-- TODO: remove id, community, user, and cluster columns and replace with refrence to similarity table
-- my_similarity is used to store the similarity bits
-- as set by the user *before* regulating
CREATE TABLE my_similarity (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 user INTEGER REFERENCES user(id),
 cluster INTEGER,
 similarity BLOB,
 UNIQUE(community, user));

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '1');
"""

class DispersyDatabase(Database):
    if __debug__:
        __doc__ = schema

    def __init__(self, working_directory):
        """
        Initialize a new DispersyDatabase instance.

        @type working_directory: unicode
        @param working_directory: the directory name where the database file should be stored.
        """
        assert isinstance(working_directory, unicode)
        return Database.__init__(self, path.join(working_directory, u"dispersy.db"))

    def check_database(self, database_version):
        assert isinstance(database_version, unicode)
        if database_version == u"0":
            self.executescript(schema)

            # Add bootstrap users
            self.bootstrap()

        elif database_version == u"1":
            # current version requires no action
            pass

    def bootstrap(self):
        """
        Populate the database with initial data.

        This method is called after the database is initially created.  It ensures that one or more
        bootstrap nodes are known.  Without these bootstrap nodes no other nodes will ever be found.
        """
        host = unicode(gethostbyname(u"dispersy1.tribler.org"))
        port = 12345
        public_key = "3081a7301006072a8648ce3d020106052b810400270381920004015f83ac4e8fe506c4035853096187814b93dbe566dbb24f98c51252c3d3a346a1c5813c7db8ece549f92c5ca9fd1cd58018a60e92432bcc12a610760f35b5907094cb6d7cd4e67001a1ab08b3a626a3884ebb5fe69969c47aba087075c72a326ae62046867aa435d71b59a388b5ecbf100896d1ed36131a0c4f6c5c3cb4f19a341919e87976eb03cdea8d6d85704370".decode("HEX")
        mid = "3a4abd4ebb317172c057728799a5e5ea88c6bffa".decode("HEX")
        self.execute(u"INSERT INTO user(mid, public_key) VALUES(?, ?)", (buffer(mid), buffer(public_key)))
        self.execute(u"INSERT INTO routing(community, host, port, incoming_time, outgoing_time) VALUES(0, ?, ?, '2010-01-01 00:00:00', '2010-01-01 00:00:00')", (host, port))
