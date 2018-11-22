from twisted.internet.defer import inlineCallbacks, succeed

from Tribler.Core.Modules.payout_manager import PayoutManager
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class TestPayoutManager(TriblerCoreTest):
    """
    This class contains various tests for the payout manager.
    """

    @inlineCallbacks
    def setUp(self):
        yield super(TestPayoutManager, self).setUp()

        fake_tc = MockObject()
        fake_tc.add_listener = lambda *_: None

        fake_response_peer = MockObject()
        fake_response_peer.public_key = MockObject()
        fake_response_peer.public_key.key_to_bin = lambda: 'a' * 64
        fake_dht = MockObject()
        fake_dht.connect_peer = lambda *_: succeed([fake_response_peer])

        self.payout_manager = PayoutManager(fake_tc, fake_dht)

    def test_do_payout(self):
        """
        Test doing a payout
        """
        self.payout_manager.do_payout('a')  # Does not exist
        self.payout_manager.update_peer('b', 'c', 10 * 1024 * 1024)
        self.payout_manager.update_peer('b', 'd', 1337)

        def mocked_sign_block(*_, **kwargs):
            tx = kwargs.pop('transaction')
            self.assertEqual(tx['down'], 10 * 1024 * 1024 + 1337)
            return succeed((None, None))

        self.payout_manager.bandwidth_wallet.trustchain.sign_block = mocked_sign_block
        self.payout_manager.do_payout('b')

    def test_update_peer(self):
        """
        Test the updating of a specific peer
        """
        self.payout_manager.update_peer('a', 'b', 1337)
        self.assertIn('a', self.payout_manager.tribler_peers)
        self.assertIn('b', self.payout_manager.tribler_peers['a'])
        self.assertEqual(self.payout_manager.tribler_peers['a']['b'], 1337)

        self.payout_manager.update_peer('a', 'b', 1338)
        self.assertEqual(self.payout_manager.tribler_peers['a']['b'], 1338)
