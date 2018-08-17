from twisted.internet.defer import inlineCallbacks, Deferred

from Tribler.Core.DecentralizedTracking.dht_provider import MainlineDHTProvider
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class TestDHTProvider(TriblerCoreTest):

    @inlineCallbacks
    def setUp(self):
        yield super(TestDHTProvider, self).setUp()

        self.cb_invoked = False

        def mocked_get_peers(infohash, ih_id, cb, bt_port=None):
            cb(infohash, {}, None)
            self.cb_invoked = True

        self.test_deferred = Deferred()
        self.mock_mainline_dht = MockObject()
        self.mock_mainline_dht.get_peers = mocked_get_peers
        self.dht_provider = MainlineDHTProvider(self.mock_mainline_dht, 1234)

    def test_lookup(self):
        """
        Test the lookup method
        """
        self.dht_provider.lookup('a' * 20, lambda *_: None)
        self.assertTrue(self.cb_invoked)

    def test_announce(self):
        """
        Test the announce method of the DHT provider
        """
        self.dht_provider.announce('a' * 20)
        self.assertTrue(self.cb_invoked)
