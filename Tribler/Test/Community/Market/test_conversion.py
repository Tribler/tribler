import unittest
import os

from twisted.python.threadable import registerAsIOThread

from Tribler.community.market.community import MarketCommunity
from Tribler.community.market.conversion import MarketConversion
from Tribler.community.tunnel.Socks5.server import Socks5Server
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.requestcache import RequestCache
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout


class ConversionTestSuite(unittest.TestCase):
    """Conversion test cases."""

    def setUp(self):
        # Faking IOThread
        registerAsIOThread()

        # Object creation and preperation
        self.dispersy = Dispersy(ManualEnpoint(0), unicode("dispersy_temporary"))
        self.dispersy._database.open()
        self.master_member = DummyMember(self.dispersy, 1, "a" * 20)
        self.member = self.dispersy.get_new_member(u"curve25519")
        self.market_community = MarketCommunity.init_community(self.dispersy, self.master_member, self.member)
        self.market_community._request_cache = RequestCache()
        self.market_community.socks_server = Socks5Server(self, 1234)
        self.market_conversion = MarketConversion(self.market_community)
        self.market_community.add_conversion(self.market_conversion)

    def test_init(self):
        self.assertIsInstance(self.market_conversion, MarketConversion)

if __name__ == '__main__':
    unittest.main()
