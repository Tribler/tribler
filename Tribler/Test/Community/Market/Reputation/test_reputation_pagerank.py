from Tribler.Test.Community.Market.Reputation.test_reputation_base import TestReputationBase
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity


class TestReputationPagerank(TestReputationBase):
    """
    Contains tests to test the reputation based on pagerank
    """

    def test_pagerank_1(self):
        """
        Test a very simple Temporal Pagerank computation
        """
        self.insert_transaction('a', 'b', Quantity(1, 'BTC'), Price(1, 'MC'))
        rep_dict = self.compute_reputations()
        self.assertTrue('a' in rep_dict)
        self.assertTrue('b' in rep_dict)
        self.assertGreater(rep_dict['a'], 0)
        self.assertGreater(rep_dict['b'], 0)

    def test_pagerank_2(self):
        """
        Test isolated nodes during a Temporal Pagerank computation
        """
        self.insert_transaction('a', 'b', Quantity(1, 'BTC'), Price(1, 'MC'))
        self.insert_transaction('c', 'd', Quantity(1, 'BTC'), Price(1, 'MC'))
        rep_dict = self.compute_reputations()
        self.assertTrue('c' in rep_dict)
        self.assertTrue('d' in rep_dict)

    def test_pagerank_3(self):
        """
        Test a more involved example of a Temporal Pagerank computation
        """
        self.insert_transaction('a', 'b', Quantity(1, 'BTC'), Price(1, 'MC'))
        self.insert_transaction('b', 'c', Quantity(100, 'BTC'), Price(100, 'MC'))
        self.insert_transaction('b', 'd', Quantity(100, 'BTC'), Price(100, 'MC'))
        self.insert_transaction('b', 'e', Quantity(100, 'BTC'), Price(100, 'MC'))
        rep_dict = self.compute_reputations()
        self.assertEqual(len(rep_dict.keys()), 5)
        for _, rep in rep_dict.iteritems():
            self.assertGreater(rep, 0)

    def test_pagerank_4(self):
        """
        Test an empty pagerank computation
        """
        rep_dict = self.compute_reputations()
        self.assertDictEqual(rep_dict, {})

    def test_pagerank_5(self):
        """
        Test a Temporal Pagerank computation
        """
        self.insert_transaction('a', 'b', Quantity(1, 'BTC'), Price(1, 'MC'))
        self.insert_transaction('a', 'c', Quantity(1, 'BTC'), Price(2, 'MC'))
        self.insert_transaction('a', 'd', Quantity(1, 'BTC'), Price(3, 'MC'))
        self.insert_transaction('a', 'e', Quantity(1, 'BTC'), Price(4, 'MC'))
        self.insert_transaction('a', 'f', Quantity(1, 'BTC'), Price(5, 'MC'))
        self.insert_transaction('a', 'g', Quantity(1, 'BTC'), Price(6, 'MC'))
        self.insert_transaction('a', 'h', Quantity(1, 'BTC'), Price(7, 'MC'))
        rep_dict = self.compute_reputations()
        self.assertTrue('c' in rep_dict)
        self.assertTrue('d' in rep_dict)
