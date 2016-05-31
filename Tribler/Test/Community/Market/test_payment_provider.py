import unittest
from mock import Mock

from Tribler.dispersy.candidate import Candidate
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.payment_provider import MultiChainPaymentProvider, InsufficientFunds


class MultiChainPaymentProviderTestSuite(unittest.TestCase):
    """Multi chain payment provider test cases."""

    def setUp(self):
        self.multi_chain_community_mock = Mock()
        self.candidate = Mock(spec=Candidate)
        self.multi_chain_payment_provider = MultiChainPaymentProvider(self.multi_chain_community_mock, "0")

    def test_balance_empty(self):
        self.multi_chain_community_mock.persistence.get_total.return_value = (-1, -1)
        self.assertEquals(0, int(self.multi_chain_payment_provider.balance()))

    def test_balance(self):
        self.multi_chain_community_mock.persistence.get_total.return_value = (2000, 1000)
        self.assertEquals(5, int(self.multi_chain_payment_provider.balance()))

    def test_multi_chain_empty(self):
        self.multi_chain_community_mock.persistence.get_total.return_value = (-1, -1)
        with self.assertRaises(InsufficientFunds):
            self.multi_chain_payment_provider.transfer_multi_chain(self.candidate, Quantity(1000))

    def test_multi_chain(self):
        self.multi_chain_community_mock.persistence.get_total.return_value = (2000, 0)
        self.multi_chain_payment_provider.transfer_multi_chain(self.candidate, Quantity(1))


if __name__ == '__main__':
    unittest.main()
