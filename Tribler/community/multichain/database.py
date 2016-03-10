"""
This file contains everything related to persistence for MultiChain.
"""
import base64
from os import path

from Tribler.dispersy.database import Database
from Tribler.community.multichain.block import GENESIS_ID, EMPTY_PK, EMPTY_SIG, MultiChainBlock

DATABASE_DIRECTORY = path.join(u"sqlite")
# Path to the database location + dispersy._workingdirectory
DATABASE_PATH = path.join(DATABASE_DIRECTORY, u"multichain.db")
# Version to keep track if the db schema needs to be updated.
LATEST_DB_VERSION = 2
# Schema for the MultiChain DB.
schema = u"""
CREATE TABLE IF NOT EXISTS multi_chain(
 up                   INTEGER NOT NULL,
 down                 INTEGER NOT NULL,
 total_up             UNSIGNED BIG INT NOT NULL,
 total_down           UNSIGNED BIG INT NOT NULL,
 public_key           TEXT NOT NULL,
 sequence_number      INTEGER NOT NULL,
 link_public_key      TEXT NOT NULL,
 link_sequence_number INTEGER NOT NULL,
 previous_hash	      TEXT NOT NULL,
 signature		      TEXT NOT NULL,

 insert_time          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
 block_hash	          TEXT NOT NULL,

 PRIMARY KEY (public_key, sequence_number)
 );

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '""" + str(LATEST_DB_VERSION) + u"""');
"""

upgrade_to_version_2_script = u"""
DROP TABLE IF EXISTS multi_chain;
DROP TABLE IF EXISTS option;
"""


class MultiChainDB(Database):
    """
    Persistence layer for the MultiChain Community.
    Connection layer to SQLiteDB.
    Ensures a proper DB schema on startup.
    """

    def __init__(self, working_directory):
        """
        Sets up the persistence layer ready for use.
        :param working_directory: Path to the working directory
        that will contain the the db at working directory/DATABASE_PATH
        :return:
        """
        super(MultiChainDB, self).__init__(path.join(working_directory, DATABASE_PATH))
        self.open()

    def get_latest(self, public_key):
        """
        Get the latest block for a given public key
        :param public_key: The public_key for which the latest block has to be found.
        :return: the latest block or None if it is not known
        """
        public_key = buffer(public_key)
        db_query = u"SELECT up, down, total_up, total_down, public_key, sequence_number, link_public_key," \
                   u"link_sequence_number, previous_hash, signature, insert_time " \
                   u"FROM multi_chain WHERE public_key = ? AND sequence_number = (SELECT MAX(sequence_number) FROM " \
                   u"multi_chain WHERE public_key = ?)"
        db_result = self.execute(db_query, (buffer(public_key), buffer(public_key))).fetchone()
        return MultiChainBlock(db_result) if db_result else None

    def add_block(self, block):
        """
        Persist a block
        :param block: The data that will be saved.
        """
        # TODO: make sure it is not outright invalid...
        self.execute(
            u"INSERT INTO multi_chain (up, down, total_up, total_down, public_key, sequence_number, link_public_key,"
            u"link_sequence_number, previous_hash, signature, block_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            block.pack_db_insert())
        self.commit()

    def contains(self, block):
        """
        Check if a block is existent in the persistence layer.
        :param block: the block to check
        :return: True if the block exists, else false.
        """
        db_query = u"SELECT * FROM multi_chain WHERE public_key = ? AND sequence_number = ?"
        db_result = self.execute(db_query, (buffer(block.public_key), block.sequence_number)).fetchone()
        return db_result is not None

    def get_blocks_since(self, public_key, sequence_number):
        """
        Returns database blocks with sequence number higher than or equal to sequence_number, at most 100 results
        :param public_key: The public key corresponding to the member id
        :param sequence_number: The linear block number
        :return A list of DB Blocks that match the criteria
        """
        db_query = u"SELECT up, down, total_up, total_down, public_key, sequence_number, link_public_key," \
                   u"link_sequence_number, previous_hash, signature, insert_time " \
                   u"FROM multi_chain WHERE sequence_number >= ? AND public_key = ? " \
                   u"ORDER BY sequence_number ASC LIMIT 100"
        db_result = self.execute(db_query, (sequence_number, buffer(public_key))).fetchall()
        return [MultiChainBlock(db_item) for db_item in db_result]

    def get_num_unique_interactors(self, public_key):
        """
        Returns the number of people you interacted with (either helped or that have helped you)
        :param public_key: The public key of the member of which we want the information
        :return: A tuple of unique number of interactors that helped you and that you have helped respectively
        """
        db_query = u"SELECT SUM(CASE WHEN up > 0 THEN 1 ELSE 0 END) AS pk_helped, SUM(CASE WHEN down > 0 THEN 1 ELSE " \
                   u"0 END) AS helped_pk FROM (SELECT link_public_key, SUM(up) AS up, SUM(down) AS down FROM " \
                   u"multi_chain WHERE public_key = ? GROUP BY link_public_key) helpers"
        db_result = self.execute(db_query, (buffer(public_key),)).fetchone()
        return db_result[0], db_result[1]

    def get_linked(self, block):
        """
        Get the block that is linked to the given block
        :param block: The block for which to get the linked block
        :return: the latest block or None if it is not known
        """
        # TODO: make sure linked also works the other way around...
        db_query = u"SELECT up, down, total_up, total_down, public_key, sequence_number, link_public_key," \
                   u"link_sequence_number, previous_hash, signature, insert_time " \
                   u"FROM multi_chain WHERE public_key = ? AND sequence_number = ? OR " \
                   u"link_public_key = ? AND link_sequence_number = ?"
        db_result = self.execute(db_query, (buffer(block.link_public_key), block.link_sequence_number,
                                            buffer(block.public_key), block.sequence_number)).fetchone()
        return MultiChainBlock(db_result) if db_result else None

    def open(self, initial_statements=True, prepare_visioning=True):
        return super(MultiChainDB, self).open(initial_statements, prepare_visioning)

    def close(self, commit=True):
        return super(MultiChainDB, self).close(commit)

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

        if database_version < LATEST_DB_VERSION:
            # Remove all previous data, since we have only been testing so far, and previous blocks might not be
            # reliable. In the future, we should implement an actual upgrade procedure
            self.executescript(upgrade_to_version_2_script)
            self.executescript(schema)
            self.commit()

        return LATEST_DB_VERSION
