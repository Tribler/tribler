from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.ipv8_base import TestBase
from Tribler.Test.mocking.ipv8 import MockIPv8
from Tribler.Test.util.ipv8_util import twisted_wrapper
from Tribler.community.triblerchain.community import TriblerChainCommunity
from Tribler.pyipv8.ipv8.messaging.anonymization.tunnel import Circuit


class TestTriblerchainCommunity(TestBase):

    def setUp(self):
        super(TestTriblerchainCommunity, self).setUp()
        self.initialize(TriblerChainCommunity, 2)
        self.nodes[0].overlay.SIGN_DELAY = 0
        self.nodes[1].overlay.SIGN_DELAY = 0

    def create_node(self):
        return MockIPv8(u"curve25519", TriblerChainCommunity, working_directory=u":memory:")

    @twisted_wrapper
    def test_on_tunnel_remove(self):
        """
        Test whether a message is created when a tunnel has been removed
        """
        tribler_session = MockObject()
        tribler_session.lm = MockObject()
        tribler_session.lm.tunnel_community = MockObject()
        tribler_session.lm.tunnel_community.network = self.nodes[0].overlay.network
        self.nodes[0].overlay.tribler_session = tribler_session

        circuit = Circuit(3)
        circuit.bytes_up = 50 * 1024 * 1024
        self.nodes[0].overlay.on_tunnel_remove(None, None, circuit,
                                               self.nodes[0].overlay.network.verified_peers[0].address)

        yield self.sleep(time=0.1)

        my_pk = self.nodes[0].overlay.my_peer.public_key.key_to_bin()
        self.assertTrue(self.nodes[0].overlay.persistence.get(my_pk, 1))
