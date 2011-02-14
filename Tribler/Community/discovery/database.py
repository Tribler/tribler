from os import path
from hashlib import sha1

from Tribler.Core.dispersy.dispersy import Dispersy
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.database import Database
from Tribler.Core.dispersy.dprint import dprint

schema = u"""
-- Each user can sign its own metadata.  The metadata received in the
-- most recent message is stored for each individual user.
CREATE TABLE user_metadata(
 user INTEGER PRIMARY KEY,              -- REFERENCES dispersy.user(id)
 host TEXT,
 port INTEGER,
 alias TEXT,
 comment TEXT);

-- Each user sends around all the communities that she knows.
CREATE TABLE community_metadata(
 cid BLOB PRIMARY KEY,
 alias TEXT,
 comment TEXT);

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option (key, value) VALUES('database_version', '1');
"""

class DiscoveryDatabase(Database):
    if __debug__:
        __doc__ = schema

    def __init__(self):
        working_directory = Dispersy.get_instance().working_directory
        super(DiscoveryDatabase, self).__init__(path.join(working_directory, u"discovery.db"))

    def check_database(self, database_version):
        if database_version == "0":
            self.executescript(schema)

        elif database_version == "1":
            # current version requires no action
            pass

        else:
            # unknown database version
            raise ValueError

    # def bootstrap(self):
    #     if __debug__: dprint()

    #     dispersy_database = DispersyDatabase.get_instance()

    #     # everyone is a member of the hardcoded Discovery community
    #     master_key = "3081a7301006072a8648ce3d020106052b81040027038192000406b298473a7e9e6c62e34672b74ce7fa5d8053b90160f5bbfeb47325dd4be0d159c2cc7876620712245a4a9a5e1f9bcc384717d464e9b2925eaaa10144e03ffe581aa38aa718e4bb02ddcaed3388395c1ddfc9966733f7fe5057c5fdb9e27a47556ee1862d020ff9c094c03694cd65a5a87c417f84f2589d82d5c6f8b57745066cd2ce03839735d73ce29d9b56ce2aa4".decode("HEX")
    #     cid = "ea31500ac3fe9979c8137f12f3ab237cb763533c".decode("HEX")

    #     self.execute(u"INSERT INTO option(key, value) VALUES(?, ?)", (u"master_key", buffer(master_key)))

    #     dispersy_database.execute(u"INSERT INTO community(user, cid, public_key) VALUES(?, ?, ?)",
    #                               (my_member.database_id, buffer(cid), buffer(master_key)))
    #     database_id = dispersy_database.last_insert_rowid

    #     # normally this is done by Community.create_community(...),
    #     # however, because the Discovery community already exists
    #     # (there is on hardcoded) it needs to be done here.
    #     dispersy_database.execute(u"INSERT INTO routing(community, host, port, incoming_time, outgoing_time) SELECT ?, host, port, incoming_time, outgoing_time FROM routing WHERE community = 0", (database_id,))


