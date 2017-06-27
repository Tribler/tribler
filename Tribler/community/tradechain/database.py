from Tribler.community.trustchain.database import TrustChainDB


class TradeChainDB(TrustChainDB):
    """
    Persistence layer for the TradeChain Community.
    """
    LATEST_DB_VERSION = 1

    def get_all_blocks(self):
        """
        Return all blocks in the database.
        """
        return self._getall(u"", ())

    def get_upgrade_script(self, current_version):
        """
        Return the upgrade script for a specific version.
        :param current_version: the version of the script to return.
        """
        return None
