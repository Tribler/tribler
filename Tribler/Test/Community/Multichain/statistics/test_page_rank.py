from unittest import TestCase

from networkx import gnm_random_graph

from Tribler.community.multichain.statistics.page_rank import IncrementalPageRank


class TestIncrementalPageRank(TestCase):
    """
    As it is a Monte Carlo method, integration tests can only be basic.
    """
    def setUp(self):
        nr_of_nodes = 1000
        nr_of_edges = 100000
        self.graph = gnm_random_graph(nr_of_nodes, nr_of_edges)
        self.page_rank = IncrementalPageRank(self.graph)

    def test_max_min(self):
        self.page_rank.initial_walk()
        self.page_rank.count()
        ranks = self.page_rank.get_ranks()
        self.assertTrue(all(0 <= rank <= 1 for rank in ranks.values()))
        total_rounding_errors_bound = 0.05
        self.assertAlmostEqual(sum(ranks.values()), 1, delta=total_rounding_errors_bound)
