"""
This file contains the functions to get the trust statistics from the database implemented in Tribler.
"""
from random import randint

from sqlite3 import connect
from networkx import random_regular_graph

from Tribler.community.multichain.block import MultiChainBlock
from Tribler.community.multichain.database import MultiChainDB


class StatisticsDB(MultiChainDB):
    """
    Statistics connection for the trust chain database.
    """

    def __init__(self, working_directory):
        """
        Sets up a database connection to the existing multi chain database.
        :param working_directory: directory of the database
        """
        super(StatisticsDB, self).__init__(working_directory)

    def total_up(self, public_key):
        """
        Gets the total uploaded value from the focus.
        :param public_key: public key of the focus node
        :return: number representing the amount of uploaded data
        """
        block = self.get_latest(public_key)
        return block.total_up if block else 0

    def total_down(self, public_key):
        """
        Gets the total downloaded value from the focus.
        :param public_key: public key of the focus node
        :return: number representing the amount of uploaded data
        """
        block = self.get_latest(public_key)
        return block.total_down if block else 0

    def neighbor_list(self, public_key):
        """
        Return a dictionary containing information about all neighbors of the focus node.
        For each neighbor, the dictionary contains a key equal to the primary key of the neighbor.
        The value stored under that key is a dictionary containing how much data has been uploaded
        and downloaded to and from that neighbor.
        :param public_key: primary key of the focus node
        :return: dictionary with for each neighbor of the focus a key, value entry: primary key neighbor, dictionary
        containing the amount of data uploaded and downloaded from that neighbor
        """
        query = u"SELECT link_public_key, sum(up), sum(down) FROM multi_chain " \
                u"WHERE public_key = ? GROUP BY link_public_key"
        params = (buffer(public_key),)
        db_result = self.execute(query, params).fetchall()

        neighbors = {}
        for row in db_result:
            neighbor_pk = row[0] if isinstance(row[0], str) else str(row[0])
            neighbors[neighbor_pk] = {"up": row[1] or 0, "down": row[2] or 0}

        return neighbors


class StatisticsTestDB(StatisticsDB):
    """
    Statistics database filled with test data.
    """

    def __init__(self, working_directory):
        """
        Fills a database with random test data.
        """
        super(StatisticsTestDB, self).__init__(working_directory)

        self.close()

        self._connection = connect(":memory:")
        self._cursor = self._connection.cursor()

        self.check_database(u"0")

        seq_num = 0

        edges = random_regular_graph(4, 26).edges()

        for edge in edges:
            up = randint(101, 200)
            down = randint(121, 200)
            from_node = str(edge[0])
            to_node = str(edge[1])
            seq_1 = seq_num
            seq_2 = seq_num + 1
            seq_num += 2
            self.add_block(MultiChainBlock([up, down, self.total_up(from_node) + up, self.total_down(from_node) + down,
                                            from_node, seq_1, to_node, seq_2, '', '', None]))
            self.add_block(MultiChainBlock([down, up, self.total_up(to_node) + down, self.total_down(to_node) + up,
                                            to_node, seq_2, from_node, seq_1, '', '', None]))
