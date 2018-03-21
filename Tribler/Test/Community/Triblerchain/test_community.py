from Tribler.Test.ipv8_base import TestBase
from Tribler.Test.mocking.ipv8 import MockIPv8
from Tribler.Test.util.ipv8_util import twisted_wrapper
from Tribler.community.triblerchain.block import TriblerChainBlock
from Tribler.community.triblerchain.community import TriblerChainCrawlerCommunity


class TestTriblerChainCrawlerCommunity(TestBase):

    def setUp(self):
        super(TestTriblerChainCrawlerCommunity, self).setUp()
        self.initialize(TriblerChainCrawlerCommunity, 2)

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
            self.assertIsNotNone(self.nodes[node_nr].overlay.persistence.get(
                self.nodes[0].overlay.my_peer.public_key.key_to_bin(), 1))
