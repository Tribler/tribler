from os import path

from Tribler.dispersy.database import Database

LATEST_VERSION = 1

schema = u"""
-- record contains all received and non-pruned barter records.  this information is, most likely
-- also available at other peers, since the barter records are gossiped around.
CREATE TABLE record(
 sync INTEGER,                          -- REFERENCES sync(id)
 first_member INTEGER,                  -- REFERENCES user(id)
 second_member INTEGER,                 -- REFERENCES user(id)
 global_time INTEGER,                   -- global time when this record was made
 cycle INTEGER,                         -- the cycle when this record was made
 effort BLOB,                           -- raw bytes where each bit represents a cycle, LSB corresponds with the cycle when this record was made
 upload_first_to_second INTEGER,        -- in cooked bytes
 upload_second_to_first INTEGER,        -- in cooked bytes

 -- the following debug values are all according to first_member
 first_timestamp INTEGER,               -- DEBUG timestamp when this record was made
 first_upload INTEGER,                  -- DEBUG bytes uploaded from first to second
 first_download INTEGER,                -- DEBUG bytes uploaded from second to first
 first_total_up INTEGER,                -- DEBUG bytes uploaded from first to others (any transfer)
 first_total_down INTEGER,              -- DEBUG bytes uploaded from others to first (any transfer)
 first_associated_up INTEGER,           -- DEBUG bytes uploaded from first to others (only transfers resulting in records)
 first_associated_down INTEGER,         -- DEBUG bytes uploaded from others to first (only transfers resulting in records)

 -- the following debug values are all according to second_member
 second_timestamp INTEGER,              -- DEBUG timestamp when this record was made (according to second)
 second_upload INTEGER,                 -- DEBUG bytes uploaded from second to first
 second_download INTEGER,               -- DEBUG bytes uploaded from first to second
 second_total_up INTEGER,               -- DEBUG bytes uploaded from second to others (any transfer)
 second_total_down INTEGER,             -- DEBUG bytes uploaded from others to second (any transfer)
 second_associated_up INTEGER,          -- DEBUG bytes uploaded from second to others (only transfers resulting in records)
 second_associated_down INTEGER,        -- DEBUG bytes uploaded from others to second (only transfers resulting in records)

 PRIMARY KEY (sync),
 UNIQUE (first_member, second_member));

-- book contains all local observations.  when criteria match, these observations are used to create
-- barter records.  until that time we should remember as much of our interactions with others as
-- possible.
CREATE TABLE book(
 member INTEGER,                        -- REFERENCES user(id)
 cycle INTEGER,                         -- the cycle when the last book update was made
 effort BLOB,                           -- raw bytes where each bit represents a cycle, LSB corresponds with the cycle when this record was made
 upload INTEGER,                        -- bytes uploaded from member to me
 download INTEGER,                      -- bytes uploaded from me to member
 PRIMARY KEY (member));

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '""" + str(LATEST_VERSION) + """');
"""

cleanup = u"""
DELETE FROM record;
DELETE FROM book;
"""


class BarterDatabase(Database):
    if __debug__:
        __doc__ = schema

    def __init__(self, dispersy):
        self._dispersy = dispersy
        super(BarterDatabase, self).__init__(path.join(dispersy.working_directory, u"sqlite", u"barter.db"))

    def open(self):
        self._dispersy.database.attach_commit_callback(self.commit)
        return super(BarterDatabase, self).open()

    def close(self, commit=True):
        self._dispersy.database.detach_commit_callback(self.commit)
        return super(BarterDatabase, self).close(commit)

    def cleanup(self):
        self.executescript(cleanup)

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
