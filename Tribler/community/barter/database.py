from os import path
from hashlib import sha1

from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.database import Database
from Tribler.dispersy.dprint import dprint

schema = u"""
CREATE TABLE record(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 community INTEGER REFERENCES community(id),
 global_time INTEGER,
 first_member INTEGER,                          -- REFERENCES user(id)
 second_member INTEGER,                         -- REFERENCES user(id)
 upload_first_member INTEGER,
 upload_second_member INTEGER);

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '1');
"""

class BarterDatabase(Database):
    if __debug__:
        __doc__ = schema

    def __init__(self):
        working_directory = Dispersy.get_instance().working_directory
        super(BarterDatabase, self).__init__(path.join(working_directory, u"barter.db"))

    def check_database(self, database_version):
        if database_version == "0":
            self.executescript(schema)

        elif database_version == "1":
            # current version requires no action
            pass

        else:
            # unknown database version
            raise ValueError
