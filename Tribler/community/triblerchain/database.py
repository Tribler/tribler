from Tribler.community.triblerchain.block import TriblerChainBlock

from Tribler.community.trustchain.database import TrustChainDB

LATEST_DB_VERSION = "4"


class TriblerChainDB(TrustChainDB):
    """
    Persistence layer for the TriblerChain Community.
    """
    BLOCK_CLASS = TriblerChainBlock

    def __init__(self, working_directory, db_name):
        super(TriblerChainDB, self).__init__(working_directory, db_name, transaction_fields=[
            ("up", "INTEGER"),
            ("down", "INTEGER"),
            ("total_up", "INTEGER"),
            ("total_down", "INTEGER")
        ])

    def get_num_unique_interactors(self, public_key):
        """
        Returns the number of people you interacted with (either helped or that have helped you)
        :param public_key: The public key of the member of which we want the information
        :return: A tuple of unique number of interactors that helped you and that you have helped respectively
        """
        peers_you_helped = set()
        peers_helped_you = set()
        for block in self.get_latest_blocks(public_key, limit=-1):
            if block.up > 0:
                peers_you_helped.add(block.link_public_key)
            if block.down > 0:
                peers_helped_you.add(block.link_public_key)
        return len(peers_you_helped), len(peers_helped_you)

    def get_subjective_work_graph(self):
        graph = {}
        db_result = self.execute(u"SELECT public_key, link_public_key, SUM(tx_up), SUM(tx_down) FROM %s_blocks "
                                 u"GROUP BY public_key, link_public_key" % self.db_name).fetchall()
        if db_result:
            for row in db_result:
                index = (str(row[0]), str(row[1]))
                if index in graph:
                    graph[index] = (max(graph[index][0], int(row[2])), max(graph[index][1], int(row[3])))
                else:
                    graph[index] = (int(row[2]), int(row[3]))
                index = (str(row[1]), str(row[0]))
                if index in graph:
                    graph[index] = (max(graph[index][0], int(row[3])), max(graph[index][1], int(row[2])))
                else:
                    graph[index] = (int(row[3]), int(row[2]))
        return graph

    def get_upgrade_script(self, level, to_version):
        """
        Return the upgrade script for a specific version.
        :param current_version: the version of the script to return.
        """
        script = super(TriblerChainDB, self).get_upgrade_script(level, to_version)
        if level == 0:
            script += u"""
            DROP TABLE IF EXISTS multi_chain;
            """
        return script

    def get_db_version(self, level=None):
        """
        Returns the current database version for a specific inheritance level. TrustChain = 0
        :param level: the inheritance level who's db version to get, or Null (default) to pass the entire version string
        :return: the current highest version of the database layout
        """
        # we can get away with this since the triblerchain does not have additional levels of sql schemas
        return LATEST_DB_VERSION
