import unittest
import os
from mock import Mock, MagicMock

from Tribler.dispersy.candidate import Candidate
from Tribler.community.market.core.bitcoin_address import BitcoinAddress
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.payment_provider import BitcoinPaymentProvider, MultiChainPaymentProvider, \
    InsufficientFunds


class BitcoinPaymentProviderTestSuite(unittest.TestCase):
    """Bitcoin payment provider test cases."""

    def setUp(self):
        # Object creation
        self.bitcoin_payment_provider = BitcoinPaymentProvider()

    def test_balance_empty(self):
        # Test for balance when there is no bitcoin balance information
        os.system = MagicMock(return_value='{}')
        self.assertEquals(0, int(self.bitcoin_payment_provider.balance()))

    def test_balance(self):
        # Test for balance
        os.system = MagicMock(return_value='{"confirmed": "1", "unconfirmed": "0"}')
        self.assertEquals(1000, int(self.bitcoin_payment_provider.balance()))

    def test_transfer_bitcoin_empty(self):
        # Test for bitcoin transfer when there is insufficient bitcoin
        os.system = MagicMock(return_value='{"confirmed": "0", "unconfirmed": "0"}')
        with self.assertRaises(InsufficientFunds):
            self.bitcoin_payment_provider.transfer_bitcoin(BitcoinAddress("0"), Quantity(1000))

    def test_transfer_bitcoin(self):
        # Test for bitcoin transfer
        os.system = MagicMock(return_value='{"confirmed": "1", "unconfirmed": "0"}')
        self.bitcoin_payment_provider.transfer_bitcoin(BitcoinAddress("0"), Quantity(10))


class MultiChainPaymentProviderTestSuite(unittest.TestCase):
    """Multi chain payment provider test cases."""

    def setUp(self):
        # Mock creation
        self.multi_chain_community_mock = Mock()
        self.candidate = Mock(spec=Candidate)

        # Object creation
        self.multi_chain_payment_provider = MultiChainPaymentProvider(self.multi_chain_community_mock, "0")

    def test_balance_empty(self):
        # Test for balance when there is no multi chain balance information
        self.multi_chain_community_mock.persistence.get_total.return_value = (-1, -1)
        self.assertEquals(0, int(self.multi_chain_payment_provider.balance()))

    def test_balance(self):
        # Test for balance
        self.multi_chain_community_mock.persistence.get_total.return_value = (2000, 1000)
        self.assertEquals(5, int(self.multi_chain_payment_provider.balance()))

    def test_transfer_multi_chain_empty(self):
        # Test for multi chain transfer when there is no multi chain balance information
        self.multi_chain_community_mock.persistence.get_total.return_value = (-1, -1)
        with self.assertRaises(InsufficientFunds):
            self.multi_chain_payment_provider.transfer_multi_chain(self.candidate, Quantity(1000))

    def test_multi_chain(self):
        # Test for multi chain transfer
        self.multi_chain_community_mock.persistence.get_total.return_value = (2000, 0)
        self.multi_chain_payment_provider.transfer_multi_chain(self.candidate, Quantity(1))


if __name__ == '__main__':
    unittest.main()
