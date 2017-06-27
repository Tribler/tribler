from Tribler.Test.Community.Market.Reputation.test_reputation_base import TestReputationBase
from Tribler.community.market.reputation.reputation_manager import ReputationManager


class TestReputationManager(TestReputationBase):
    """
    Contains tests to test the reputation manager
    """

    def test_compute(self):
        """
        Test the base compute method of the reputation manager
        """
        rep_mgr = ReputationManager(None)
        self.assertRaises(NotImplementedError, rep_mgr.compute, 'a')
