from twisted.internet.defer import inlineCallbacks, Deferred, succeed

from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import AbstractServer
from Tribler.Test.twisted_thread import deferred
from Tribler.community.market.wallet.tc_wallet import TrustchainWallet
from Tribler.community.market.wallet.wallet import InsufficientFunds
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTrustchainWallet(AbstractServer):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestTrustchainWallet, self).setUp(annotate=annotate)

        latest_block = MockObject()
        latest_block.transaction = {"total_up": 10 * 1024 * 1024, "total_down": 5 * 1024 * 1024}
        latest_block.previous_hash_requester = 'b' * 5

        self.tc_community = MockObject()
        self.tc_community.add_discovered_candidate = lambda _: None
        self.tc_community.create_introduction_request = lambda *_: None
        self.tc_community.wait_for_intro_of_candidate = lambda _: succeed(None)
        self.tc_community.received_payment_message = lambda *_: None
        self.tc_community.sign_block = lambda *_: None
        self.tc_community.wait_for_signature_request = lambda _: succeed('a')
        self.tc_community.my_member = MockObject()
        self.tc_community.my_member.public_key = 'a' * 20
        self.tc_community.persistence = MockObject()
        self.tc_community.persistence.get_latest = lambda _: latest_block
        self.tc_community.get_candidate = lambda _: MockObject()

        self.tc_wallet = TrustchainWallet(self.tc_community)

    def test_get_mc_wallet_name(self):
        """
        Test the identifier of the Trustchain wallet
        """
        self.assertEqual(self.tc_wallet.get_name(), 'Reputation')

    def test_get_mc_wallet_id(self):
        """
        Test the identifier of a Trustchain wallet
        """
        self.assertEqual(self.tc_wallet.get_identifier(), 'MC')

    @deferred(timeout=10)
    def test_get_balance(self):
        """
        Test the balance retrieval of a Trustchain wallet
        """
        def on_balance(balance):
            self.assertEqual(balance['available'], 5)

        return self.tc_wallet.get_balance().addCallback(on_balance)

    def test_create_wallet(self):
        """
        Test whether creating a Trustchain wallet raises an error
        """
        self.assertRaises(RuntimeError, self.tc_wallet.create_wallet)

    @deferred(timeout=10)
    def test_transfer_invalid(self):
        """
        Test the transfer method of a Trustchain wallet
        """
        test_deferred = Deferred()

        def on_error(failure):
            self.assertIsInstance(failure.value, InsufficientFunds)
            test_deferred.callback(None)

        self.tc_wallet.transfer(200, None).addErrback(on_error)
        return test_deferred

    @deferred(timeout=10)
    def test_transfer_missing_member(self):
        """
        Test the transfer method of a Trustchain wallet with a missing member
        """
        candidate = MockObject()
        candidate.get_member = lambda: None
        candidate.sock_addr = None
        self.tc_wallet.check_negative_balance = False
        self.tc_wallet.send_signature = lambda *_: None
        return self.tc_wallet.transfer(200, candidate)

    @deferred(timeout=10)
    def test_monitor_transaction(self):
        """
        Test the monitoring of a transaction in a Trustchain wallet
        """
        def on_transaction(transaction):
            self.assertEqual(transaction, 'a')

        return self.tc_wallet.monitor_transaction('abc.1').addCallback(on_transaction)

    def test_address(self):
        """
        Test the address of a Trustchain wallet
        """
        self.assertIsInstance(self.tc_wallet.get_address(), str)

    @deferred(timeout=10)
    def test_get_transaction(self):
        """
        Test the retrieval of transactions of a dummy wallet
        """

        def on_transactions(transactions):
            self.assertIsInstance(transactions, list)

        return self.tc_wallet.get_transactions().addCallback(on_transactions)

    def test_min_unit(self):
        """
        Test the minimum unit of a Trustchain wallet
        """
        self.assertEqual(self.tc_wallet.min_unit(), 1)

    def test_wait_for_intro_of_candidate(self):
        """
        Test waiting for an introduction candidate in the TrustChain wallet
        """
        candidate = MockObject()
        candidate.sock_addr = None
        return self.tc_wallet.wait_for_intro_of_candidate(candidate)
