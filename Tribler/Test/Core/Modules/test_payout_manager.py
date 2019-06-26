from __future__ import absolute_import

from twisted.internet.defer import inlineCallbacks, succeed

from Tribler.Core.Modules.payout_manager import PayoutManager
from Tribler.Test.Core.base_test import MockObject, TriblerCoreTest


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
        fake_response_peer.public_key.key_to_bin = lambda: b'a' * 64
        fake_dht = MockObject()
        fake_dht.connect_peer = lambda *_: succeed([fake_response_peer])

        self.payout_manager = PayoutManager(fake_tc, fake_dht)

    def test_do_payout(self):
        """
        Test doing a payout
        """
        self.payout_manager.do_payout(b'a')  # Does not exist
        self.payout_manager.update_peer(b'b', b'c', 10 * 1024 * 1024)
        self.payout_manager.update_peer(b'b', b'd', 1337)

        def mocked_sign_block(*_, **kwargs):
            tx = kwargs.pop('transaction')
            self.assertEqual(tx['down'], 10 * 1024 * 1024 + 1337)
            return succeed((None, None))

        self.payout_manager.bandwidth_wallet.trustchain.sign_block = mocked_sign_block
        self.payout_manager.do_payout(b'b')

    def test_update_peer(self):
        """
        Test the updating of a specific peer
        """
        self.payout_manager.update_peer(b'a', b'b', 1337)
        self.assertIn(b'a', self.payout_manager.tribler_peers)
        self.assertIn(b'b', self.payout_manager.tribler_peers[b'a'])
        self.assertEqual(self.payout_manager.tribler_peers[b'a'][b'b'], 1337)

        self.payout_manager.update_peer(b'a', b'b', 1338)
        self.assertEqual(self.payout_manager.tribler_peers[b'a'][b'b'], 1338)
