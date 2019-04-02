from __future__ import absolute_import

from binascii import hexlify

from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.Modules.wallet.tc_wallet import TrustchainWallet
from Tribler.Core.Modules.wallet.wallet import InsufficientFunds
from Tribler.Test.tools import trial_timeout
from Tribler.pyipv8.ipv8.attestation.trustchain.community import TrustChainCommunity
from Tribler.pyipv8.ipv8.test.base import TestBase
from Tribler.pyipv8.ipv8.test.mocking.ipv8 import MockIPv8


class TestTrustchainWallet(TestBase):

    def setUp(self):
        super(TestTrustchainWallet, self).setUp()
        self.initialize(TrustChainCommunity, 2)
        self.tc_wallet = TrustchainWallet(self.nodes[0].overlay)
        self.tc_wallet.MONITOR_DELAY = 0.01
        self.tc_wallet.check_negative_balance = True

    def create_node(self):
        return MockIPv8(u"curve25519", TrustChainCommunity, working_directory=u":memory:")

    def test_get_mc_wallet_name(self):
        """
        Test the identifier of the Trustchain wallet
        """
        self.assertEqual(self.tc_wallet.get_name(), 'Tokens (MB)')

    def test_get_mc_wallet_id(self):
        """
        Test the identifier of a Trustchain wallet
        """
        self.assertEqual(self.tc_wallet.get_identifier(), 'MB')

    @trial_timeout(2)
    @inlineCallbacks
    def test_get_balance(self):
        """
        Test the balance retrieval of a Trustchain wallet
        """
        yield self.introduce_nodes()

        balance = yield self.tc_wallet.get_balance()
        self.assertEqual(balance['available'], 0)

        his_pubkey = self.nodes[0].network.verified_peers[0].public_key.key_to_bin()
        tx = {
            'up': 20 * 1024 * 1024,
            'down': 5 * 1024 * 1024,
            'total_up': 20 * 1024 * 1024,
            'total_down': 5 * 1024 * 1024
        }
        self.nodes[0].overlay.sign_block(self.nodes[0].network.verified_peers[0], public_key=his_pubkey,
                                         block_type=b'tribler_bandwidth', transaction=tx)

        yield self.deliver_messages()

        balance = yield self.tc_wallet.get_balance()
        self.assertEqual(balance['available'], 15)

    def test_create_wallet(self):
        """
        Test whether creating a Trustchain wallet raises an error
        """
        self.assertRaises(RuntimeError, self.tc_wallet.create_wallet)

    @inlineCallbacks
    def test_transfer_invalid(self):
        """
        Test the transfer method of a Trustchain wallet
        """
        test_deferred = Deferred()

        def on_error(failure):
            self.assertIsInstance(failure.value, InsufficientFunds)
            test_deferred.callback(None)

        self.tc_wallet.transfer(200, None).addErrback(on_error)
        yield test_deferred

    @inlineCallbacks
    def test_monitor_transaction(self):
        """
        Test the monitoring of a transaction in a Trustchain wallet
        """
        his_pubkey = self.nodes[0].overlay.my_peer.public_key.key_to_bin()

        tx_deferred = self.tc_wallet.monitor_transaction('%s.1' % hexlify(his_pubkey).decode('utf-8'))

        # Now create the transaction
        transaction = {
            'up': 20 * 1024 * 1024,
            'down': 5 * 1024 * 1024,
            'total_up': 20 * 1024 * 1024,
            'total_down': 5 * 1024 * 1024
        }
        self.nodes[1].overlay.sign_block(self.nodes[1].network.verified_peers[0], public_key=his_pubkey,
                                         block_type=b'tribler_bandwidth', transaction=transaction)

        yield tx_deferred

    @trial_timeout(2)
    @inlineCallbacks
    def test_monitor_tx_existing(self):
        """
        Test monitoring a transaction that already exists
        """
        transaction = {
            'up': 20 * 1024 * 1024,
            'down': 5 * 1024 * 1024,
            'total_up': 20 * 1024 * 1024,
            'total_down': 5 * 1024 * 1024
        }
        his_pubkey = self.nodes[0].overlay.my_peer.public_key.key_to_bin()
        yield self.nodes[1].overlay.sign_block(self.nodes[1].network.verified_peers[0], public_key=his_pubkey,
                                               block_type=b'tribler_bandwidth', transaction=transaction)
        yield self.tc_wallet.monitor_transaction('%s.1' % hexlify(his_pubkey).decode('utf-8'))

    def test_address(self):
        """
        Test the address of a Trustchain wallet
        """
        self.assertTrue(self.tc_wallet.get_address())

    @inlineCallbacks
    def test_get_transaction(self):
        """
        Test the retrieval of transactions of a Trustchain wallet
        """
        def on_transactions(transactions):
            self.assertIsInstance(transactions, list)

        yield self.tc_wallet.get_transactions().addCallback(on_transactions)

    def test_min_unit(self):
        """
        Test the minimum unit of a Trustchain wallet
        """
        self.assertEqual(self.tc_wallet.min_unit(), 1)

    @inlineCallbacks
    def test_get_statistics(self):
        """
        Test fetching statistics from a Trustchain wallet
        """
        self.tc_wallet.check_negative_balance = False
        res = self.tc_wallet.get_statistics()
        self.assertEqual(res["total_blocks"], 0)
        yield self.tc_wallet.transfer(5, self.nodes[1].overlay.my_peer)
        res = self.tc_wallet.get_statistics()
        self.assertTrue(res["latest_block"])
