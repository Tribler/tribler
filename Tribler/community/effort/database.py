from os import path

from Tribler.dispersy.database import Database
from Tribler.dispersy.revision import update_revision_information

if __debug__:
    from Tribler.dispersy.dprint import dprint

# update version information directly from SVN
update_revision_information("$HeadURL$", "$Revision$")

LATEST_VERSION = 4

schema = u"""
CREATE TABLE record(
 sync INTEGER,                                  -- REFERENCES sync(id)
 first_member INTEGER,                          -- REFERENCES user(id)
 second_member INTEGER,                         -- REFERENCES user(id)
 global_time INTEGER,
 first_timestamp INTEGER,
 second_timestamp INTEGER,
 effort BLOB,
 first_upload INTEGER,
 first_download INTEGER,
 second_upload INTEGER,
 second_download INTEGER,
 PRIMARY KEY (sync),
 UNIQUE (first_member, second_member));

CREATE TABLE observation(
 member INTEGER,                                -- REFERENCES user(id)
 timestamp INTEGER,
 effort BLOB,
 PRIMARY KEY (member));

CREATE TABLE bandwidth_guess(
 ip STRING,
 member INTEGER,
 timestamp INTEGER,
 upload INTEGER,                                -- bytes uploaded from me to member
 download INTEGER,                              -- bytes uploaded from member to me
 PRIMARY KEY (ip));
CREATE INDEX bandwidth_guess_member_index ON bandwidth_guess (member);

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '""" + str(LATEST_VERSION) + """');
INSERT INTO option(key, value) VALUES('last_record_pushed', 0);
"""

cleanup = u"""
DELETE FROM record;
DELETE FROM observation;
DELETE FROM bandwidth_guess;
"""

class EffortDatabase(Database):
    if __debug__:
        __doc__ = schema

    def __init__(self, dispersy):
        self._dispersy = dispersy
        super(EffortDatabase, self).__init__(path.join(dispersy.working_directory, u"sqlite", u"effort.db"))
        dispersy.database.attach_commit_callback(self.commit)

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
            # upgrade an older version

#             # upgrade from version 1 to version 2
#             if database_version < 2:
#                 if __debug__: dprint("upgrade database ", database_version, " -> ", 2)
#                 self.executescript(u"""
# INSERT INTO option(key, value) VALUES('last_record_pushed', 0);
# UPDATE option SET value = '2' WHERE key = 'database_version';
# """)
#                 self.commit()
#                 if __debug__: dprint("upgrade database ", database_version, " -> ", 2, " (done)")

#             # upgrade from version 2 to version 3
#             if database_version < 3:
#                 if __debug__: dprint("upgrade database ", database_version, " -> ", 3)
#                 self.executescript(u"""
# CREATE TABLE bandwidth_guess(
#  ip STRING,
#  member INTEGER,
#  timestamp INTEGER,
#  upload INTEGER,                                -- bytes uploaded from me to member
#  download INTEGER,                              -- bytes uploaded from member to me
#  PRIMARY KEY (ip));
# UPDATE option SET value = '3' WHERE key = 'database_version';
# """)
#                 self.commit()
#                 if __debug__: dprint("upgrade database ", database_version, " -> ", 3, " (done)")

#             # upgrade from version 3 to version 4
#             if database_version < 4:
#                 if __debug__: dprint("upgrade database ", database_version, " -> ", 4)
#                 self.executescript(u"""
# -- remove old records.  these are no longer compatible
# DELETE FROM dispersy.sync WHERE dispersy.sync.id IN (SELECT sync FROM record);
# DELETE FROM record;
# -- performance index
# CREATE INDEX bandwidth_guess_member_index ON bandwidth_guess (member);
# -- new columns in the records
# ALTER TABLE record ADD COLUMN first_upload INTEGER;
# ALTER TABLE record ADD COLUMN first_download INTEGER;
# ALTER TABLE record ADD COLUMN second_upload INTEGER;
# ALTER TABLE record ADD COLUMN second_download INTEGER;
# -- update version
# UPDATE option SET value = '4' WHERE key = 'database_version';
# """)
#                 self.commit()
#                 if __debug__: dprint("upgrade database ", database_version, " -> ", 4, " (done)")

            if database_version < 4:
                raise RuntimeError("Unable to upgrade versions below 4")

            # upgrade from version 4 to version 5
            if database_version < 5:
                # there is no version 5 yet...
                # if __debug__: dprint("upgrade database ", database_version, " -> ", 5)
                # self.executescript(u"""UPDATE option SET value = '4' WHERE key = 'database_version';""")
                # self.commit()
                # if __debug__: dprint("upgrade database ", database_version, " -> ", 5, " (done)")
                pass

        return LATEST_VERSION
