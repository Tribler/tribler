# Python 2.5 features
from __future__ import with_statement

"""
This module provides an interface to the Dispersy database.

@author: Boudewijn Schoon
@organization: Technical University Delft
@contact: dispersy@frayja.com
"""

from os import path

from database import Database

schema = u"""
CREATE TABLE member(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 mid BLOB,                                      -- member identifier (sha1 of public_key)
 public_key BLOB,                               -- member public key
 tags TEXT DEFAULT '',                          -- comma separated tags: store, ignore, and blacklist
 UNIQUE(public_key));
CREATE INDEX member_mid_index ON member(mid);

CREATE TABLE private_key(
 member INTEGER PRIMARY KEY REFERENCES member(id),
 private_key BLOB);

CREATE TABLE community(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 master INTEGER REFERENCES member(id),          -- master member (permission tree root)
 member INTEGER REFERENCES member(id),          -- my member (used to sign messages)
 classification TEXT,                           -- community type, typically the class name
 auto_load BOOL DEFAULT 1,                      -- when 1 this community is loaded whenever a packet for it is received
 UNIQUE(master));

CREATE TABLE meta_message(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 name TEXT,
 cluster INTEGER DEFAULT 0,
 priority INTEGER DEFAULT 128,
 direction INTEGER DEFAULT 1,                           -- direction used when synching (1 for ASC, -1 for DESC)
 UNIQUE(community, name));

CREATE TABLE reference_member_sync(
 member INTEGER REFERENCES member(id),
 sync INTEGER REFERENCES sync(id),
 UNIQUE(member, sync));

CREATE TABLE sync(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 member INTEGER REFERENCES member(id),                  -- the creator of the message
 global_time INTEGER,
 meta_message INTEGER REFERENCES meta_message(id),
 undone BOOL DEFAULT 0,
 packet BLOB,
 UNIQUE(community, member, global_time));
CREATE INDEX sync_meta_message_global_time_index ON sync(meta_message, global_time);

CREATE TABLE malicious_proof(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 member INTEGER REFERENCES name(id),
 packet BLOB);

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '7');
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
        Database.__init__(self, path.join(working_directory, u"dispersy.db"))

    def check_database(self, database_version):
        assert isinstance(database_version, unicode)
        assert database_version.isdigit()
        assert int(database_version) >= 0
        database_version = int(database_version)

        if database_version == 0:
            # setup new database with current database_version
            self.executescript(schema)

            # # Add bootstrap members
            # self.bootstrap()

        else:
            # upgrade an older version

            # upgrade from version 1 to version 7
            if database_version < 7:
                raise RuntimeError("First official release uses database version 7.  No upgrade supported before this version.")

            # upgrade from version 7 to version 8
            if database_version < 8:
                # there is no version 8 yet...
                # self.executescript(u"""UPDATE option SET value = '8' WHERE key = 'database_version';""")
                pass
