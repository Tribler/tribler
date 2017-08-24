from Tribler.Test.Community.Market.Reputation.test_reputation_base import TestReputationBase
from Tribler.community.market.reputation.pagerank_manager import PagerankReputationManager


class TestReputationPagerank(TestReputationBase):
    """
    Contains tests to test the reputation based on pagerank
    """

    def test_pagerank_1(self):
        self.insert_transaction('a', 'b', 1, 20, 2, 20)
        self.insert_transaction('a', 'b', 1, 20, 2, 20)
        self.insert_transaction('b', 'c', 1, 20, 2, 20)
        self.insert_transaction('b', 'd', 1, 20, 2, 20)
        self.insert_transaction('d', 'e', 1, 10, 2, 10)

        blocks = self.market_db.get_all_blocks()
        rep_manager = PagerankReputationManager(blocks)
        rep = rep_manager.compute(own_public_key='a')
        self.assertIsInstance(rep, dict)
