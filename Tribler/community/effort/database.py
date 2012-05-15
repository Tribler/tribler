from os import path

from Tribler.dispersy.database import Database

LATEST_VERSION = 1

schema = u"""
CREATE TABLE record(
 community INTEGER,                             -- REFERENCES community(id),
 first_member INTEGER,                          -- REFERENCES user(id)
 second_member INTEGER,                         -- REFERENCES user(id)
 global_time INTEGER,
 first_timestamp INTEGER,
 second_timestamp INTEGER,
 effort BLOB,
 PRIMARY KEY (community, first_member, second_member));

CREATE TABLE observation(
 community INTEGER,                             -- REFERENCES community(id),
 member INTEGER,
 timestamp INTEGER,
 effort BLOB,
 PRIMARY KEY (community, member));

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '""" + str(LATEST_VERSION) + """');
"""

class EffortDatabase(Database):
    if __debug__:
        __doc__ = schema

    def __init__(self, working_directory):
        assert isinstance(working_directory, unicode)
        super(EffortDatabase, self).__init__(path.join(working_directory, u"sqlite", u"effort.db"))

    def check_database(self, database_version):
        assert isinstance(database_version, unicode)
        assert database_version.isdigit()
        assert int(database_version) >= 0
        database_version = int(database_version)

        # setup new database with current database_version
        if database_version < 1:
            self.executescript(schema)

        # upgrade from version 1 to version 2
        elif database_version < 2:
            # there is no version 2 yet...
            # self.executescript(u"""UPDATE option SET value = '2' WHERE key = 'database_version';""")
            pass

        return LATEST_VERSION
