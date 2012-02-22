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

if __debug__:
    from dprint import dprint

LATEST_VERSION = 9

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
 database_version INTEGER DEFAULT """ + str(LATEST_VERSION) + """,
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
 undone INTEGER DEFAULT 0,
 packet BLOB,
 UNIQUE(community, member, global_time));
CREATE INDEX sync_meta_message_global_time_index ON sync(meta_message, global_time);

CREATE TABLE malicious_proof(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 member INTEGER REFERENCES name(id),
 packet BLOB);

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '""" + str(LATEST_VERSION) + """');
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

        else:
            # upgrade an older version

            # upgrade from version 1 to version 2
            if database_version < 2:
                self.executescript(u"""
ALTER TABLE sync ADD COLUMN priority INTEGER DEFAULT 128;
UPDATE option SET value = '2' WHERE key = 'database_version';
""")

            # upgrade from version 2 to version 3
            if database_version < 3:
                self.executescript(u"""
CREATE TABLE malicious_proof(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 user INTEGER REFERENCES name(id),
 packet BLOB);
ALTER TABLE sync ADD COLUMN undone BOOL DEFAULT 0;
UPDATE tag SET value = 'blacklist' WHERE key = 4;
UPDATE option SET value = '3' WHERE key = 'database_version';
""")

            # upgrade from version 3 to version 4
            if database_version < 4:
                self.executescript(u"""
-- create new tables

CREATE TABLE member(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 mid BLOB,
 public_key BLOB,
 tags TEXT DEFAULT '',
 UNIQUE(public_key));
CREATE INDEX member_mid_index ON member(mid);

CREATE TABLE identity(
 community INTEGER REFERENCES community(id),
 member INTEGER REFERENCES member(id),
 host TEXT DEFAULT '',
 port INTEGER DEFAULT -1,
 PRIMARY KEY(community, member));

CREATE TABLE private_key(
 member INTEGER PRIMARY KEY REFERENCES member(id),
 private_key BLOB);

CREATE TABLE new_community(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 master INTEGER REFERENCES member(id),
 member INTEGER REFERENCES member(id),
 classification TEXT,
 auto_load BOOL DEFAULT 1,
 UNIQUE(master));

CREATE TABLE new_reference_member_sync(
 member INTEGER REFERENCES member(id),
 sync INTEGER REFERENCES sync(id),
 UNIQUE(member, sync));

CREATE TABLE meta_message(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 name TEXT,
 cluster INTEGER DEFAULT 0,
 priority INTEGER DEFAULT 128,
 direction INTEGER DEFAULT 1,
 UNIQUE(community, name));

CREATE TABLE new_sync(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 member INTEGER REFERENCES member(id),
 global_time INTEGER,
 meta_message INTEGER REFERENCES meta_message(id),
 undone BOOL DEFAULT 0,
 packet BLOB,
 UNIQUE(community, member, global_time));
CREATE INDEX sync_meta_message_index ON new_sync(meta_message);

CREATE TABLE new_malicious_proof(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 member INTEGER REFERENCES name(id),
 packet BLOB);

-- populate new tables

-- no tags have ever been set outside debugging hence we do not upgrade those
INSERT INTO member (id, mid, public_key) SELECT id, mid, public_key FROM user;
INSERT INTO identity (community, member, host, port) SELECT community.id, user.id, user.host, user.port FROM community JOIN user;
INSERT INTO private_key (member, private_key) SELECT member.id, key.private_key FROM key JOIN member ON member.public_key = key.public_key;
INSERT INTO new_community (id, member, master, classification, auto_load) SELECT community.id, community.user, user.id, community.classification, community.auto_load FROM community JOIN user ON user.mid = community.cid;
INSERT INTO new_reference_member_sync (member, sync) SELECT user, sync FROM reference_user_sync;
INSERT INTO new_malicious_proof (id, community, member, packet) SELECT id, community, user, packet FROM malicious_proof ;
""")

                # copy all data from sync and name into new_sync and meta_message
                meta_messages = {}
                for id, community, name, user, global_time, synchronization_direction, distribution_sequence, destination_cluster, packet, priority, undone in list(self.execute(u"SELECT sync.id, sync.community, name.value, sync.user, sync.global_time, sync.synchronization_direction, sync.distribution_sequence, sync.destination_cluster, sync.packet, sync.priority, sync.undone FROM sync JOIN name ON name.id = sync.name")):

                    # get or create meta_message id
                    key = (community, name)
                    if not key in meta_messages:
                        self.execute(u"INSERT INTO meta_message (community, name, cluster, priority, direction) VALUES (?, ?, ?, ?, ?)",
                                     (community, name, destination_cluster, priority, -1 if synchronization_direction == 2 else 1))
                        meta_messages[key] = self.last_insert_rowid
                    meta_message = meta_messages[key]

                    self.execute(u"INSERT INTO new_sync (community, member, global_time, meta_message, undone, packet) VALUES (?, ?, ?, ?, ?, ?)",
                                 (community, user, global_time, meta_message, undone, packet))

                self.executescript(u"""
-- drop old tables and entries

DROP TABLE community;
DROP TABLE key;
DROP TABLE malicious_proof;
DROP TABLE name;
DROP TABLE reference_user_sync;
DROP TABLE sync;
DROP TABLE tag;
DROP TABLE user;

-- rename replacement tables

ALTER TABLE new_community RENAME TO community;
ALTER TABLE new_reference_member_sync RENAME TO reference_member_sync;
ALTER TABLE new_sync RENAME TO sync;
ALTER TABLE new_malicious_proof RENAME TO malicious_proof;

-- update database version
UPDATE option SET value = '4' WHERE key = 'database_version';
""")

            # upgrade from version 4 to version 5
            if database_version < 5:
                self.executescript(u"""
DROP TABLE candidate;
UPDATE option SET value = '5' WHERE key = 'database_version';
""")

            # upgrade from version 5 to version 6
            if database_version < 6:
                self.executescript(u"""
DROP TABLE identity;
UPDATE option SET value = '6' WHERE key = 'database_version';
""")

            # upgrade from version 6 to version 7
            if database_version < 7:
                self.executescript(u"""
DROP INDEX sync_meta_message_index;
CREATE INDEX sync_meta_message_global_time_index ON sync(meta_message, global_time);
UPDATE option SET value = '7' WHERE key = 'database_version';
""")

            # upgrade from version 7 to version 8
            if database_version < 8:
                if __debug__: dprint("upgrade database ", database_version, " -> ", 8)
                self.executescript(u"""
ALTER TABLE community ADD COLUMN database_version INTEGER DEFAULT 0;
UPDATE option SET value = '8' WHERE key = 'database_version';
""")
            if __debug__: dprint("upgrade database ", database_version, " -> ", 8, " (done)")

            # upgrade from version 8 to version 9
            if database_version < 9:
                if __debug__: dprint("upgrade database ", database_version, " -> ", 9)
                self.executescript(u"""
DROP INDEX sync_meta_message_global_time_index;
CREATE INDEX sync_global_time_undone_meta_message_index ON sync(global_time, undone, meta_message);
UPDATE option SET value = '9' WHERE key = 'database_version';
""")
            if __debug__: dprint("upgrade database ", database_version, " -> ", 8, " (done)")

            # upgrade from version 9 to version 10
            if database_version < 10:
                # there is no version 10 yet...
                # self.executescript(u"""UPDATE option SET value = '10' WHERE key = 'database_version';""")
                pass

        return LATEST_VERSION

    def check_community_database(self, community, database_version):
        assert isinstance(database_version, int)
        assert database_version >= 0

        if database_version < 8:
            if __debug__: dprint("upgrade community ", database_version, " -> ", 8)

            # patch notes:
            #
            # - the undone column in the sync table is not a boolean anymore.  instead it points to
            #   the row id of one of the associated dispersy-undo-own or dispersy-undo-other
            #   messages
            #
            # - we know that Dispersy.create_undo has been called while the member did not have
            #   permission to do so.  hence, invalid dispersy-undo-other messages have been stored
            #   in the local database, causing problems with the sync.  these need to be removed
            #
            updates = []
            deletes = []
            redoes = []
            convert_packet_to_message = community.dispersy.convert_packet_to_message
            undo_own_meta = community.get_meta_message(u"dispersy-undo-own")
            undo_other_meta = community.get_meta_message(u"dispersy-undo-other")

            progress = 0
            count, = self.execute(u"SELECT COUNT(1) FROM sync WHERE meta_message = ? OR meta_message = ?", (undo_own_meta.database_id, undo_other_meta.database_id)).next()
            if __debug__: dprint("upgrading ", count, " undo messages")
            if count > 50:
                progress_handlers = [handler("Upgrading database", "Please wait while we upgrade the database", count) for handler in community.dispersy.get_progress_handlers()]
            else:
                progress_handlers = []

            for packet_id, packet in list(self.execute(u"SELECT id, packet FROM sync WHERE meta_message = ?", (undo_own_meta.database_id,))):
                message = convert_packet_to_message(str(packet), community)
                if message:
                    updates.append((packet_id, message.payload.packet.packet_id))

                progress += 1
                for handler in progress_handlers:
                    handler.Update(progress)

            for packet_id, packet in list(self.execute(u"SELECT id, packet FROM sync WHERE meta_message = ?", (undo_other_meta.database_id,))):
                message = convert_packet_to_message(str(packet), community)
                if message:
                    allowed, _ = community._timeline.check(message)
                    if allowed:
                        updates.append((packet_id, message.payload.packet.packet_id))

                    else:
                        deletes.append((packet_id,))
                        msg = message.payload.packet.load_message()
                        redoes.append((msg.packet_id,))
                        if msg.undo_callback:
                            try:
                                # try to redo the message... this may not always be possible now...
                                msg.undo_callback([(msg.authentication.member, msg.distribution.global_time, msg)], redo=True)
                            except:
                                if __debug__: dprint(exception=True, level="warning")

                progress += 1
                for handler in progress_handlers:
                    handler.Update(progress)

            for handler in progress_handlers:
                handler.Update(progress, "Saving the results...")

            # note: UPDATE first, REDOES second, since UPDATES contains undo items that may have
            # been invalid
            self.executemany(u"UPDATE sync SET undone = ? WHERE id = ?", updates)
            self.executemany(u"UPDATE sync SET undone = 0 WHERE id = ?", redoes)
            self.executemany(u"DELETE FROM sync WHERE id = ?", deletes)

            self.execute(u"UPDATE community SET database_version = 8 WHERE id = ?", (community.database_id,))
            self.commit()

            for handler in progress_handlers:
                handler.Destroy()

        return LATEST_VERSION
