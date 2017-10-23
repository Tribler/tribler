"""
This file contains everything related to persistence for TrustChain.
"""
import os

from Tribler.dispersy.database import Database
from Tribler.community.trustchain.block import TrustChainBlock


DATABASE_DIRECTORY = os.path.join(u"sqlite")
LATEST_DB_VERSION = "1"


class TrustChainDB(Database):
    """
    Persistence layer for the TrustChain Community.
    Connection layer to SQLiteDB.
    Ensures a proper DB schema on startup.
    """
    BLOCK_CLASS = TrustChainBlock

    def __init__(self, working_directory, db_name, transaction_fields=[("tx", "TEXT")]):
        """
        Sets up the persistence layer ready for use.
        :param working_directory: Path to the working directory
        that will contain the the db at working directory/DATABASE_PATH
        :param db_name: The name of the database
        """
        assert len(transaction_fields) > 0, "Must contain at least one transaction field"
        db_path = os.path.join(working_directory, os.path.join(DATABASE_DIRECTORY, u"%s.db" % db_name))
        self.transaction_fields = transaction_fields
        self.db_name = db_name

        super(TrustChainDB, self).__init__(db_path)
        self._logger.debug("TrustChain database path: %s", db_path)
        self.open()

    def add_block(self, block):
        """
        Persist a block
        :param block: The data that will be saved.
        """
        self.execute(
            (u"INSERT INTO %s_blocks (public_key, sequence_number, link_public_key," +
             u"link_sequence_number, previous_hash, signature, block_hash, tx_" +
             u", tx_".join([tx[0] for tx in self.transaction_fields]) + u") VALUES(?,?,?,?,?,?,?" +
             (u",?" * len(self.transaction_fields)) + u")")
            % self.db_name, block.pack_db_insert())
        self.commit()

    def _get(self, query, params):
        db_result = self.execute(self.get_sql_header() + query, params).fetchone()
        return self.BLOCK_CLASS(db_result) if db_result else None

    def _getall(self, query, params):
        db_result = self.execute(self.get_sql_header() + query, params).fetchall()
        return [self.BLOCK_CLASS(db_item) for db_item in db_result]

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
        return self._get(u"WHERE public_key = ? AND sequence_number = (SELECT MAX(sequence_number) FROM %s_blocks "
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
        return self._getall(u"WHERE insert_time >= (SELECT MAX(insert_time) FROM %s_blocks WHERE public_key = ? AND "
                            u"sequence_number <= ?) AND (public_key = ? OR link_public_key = ?) "
                            u"ORDER BY insert_time ASC LIMIT ?" % self.db_name,
                            (buffer(public_key), sequence_number, buffer(public_key), buffer(public_key), limit))

    def get_sql_header(self):
        """
        Return the first part of a generic sql select query.
        """
        _columns = u"public_key, sequence_number, link_public_key, link_sequence_number, " \
                   u"previous_hash, signature, insert_time, tx_" + \
                   u", tx_".join([tx[0] for tx in self.transaction_fields])
        return u"SELECT " + _columns + u" FROM %s_blocks " % self.db_name

    def get_schema(self, level = None):
        """
        Return the schema for the database.
        """
        return u"""
        CREATE TABLE IF NOT EXISTS %s_blocks(
         public_key           TEXT NOT NULL,
         sequence_number      INTEGER NOT NULL,
         link_public_key      TEXT NOT NULL,
         link_sequence_number INTEGER NOT NULL,
         previous_hash	      TEXT NOT NULL,
         signature		      TEXT NOT NULL,

         insert_time          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
         block_hash	          TEXT NOT NULL,

         %s,

         PRIMARY KEY (public_key, sequence_number)
         );

        CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
        INSERT INTO option(key, value) VALUES('database_version', '%s');
        """ % (self.db_name,
               u",\n".join(["tx_" + tx[0] + u" " + tx[1] + u" NOT NULL" for tx in self.transaction_fields]),
               self.get_db_version())

    def get_upgrade_script(self, level, to_version):
        """
        Return the upgrade script for a specific version.
        :param to_version: the version of the script to return.
        """
        if level == 0 and to_version <= int(LATEST_DB_VERSION):
            return u"""
            DROP TABLE IF EXISTS blocks;
            DROP TABLE IF EXISTS %s_blocks;
            """ % self.db_name

        return None

    def open(self, initial_statements=True, prepare_visioning=True):
        return super(TrustChainDB, self).open(initial_statements, prepare_visioning)

    def close(self, commit=True):
        return super(TrustChainDB, self).close(commit)

    def get_db_version(self, level=None):
        """
        Returns the current database version for a specific inheritance level. TrustChain = 0
        :param level: the inheritance level who's db version to get, or Null (default) to pass the entire version string
        :return: the current highest version of the database layout
        """
        return LATEST_DB_VERSION

    def check_database(self, database_version, levels = 1):
        """
        Ensure the proper schema is used by the database.
        :param database_version: Current version of the database.
        :return:
        """
        assert isinstance(database_version, unicode)
        version_parts = database_version.split(u'.')
        if database_version == u"0":
            version_parts = [u"0"] * levels
        assert len(version_parts) == levels, "invalid number of levels/versions"
        assert len([part for part in version_parts if not part.isdigit()]) == 0, \
            "non digit version part %s" % repr(database_version)
        assert len([part for part in version_parts if not int(part) >= 0]) == 0, \
            "negative version part %s" % repr(database_version)

        for level in range(0, levels):
            version = version_parts[level]

            if version < self.get_db_version(level):
                while version < LATEST_DB_VERSION:
                    version = str(int(version) + 1)
                    upgrade_script = self.get_upgrade_script(0, int(version))
                    if upgrade_script:
                        self.executescript(upgrade_script)
                self.executescript(self.get_schema(level))
                self.executescript(u"""
                    UPDATE option SET value = '%s' WHERE key = 'database_version';                
                """ % self.get_db_version())
                self.commit()

        return sum([int(part) for part in version_parts])
