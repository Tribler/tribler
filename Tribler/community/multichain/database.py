""" This file contains everything related to persistence for MultiChain.
"""
from os import path
# Hasher used to generate hashes in the MultiChain Community
from hashlib import sha1

from Tribler.dispersy.database import Database
from Tribler.community.multichain.conversion import encode_block

DATABASE_DIRECTORY = path.join(u"sqlite")
""" Path to the database location + dispersy._workingdirectory"""
DATABASE_PATH = path.join(DATABASE_DIRECTORY, u"multichain.db")
""" Version to keep track if the db schema needs to be updated."""
LATEST_DB_VERSION = 1
""" Schema for the MultiChain DB."""
schema = u"""
CREATE TABLE IF NOT EXISTS multi_chain(
 block_hash			        TEXT PRIMARY KEY,
 up                         INTEGER NOT NULL,
 down                       INTEGER NOT NULL,
 total_up_requester         UNSIGNED BIG INT NOT NULL,
 total_down_requester       UNSIGNED BIG INT NOT NULL,
 sequence_number_requester  INTEGER NOT NULL,
 previous_hash_requester	TEXT NOT NULL,
 total_up_responder         UNSIGNED BIG INT NOT NULL,
 total_down_responder       UNSIGNED BIG INT NOT NULL,
 sequence_number_responder  INTEGER NOT NULL,
 previous_hash_responder	TEXT NOT NULL,
 mid_requester		        TEXT NOT NULL,
 signature_requester		TEXT NOT NULL,
 mid_responder		        TEXT NOT NULL,
 signature_responder		TEXT NOT NULL
);

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '""" + str(LATEST_DB_VERSION) + u"""');
"""


