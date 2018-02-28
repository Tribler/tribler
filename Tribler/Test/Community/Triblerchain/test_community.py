from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.ipv8_base import TestBase
from Tribler.Test.mocking.ipv8 import MockIPv8
from Tribler.Test.util.ipv8_util import twisted_wrapper
from Tribler.community.triblerchain.block import TriblerChainBlock
from Tribler.community.triblerchain.community import TriblerChainCommunity, TriblerChainCrawlerCommunity
from Tribler.pyipv8.ipv8.messaging.anonymization.tunnel import Circuit


class TestTriblerChainCommunity(TestBase):

    def setUp(self):
        super(TestTriblerChainCommunity, self).setUp()
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


class TestTriblerChainCrawlerCommunity(TestBase):

    def setUp(self):
        super(TestTriblerChainCrawlerCommunity, self).setUp()
        self.initialize(TriblerChainCrawlerCommunity, 2)
        self.nodes[0].overlay.SIGN_DELAY = 0
        self.nodes[1].overlay.SIGN_DELAY = 0

    def create_node(self):
        return MockIPv8(u"curve25519", TriblerChainCrawlerCommunity, working_directory=u":memory:")

    @twisted_wrapper
    def test_crawl_request(self):
        """
        Test whether a crawl request is sent when receiving an introduction response
        """
        his_pk = self.nodes[1].overlay.my_peer.public_key.key_to_bin()
        block = TriblerChainBlock.create({'up': 20, 'down': 40},
                                         self.nodes[0].overlay.persistence,
                                         self.nodes[0].overlay.my_peer.public_key.key_to_bin(),
                                         link=None, link_pk=his_pk)
        block.sign(self.nodes[0].overlay.my_peer.key)
        self.nodes[0].overlay.persistence.add_block(block)

        yield self.introduce_nodes()

        # The block should be available in the databases of both involved parties.
        for node_nr in [0, 1]:
            self.assertIsNotNone(self.nodes[node_nr].overlay.persistence.get(his_pk, 1))
