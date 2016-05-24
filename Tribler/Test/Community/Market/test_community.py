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

class CommunityTestSuite(unittest.TestCase):
    """Community test cases."""

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
        self.market_community.add_conversion(MarketConversion(self.market_community))

    def test_get_master_members(self):
        # Test for get masters members
        master_key = "3081a7301006072a8648ce3d020106052b8104002703819200040159af0c0925034bba3b4ea26661828e09247236059" \
                     "c773dac29ac9fb84d50fa6bd8acc035127a6f5c11873915f9b9a460e116ecccccfc5db1b5d8ba86bd701886ea45d8db" \
                     "bb634906989395d366888d008f4119ad0e7f45b9dab7fb3d78a0065c5f7a866b78cb8e59b9a7d048cc0d650c5a86bdf" \
                     "dabb434396d23945d1239f88de4935467424c7cc02b6579e45f63ee".decode("HEX")
        self.assertEquals(self.dispersy.get_member(public_key=master_key),
                          MarketCommunity.get_master_members(self.dispersy)[0])

    def tearDown(self):
        # Closing and unlocking dispersy database for other tests in test suite
        self.dispersy._database.close()

if __name__ == '__main__':
    unittest.main()