class MultiChainDB(Database):
    """
    Persistence layer for the MultiChain Community.
    Connection layer to SQLiteDB.
    Ensures a proper DB schema on startup.
    """

    def __init__(self, dispersy, working_directory):
        """
        Sets up the persistence layer ready for use.
        :param dispersy: Dispersy stores the PK.
        :param working_directory: Path to the working directory
        that will contain the the db at working directory/DATABASE_PATH
        :return:
        """
        super(MultiChainDB, self).__init__(path.join(working_directory, DATABASE_PATH))
        self._dispersy = dispersy
        self.open()

    def add_block(self, block):
        """
        Persist a block under a block_id
        :param block: The data that will be saved.
        """
        data = (buffer(block.id), block.up, block.down,
                block.total_up_requester, block.total_down_requester,
                block.sequence_number_requester, buffer(block.previous_hash_requester),
                block.total_up_responder, block.total_down_responder,
                block.sequence_number_responder, buffer(block.previous_hash_responder),
                buffer(block.mid_requester), buffer(block.signature_requester),
                buffer(block.mid_responder), buffer(block.signature_responder))

        self.execute(
            u"INSERT INTO multi_chain (block_hash, up, down, "
            u"total_up_requester, total_down_requester, sequence_number_requester, previous_hash_requester,"
            u"total_up_responder, total_down_responder, sequence_number_responder, previous_hash_responder,"
            u"mid_requester, signature_requester, mid_responder, signature_responder) "
            u"VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            data)

    def get_previous_id(self, mid):
        """
        Get the id of the latest block in the chain for a specific public key.
        :param mid: The mid for which the latest hash has to be found.
        :return: block_id
        """
        mid = buffer(mid)
        db_query = u"SELECT block_hash, MAX(sequence_number) FROM " \
                   u"(SELECT block_hash, sequence_number_requester AS sequence_number FROM multi_chain " \
                   u"WHERE mid_requester == ? UNION SELECT block_hash, sequence_number_responder " \
                   u"FROM multi_chain WHERE mid_responder = ?)"

        db_result = self.execute(db_query, (mid, mid)).fetchone()[0]

        return str(db_result) if db_result else None

    def get_by_block_id(self, block_id):
        """
        Returns a block saved in the persistence
        :param block_id: The id of the block that needs to be retrieved.
        :return: The block that was requested or None
        """
        db_query = u"SELECT up, down, " \
                   u"total_up_requester, total_down_requester, sequence_number_requester,  previous_hash_requester, " \
                   u"total_up_responder, total_down_responder, sequence_number_responder,  previous_hash_responder," \
                   u"mid_requester, signature_requester, mid_responder, signature_responder " \
                   u"FROM `multi_chain` WHERE block_hash = ? LIMIT 1"
        db_result = self.execute(db_query, (buffer(block_id),)).fetchone()
        # Create a DB Block or return None
        return self._create_database_block(db_result)

    def get_by_sequence_number_and_mid(self, sequence_number, mid):
        """
        Returns a block saved in the persistence.
        :param sequence_number: The sequence number corresponding to the block.
        :param mid: The public key corresponding to the block
        :return: The block that was requested or None"""
        db_query = u"SELECT up, down, " \
                   u"total_up_requester, total_down_requester, sequence_number_requester,  previous_hash_requester, " \
                   u"total_up_responder, total_down_responder, sequence_number_responder,  previous_hash_responder," \
                   u"mid_requester, signature_requester, mid_responder, signature_responder " \
                   u"FROM (" \
                   u"SELECT *, sequence_number_requester AS sequence_number, mid_requester AS mid FROM `multi_chain` " \
                   u"UNION " \
                   u"SELECT *, sequence_number_responder AS sequence_number, mid_responder AS mid FROM `multi_chain`) " \
                   u"WHERE sequence_number = ? AND mid = ? LIMIT 1"
        db_result = self.execute(db_query, (sequence_number, buffer(mid))).fetchone()
        # Create a DB Block or return None
        return self._create_database_block(db_result)

    def _create_database_block(self, db_result):
        """
        Create a Database block or return None.
        :param db_result: The DB_result with the DatabaseBlock or None
        :return: DatabaseBlock if db_result else None
        """
        if db_result:
            requester = self._dispersy.get_member(mid=str(db_result[10]))
            responder = self._dispersy.get_member(mid=str(db_result[12]))
            return DatabaseBlock(db_result + (requester.public_key, responder.public_key))
        else:
            return None

    def get_ids(self):
        """
        Get all the IDs saved in the persistence layer.
        :return: list of ids.
        """
        db_result = self.execute(u"SELECT block_hash FROM multi_chain").fetchall()
        # Unpack the db_result tuples and decode the results.
        return [str(x[0]) for x in db_result]

    def contains(self, block_id):
        """
        Check if a block is existent in the persistence layer.
        :param block_id: The id t hat needs to be checked.
        :return: True if the block exists, else false.
        """
        db_query = u"SELECT block_hash FROM multi_chain WHERE block_hash == ? LIMIT 1"
        db_result = self.execute(db_query, (buffer(block_id),)).fetchone()
        return db_result is not None

    def get_latest_sequence_number(self, mid):
        """
        Return the latest sequence number known in this node.
        If no block for the pk is know returns -1.
        :param mid: Corresponding public key
        :return: sequence number (integer) or -1 if no block is known
        """
        mid = buffer(mid)
        db_query = u"SELECT MAX(sequence_number) FROM (" \
                   u"SELECT sequence_number_requester AS sequence_number " \
                   u"FROM multi_chain WHERE mid_requester == ? UNION " \
                   u"SELECT sequence_number_responder AS sequence_number " \
                   u"FROM multi_chain WHERE mid_responder = ? )"
        db_result = self.execute(db_query, (mid, mid)).fetchone()[0]
        return db_result if db_result is not None else -1

    def get_total(self, mid):
        """
        Return the latest (total_up, total_down) known in this node.
        if no block for the pk is know returns (-1,-1)
        :param mid: Corresponding mid
        :return: (total_up (int), total_down (int)) or (-1, -1) if no block is known.
        """
        mid = buffer(mid)
        db_query = u"SELECT total_up, total_down, MAX(sequence_number) FROM (" \
                   u"SELECT total_up_requester AS total_up, total_down_requester AS total_down, " \
                   u"sequence_number_requester AS sequence_number FROM multi_chain " \
                   u"WHERE mid_requester == ? UNION " \
                   u"SELECT total_up_responder AS total_up, total_down_responder AS total_down, " \
                   u"sequence_number_responder AS sequence_number FROM multi_chain WHERE mid_responder = ? )" \
                   u"LIMIT 1"
        db_result = self.execute(db_query, (mid, mid)).fetchone()
        return (db_result[0], db_result[1]) if db_result[0] is not None and db_result[1] is not None \
            else (-1, -1)

    def open(self, initial_statements=True, prepare_visioning=True):
        return super(MultiChainDB, self).open(initial_statements, prepare_visioning)

    def close(self, commit=True):
        return super(MultiChainDB, self).close(commit)

    def cleanup(self):
        self.executescript(cleanup)

    def check_database(self, database_version):
        """
        Ensure the proper schema is used by the database.
        :param database_version: Current version of the database.
        :return:
        """
        assert isinstance(database_version, unicode)
        assert database_version.isdigit()
        assert int(database_version) >= 0
        database_version = int(database_version)

        if database_version < 1:
            self.executescript(schema)
            self.commit()

        return LATEST_DB_VERSION

    @staticmethod
    def _convert_to_database_block(db_result):
        data = ()
        for x in range(0, len(db_result)):
            if x <= 6:
                data += (str(db_result[x]),)
            else:
                data += (db_result[x],)
        return DatabaseBlock(data)


class DatabaseBlock:
    """ DataClass for a block that comes out of the DB.
    """

    def __init__(self, data):
        """ Set the partial signature of the requester of the block."""
        """ Set the interaction part of the message """
        self.up = data[0]
        self.down = data[1]
        """ Set the requester part of the message """
        self.total_up_requester = data[2]
        self.total_down_requester = data[3]
        self.sequence_number_requester = data[4]
        self.previous_hash_requester = str(data[5])
        """ Set the responder part of the message. """
        self.total_up_responder = data[6]
        self.total_down_responder = data[7]
        self.sequence_number_responder = data[8]
        self.previous_hash_responder = str(data[9])
        """ Set the signature part of the requester """
        self.mid_requester = str(data[10])
        self.signature_requester = str(data[11])
        """ Set the signature part of the responder """
        self.mid_responder = str(data[12])
        self.signature_responder = str(data[13])
        """ Set the public keys """
        self.public_key_requester = str(data[14])
        self.public_key_responder = str(data[15])
        """ Set up the block hash """
        self.id = sha1(encode_block(self)).digest()


    @classmethod
    def from_tuple(cls, data):
        return cls(data)

    @classmethod
    def from_signature_response_message(cls, message):
        payload = message.payload
        requester = message.authentication.signed_members[0]
        responder = message.authentication.signed_members[1]
        return cls((payload.up, payload.down,
                    payload.total_up_requester, payload.total_down_requester,
                    payload.sequence_number_requester, payload.previous_hash_requester,
                    payload.total_up_responder, payload.total_down_responder,
                    payload.sequence_number_responder, payload.previous_hash_responder,
                    requester[1].mid, requester[0], responder[1].mid, responder[0],
                    requester[1].public_key, responder[1].public_key))

    @classmethod
    def from_block_response_message(cls, message, requester, responder):
        payload = message.payload
        return cls((payload.up, payload.down,
                    payload.total_up_requester, payload.total_down_requester,
                    payload.sequence_number_requester, payload.previous_hash_requester,
                    payload.total_up_responder, payload.total_down_responder,
                    payload.sequence_number_responder, payload.previous_hash_responder,
                    requester.mid, payload.signature_requester, responder.mid, payload.signature_responder,
                    requester.public_key, responder.public_key))

    def to_payload(self):
        """
        :return: (tuple) corresponding to the payload data in a Signature message.
        """
        return (self.up, self.down,
                self.total_up_requester, self.total_down_requester,
                self.sequence_number_requester, self.previous_hash_requester,
                self.total_up_responder, self.total_down_responder,
                self.sequence_number_responder, self.previous_hash_responder,
                self.public_key_requester, self.signature_requester,
                self.public_key_responder, self.signature_responder)

    def __str__(self):
        return "UP: {0!s}\n Down: {1!s}\n" \
               "Requester:\n TU: {2!s}\n TD:{3!s}\n SEQ#: {4!s}\nPREVHASH: {5!s}\nPKREQ:{6!s}\SIG:{7!s}\n" \
               "Responder:\n TU: {8!s}\n TD:{9!s}\n SEQ#: {10!s}\nPREVHASH: {11!s}\nPKREQ:{12!s}\nSIG:{13!s}\n".format(
                   self.up, self.down, self.total_up_requester, self.total_down_requester,
                   self.sequence_number_requester, self.previous_hash_requester,
                   self.public_key_requester, self.signature_requester,
                   self.total_up_responder, self.total_down_responder,
                   self.sequence_number_responder, self.previous_hash_responder,
                   self.public_key_responder, self.signature_responder)