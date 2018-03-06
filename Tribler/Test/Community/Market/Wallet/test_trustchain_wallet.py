from Tribler.Test.ipv8_base import TestBase
from Tribler.Test.mocking.ipv8 import MockIPv8
from Tribler.Test.util.ipv8_util import twisted_wrapper
from Tribler.community.market.wallet.tc_wallet import TrustchainWallet
from Tribler.community.market.wallet.wallet import InsufficientFunds
from Tribler.pyipv8.ipv8.attestation.trustchain.community import TrustChainCommunity
from twisted.internet.defer import Deferred


class TestTrustchainWallet(TestBase):

    def setUp(self):
        super(TestTrustchainWallet, self).setUp()
        self.initialize(TrustChainCommunity, 2)
        self.tc_wallet = TrustchainWallet(self.nodes[0].overlay)
        self.tc_wallet.MONITOR_DELAY = 0.01

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

    @twisted_wrapper
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
        self.nodes[0].overlay.sign_block(self.nodes[0].network.verified_peers[0], public_key=his_pubkey, transaction=tx)

        yield self.deliver_messages()

        balance = yield self.tc_wallet.get_balance()
        self.assertEqual(balance['available'], 15)

    def test_create_wallet(self):
        """
        Test whether creating a Trustchain wallet raises an error
        """
        self.assertRaises(RuntimeError, self.tc_wallet.create_wallet)

    @twisted_wrapper
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

    @twisted_wrapper
    def test_monitor_transaction(self):
        """
        Test the monitoring of a transaction in a Trustchain wallet
        """
        his_pubkey = self.nodes[0].overlay.my_peer.public_key.key_to_bin()

        tx_deferred = self.tc_wallet.monitor_transaction('%s.1' % his_pubkey.encode('hex'))

        # Now create the transaction
        self.nodes[1].overlay.sign_block(self.nodes[1].network.verified_peers[0], public_key=his_pubkey, transaction={})

        yield tx_deferred

    def test_address(self):
        """
        Test the address of a Trustchain wallet
        """
        self.assertIsInstance(self.tc_wallet.get_address(), str)

    @twisted_wrapper
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
