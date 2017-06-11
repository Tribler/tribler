from Tribler.community.trustchain.database import TrustChainDB


class TriblerChainDB(TrustChainDB):
    """
    Persistence layer for the TriblerChain Community.
    """
    LATEST_DB_VERSION = 4

    def get_num_unique_interactors(self, public_key):
        """
        Returns the number of people you interacted with (either helped or that have helped you)
        :param public_key: The public key of the member of which we want the information
        :return: A tuple of unique number of interactors that helped you and that you have helped respectively
        """
        peers_you_helped = set()
        peers_helped_you = set()
        for block in self.get_latest_blocks(public_key, limit=-1):
            if int(block.transaction["up"]) > 0:
                peers_you_helped.add(block.link_public_key)
            if int(block.transaction["down"]) > 0:
                peers_helped_you.add(block.link_public_key)
        return len(peers_you_helped), len(peers_helped_you)

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
            while database_version < self.LATEST_DB_VERSION:
                upgrade_script = self.get_upgrade_script(current_version=database_version)
                if upgrade_script:
                    self.executescript(upgrade_script)
                database_version += 1
            self.executescript(self.get_schema())
            self.commit()

        return self.LATEST_DB_VERSION
