"""
Tests for the incremental PageRank.
"""
from unittest import TestCase
from random import randint

from networkx import gnm_random_graph

from Tribler.community.multichain.statistics.page_rank import IncrementalPageRank


class TestIncrementalPageRank(TestCase):
    """
    As it is a Monte Carlo method, integration tests are often probabilistic in nature.
    Moreover, creating a directed graph with random weights on edges, even increases the randomness.
    That is, they might fail on rare occasions.
    """
    def create_graph(self, nr_of_nodes, nr_of_edges, nr_of_times=1):
        """
        Helper method to create a random graph.

        :param nr_of_nodes: amount of nodes in the random graph
        :param nr_of_edges: amount of edges in the random graph
        """
        self.graph = gnm_random_graph(nr_of_nodes, nr_of_edges, directed=True)
        for (u, v) in self.graph.edges():
            self.graph.edge[u][v]["weight"] = randint(0, 100)
        self.page_rank = IncrementalPageRank(self.graph)
        for _ in range(nr_of_times):
            self.page_rank.initial_walk()
            self.page_rank.count()
            self.ranks = self.page_rank.get_ranks()

    def test_single_node(self):
        """
        A single node should have a 1.0 ranking.
        """
        self.create_graph(1, 0)
        self.assertDictEqual(self.ranks, {0: 1.0})

    def test_two_nodes(self):
        """
        Two nodes with a single edge in between should both have a ranking close to 0.5.
        """
        nr_of_nodes = 2
        graph = gnm_random_graph(2, 1)
        for (u, v) in graph.edges():
            graph.edge[u][v]["weight"] = randint(0, 100)
        page_rank = IncrementalPageRank(graph)
        page_rank.initial_walk()
        page_rank.count()
        self.ranks = page_rank.get_ranks()
        self.assertAlmostEqual(self.ranks[0], float(1) / nr_of_nodes, delta=0.1)

    def test_max_rank_of_large_graph(self):
        """
        As the number of connections per node follows a power law in a random graph, only
        very rarely should the maximum PageRank of a single node be above 0.2 in a large graph.
        """
        nr_of_nodes = 1000
        self.create_graph(nr_of_nodes, round(0.5 * nr_of_nodes ** 2 / 2))
        self.assertGreater(0.2, max(self.ranks.values()))

    def tearDown(self):
        """
        All PageRank values should be between 0 and 1 and sum to 1 (while accounting for rounding errors).
        """
        self.assertTrue(all(0 <= rank <= 1 for rank in self.ranks.values()))
        self.assertAlmostEqual(sum(self.ranks.values()), 1, delta=0.01)

    def test_multiple_times(self):
        """
        All PageRank values should be between 0 and 1, even if called multiple times.
        """
        self.create_graph(10, 15, 10)
        self.assertTrue(all(0 <= rank <= 1 for rank in self.ranks.values()))
