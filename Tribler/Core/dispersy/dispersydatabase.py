# Python 2.5 features
from __future__ import with_statement

"""
This module provides an interface to the Dispersy database.

@author: Boudewijn Schoon
@organization: Technical University Delft
@contact: dispersy@frayja.com
"""

from socket import gethostbyname
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
INSERT INTO tag (key, value) VALUES (4, 'blacklist');
INSERT INTO tag (key, value) VALUES (1, 'in-order');
INSERT INTO tag (key, value) VALUES (2, 'out-order');
INSERT INTO tag (key, value) VALUES (3, 'random-order');

--CREATE TABLE identity(
-- user INTEGER REFERENCES user(id),
-- community INTEGER REFERENCES community(id),
-- packet BLOB,
-- UNIQUE(user, community));

CREATE TABLE community(
 id INTEGER PRIMARY KEY AUTOINCREMENT,          -- local counter for database optimization
 user INTEGER REFERENCES user(id),              -- my member that is used to sign my messages
 classification TEXT,                           -- the community type, typically the class name
 cid BLOB,                                      -- the sha1 digest of the public_key
 public_key BLOB DEFAULT '',                    -- community master key (public part) when available
 auto_load BOOL DEFAULT 1,                      -- when 1 this community is loaded whenever a packet for it is received
 UNIQUE(user, cid, public_key));

CREATE TABLE key(
 public_key BLOB,                               -- public part
 private_key BLOB,                              -- private part
 UNIQUE(public_key, private_key));

CREATE TABLE candidate(
 community INTEGER REFERENCES community(id),
 host TEXT,                                             -- IP address
 port INTEGER,                                          -- port number
 incoming_time TEXT DEFAULT '2010-01-01 00:00:00',      -- time when received data
 outgoing_time TEXT DEFAULT '2010-01-01 00:00:00',      -- time when data send
 external_time TEXT DEFAULT '2010-01-01 00:00:00',      -- time when we heared about this address from 3rd party
 UNIQUE(community, host, port));

CREATE TABLE name(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 value TEXT);

-- when a message has multiple signatures, using the MultiMemberAuthentication policy, the
-- reference_user_sync table contains an entry for each member
CREATE TABLE reference_user_sync(
 user INTEGER REFERENCES user(id),
 sync INTEGER REFERENCES sync(id),
 UNIQUE(user, sync));

CREATE TABLE sync(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 name INTEGER REFERENCES name(id),
 user INTEGER REFERENCES user(id),              -- the creator of the message
 global_time INTEGER,
 synchronization_direction INTEGER REFERENCES tag(key),
 distribution_sequence INTEGER DEFAULT 0,       -- used for the sync-distribution policy
 destination_cluster INTEGER DEFAULT 0,         -- used for the similarity-destination policy
 packet BLOB,
 priority INTEGER DEFAULT 128,                  -- added in version 2
 undone BOOL DEFAULT 0,                         -- added in version 3?
 UNIQUE(community, user, global_time));

CREATE TABLE malicious_proof(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 user INTEGER REFERENCES name(id),
 packet BLOB);

--CREATE TABLE similarity(
-- id INTEGER PRIMARY KEY AUTOINCREMENT,
-- community INTEGER REFERENCES community(id),
-- user INTEGER REFERENCES user(id),
-- cluster INTEGER,
-- similarity BLOB,
-- packet BLOB,
-- UNIQUE(community, user, cluster));

-- TODO: remove id, community, user, and cluster columns and replace with refrence to similarity table
-- my_similarity is used to store the similarity bits
-- as set by the user *before* regulating
--CREATE TABLE my_similarity (
-- id INTEGER PRIMARY KEY AUTOINCREMENT,
-- community INTEGER REFERENCES community(id),
-- user INTEGER REFERENCES user(id),
-- cluster INTEGER,
-- similarity BLOB,
-- UNIQUE(community, user));

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '3');
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
        assert database_version.isdigit()
        assert int(database_version) >= 0
        previous_version = database_version = int(database_version)

        if database_version == 0:
            # setup new database with current database_version
            self.executescript(schema)

            # Add bootstrap users
            self.bootstrap()

        else:
            # upgrade an older version

            # upgrade from version 1 to version 2
            if database_version < 2:
                with self:
                    self.executescript(u"""
ALTER TABLE sync ADD COLUMN priority INTEGER DEFAULT 128;
UPDATE option SET value = '2' WHERE key = 'database_version';
""")

            # upgrade from version 2 to version 3
            if database_version < 3:
                with self:
                    self.executescript(u"""
CREATE TABLE malicious_proof(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 user INTEGER REFERENCES name(id),
 packet BLOB)
ALTER TABLE sync ADD COLUMN undone BOOL DEFAULT 0;
UPDATE tag SET value = 'blacklist' WHERE key = 4;
UPDATE option SET value = '3' WHERE key = 'database_version';
""")

            # upgrade from version 3 to version 4
            if database_version < 4:
                # there is no version 4 yet...
                # self.executescript(u"""UPDATE option SET value = '4' WHERE key = 'database_version';""")
                pass

    def bootstrap(self):
        """
        Populate the database with initial data.

        This method is called after the database is initially created.  It ensures that one or more
        bootstrap nodes are known.  Without these bootstrap nodes no other nodes will ever be found.
        """
        host = unicode(gethostbyname(u"dispersy1.tribler.org"))
        port = 6421
        public_key = "3081a7301006072a8648ce3d020106052b810400270381920004008444b3016503206d4a3429621dc0dda85481124e3c823a44aaee3f489df396a138af05409c15af6af8c5d88520078cd7d95808dceb49800d8e3532b737b68496225ac43051f99f035a6fecab844ae214471f5dc0c247fcdc199900ed64afd136537543ca41229df6e597b30facfd7dd4ce6d04ef7ded4fe19118cd951fcd43e4930eb963741fd806b4e46bde04c142".decode("HEX")
        mid = "69249b231d04650175c01a622504a95a2dbbc728".decode("HEX")
        self.execute(u"INSERT INTO user(mid, public_key) VALUES(?, ?)", (buffer(mid), buffer(public_key)))
        self.execute(u"INSERT INTO candidate(community, host, port) VALUES(0, ?, ?)", (host, port))
