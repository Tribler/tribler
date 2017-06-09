"""
This file contains everything related to persistence for MultiChain.
"""
import os

from Tribler.community.multichain.block import MultiChainBlock
from Tribler.dispersy.database import Database

DATABASE_DIRECTORY = os.path.join(u"sqlite")


class MultiChainDB(Database):
    """
    Persistence layer for the MultiChain Community.
    Connection layer to SQLiteDB.
    Ensures a proper DB schema on startup.
    """
    LATEST_DB_VERSION = 4

    def __init__(self, working_directory, db_name):
        """
        Sets up the persistence layer ready for use.
        :param working_directory: Path to the working directory
        that will contain the the db at working directory/DATABASE_PATH
        :param db_name: The name of the database
        """
        super(MultiChainDB, self).__init__(os.path.join(
            working_directory, os.path.join(DATABASE_DIRECTORY, u"%s.db" % db_name)))
        self.db_name = db_name
        self.open()

    def add_block(self, block):
        """
        Persist a block
        :param block: The data that will be saved.
        """
        self.execute(
            u"INSERT INTO %s (up, down, total_up, total_down, public_key, sequence_number, link_public_key,"
            u"link_sequence_number, previous_hash, signature, block_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?)" % self.db_name,
            block.pack_db_insert())
        self.commit()

    def _get(self, query, params):
        db_result = self.execute(self.get_sql_header() + query, params).fetchone()
        return MultiChainBlock(db_result) if db_result else None

    def _getall(self, query, params):
        db_result = self.execute(self.get_sql_header() + query, params).fetchall()
        return [MultiChainBlock(db_item) for db_item in db_result]

    def get(self, public_key, sequence_number):
        """
        Get a specific block for a given public key
        :param public_key: The public_key for which the block has to be found.
        :param sequence_number: The specific block to get
        :return: the block or None if it is not known
        """
        return self._get(u"WHERE public_key = ? AND sequence_number = ?", (buffer(public_key), sequence_number))

    def contains(self, block):
        """
        Check if a block is existent in the persistence layer.
        :param block: the block to check
        :return: True if the block exists, else false.
        """
        return self.get(block.public_key, block.sequence_number) is not None

    def get_latest(self, public_key):
        """
        Get the latest block for a given public key
        :param public_key: The public_key for which the latest block has to be found.
        :return: the latest block or None if it is not known
        """
        return self._get(u"WHERE public_key = ? AND sequence_number = (SELECT MAX(sequence_number) FROM %s "
                         u"WHERE public_key = ?)" % self.db_name, (buffer(public_key), buffer(public_key)))

    def get_latest_blocks(self, public_key, limit=25):
        return self._getall(u"WHERE public_key = ? ORDER BY sequence_number DESC LIMIT ?", (buffer(public_key), limit))

    def get_block_after(self, block):
        """
        Returns database block with the lowest sequence number higher than the block's sequence_number
        :param block: The block who's successor we want to find
        :return A block
        """
        return self._get(u"WHERE sequence_number > ? AND public_key = ? ORDER BY sequence_number ASC",
                         (block.sequence_number, buffer(block.public_key)))

    def get_block_before(self, block):
        """
        Returns database block with the highest sequence number lower than the block's sequence_number
        :param block: The block who's predecessor we want to find
        :return A block
        """
        return self._get(u"WHERE sequence_number < ? AND public_key = ? ORDER BY sequence_number DESC",
                         (block.sequence_number, buffer(block.public_key)))

    def get_linked(self, block):
        """
        Get the block that is linked to the given block
        :param block: The block for which to get the linked block
        :return: the latest block or None if it is not known
        """
        return self._get(u"WHERE public_key = ? AND sequence_number = ? OR link_public_key = ? AND "
                         u"link_sequence_number = ?", (buffer(block.link_public_key), block.link_sequence_number,
                                                       buffer(block.public_key), block.sequence_number))

    def crawl(self, public_key, sequence_number, limit=100):
        assert limit <= 100, "Don't fetch too much"
        return self._getall(u"WHERE insert_time >= (SELECT MAX(insert_time) FROM %s WHERE public_key = ? AND "
                            u"sequence_number <= ?) AND (public_key = ? OR link_public_key = ?) "
                            u"ORDER BY insert_time ASC LIMIT ?" % self.db_name,
                            (buffer(public_key), sequence_number, buffer(public_key), buffer(public_key), limit))

    def get_num_unique_interactors(self, public_key):
        """
        Returns the number of people you interacted with (either helped or that have helped you)
        :param public_key: The public key of the member of which we want the information
        :return: A tuple of unique number of interactors that helped you and that you have helped respectively
        """
        db_query = u"SELECT SUM(CASE WHEN up > 0 THEN 1 ELSE 0 END) AS pk_helped, SUM(CASE WHEN down > 0 THEN 1 ELSE " \
                   u"0 END) AS helped_pk FROM (SELECT link_public_key, SUM(up) AS up, SUM(down) AS down FROM " \
                   u"%s WHERE public_key = ? GROUP BY link_public_key) helpers" % self.db_name
        return self.execute(db_query, (buffer(public_key),)).fetchone()

    def get_sql_header(self):
        """
        Return the first part of a generic sql select query.
        """
        _columns = u"up, down, total_up, total_down, public_key, sequence_number, link_public_key, link_sequence_number, " \
                   u"previous_hash, signature, insert_time"
        return u"SELECT " + _columns + u" FROM %s " % self.db_name

    def get_schema(self):
        """
        Return the schema for the database.
        """
        return u"""
        CREATE TABLE IF NOT EXISTS %s(
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
        INSERT INTO option(key, value) VALUES('database_version', '%s');
        """ % (self.db_name, str(self.LATEST_DB_VERSION))

    def get_upgrade_script(self, current_version):
        """
        Return the upgrade script for a specific version.
        :param current_version: the version of the script to return.
        """
        if current_version == 2 or current_version == 3:
            return u"""
            DROP TABLE IF EXISTS %s;
            DROP TABLE IF EXISTS option;
            """ % self.db_name

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

        if database_version < self.LATEST_DB_VERSION:
            # Remove all previous data, since we have only been testing so far, and previous blocks might not be
            # reliable. In the future, we should implement an actual upgrade procedure
            self.executescript(self.get_upgrade_script(current_version=2))
            self.executescript(self.get_schema())
            self.commit()

        return self.LATEST_DB_VERSION
