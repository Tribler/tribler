from twisted.internet.defer import inlineCallbacks, succeed

from Tribler.community.dht.provider import DHTCommunityProvider
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class TestDHTProvider(TriblerCoreTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestDHTProvider, self).setUp(annotate=annotate)

        def mocked_find_values(key):
            return succeed(['\x01\x01\x01\x01\x04\xd2'])

        def mocked_store(key, value):
            self.stored_value = value
            return succeed([])

        self.cb_invoked = False
        self.stored_value = None
        self.dhtcommunity = MockObject()
        self.dhtcommunity.find_values = mocked_find_values
        self.dhtcommunity.store_value = mocked_store
        self.dhtcommunity.my_estimated_lan = ('1.1.1.1', 1234)
        self.dht_provider = DHTCommunityProvider(self.dhtcommunity, 1234)

    def test_lookup(self):
        def check_result(result):
            self.cb_invoked = True
            self.assertEqual(result[1], [self.dhtcommunity.my_estimated_lan])
        self.dht_provider.lookup('\x00' * 20, check_result)
        self.assertTrue(self.cb_invoked)

    def test_announce(self):
        self.dht_provider.announce('\x00' * 20)
        self.assertEqual(self.stored_value, '\x01\x01\x01\x01\x04\xd2')
