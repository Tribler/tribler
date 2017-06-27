from twisted.internet.defer import inlineCallbacks, returnValue

from Tribler.Test.Community.Trustchain.test_community import BaseTestTrustChainCommunity
from Tribler.community.tradechain.community import TradeChainCommunity
from Tribler.dispersy.tests.dispersytestclass import DispersyTestFunc
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTradeChainCommunity(BaseTestTrustChainCommunity):
    """
    Class that tests the TradeChainCommunity on an integration level.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def create_nodes(self, *args, **kwargs):
        nodes = yield DispersyTestFunc.create_nodes(self, *args, community_class=TradeChainCommunity,
                                                    memory_database=False, **kwargs)
        for outer in nodes:
            for inner in nodes:
                if outer != inner:
                    outer.send_identity(inner)

        returnValue(nodes)

    def test_should_sign_no_market(self):
        """
        Test whether the should_sign method return False when there is no market community
        """
        node, = self.create_nodes(1)
        self.assertFalse(node.community.should_sign(None))
