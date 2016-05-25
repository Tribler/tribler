import unittest

from twisted.python.threadable import registerAsIOThread

from Tribler.community.market.community import MarketCommunity
from Tribler.community.market.conversion import MarketConversion
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade
from Tribler.community.market.socket_address import SocketAddress
from Tribler.community.market.ttl import Ttl
from Tribler.community.tunnel.Socks5.server import Socks5Server
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.requestcache import RequestCache


class CommunityTestSuite(unittest.TestCase):
    """Community test cases."""

    def setUp(self):
        # Faking IOThread
        registerAsIOThread()

        # Object creation
        endpoint = ManualEnpoint(0)
        self.dispersy = Dispersy(endpoint, unicode("dispersy_temporary"))
        self.dispersy._database.open()
        endpoint.open(self.dispersy)

        # Faking wan address vote
        self.dispersy.wan_address_vote(('1.1.1.1', 1), Candidate(('1.1.1.1', 1), False))

        # Object creation
        self.master_member = DummyMember(self.dispersy, 1, "a" * 20)
        self.member = self.dispersy.get_new_member(u"curve25519")
        self.market_community = MarketCommunity.init_community(self.dispersy, self.master_member, self.member)
        self.market_community._request_cache = RequestCache()
        self.market_community.socks_server = Socks5Server(self, 1234)
        self.market_community.add_conversion(MarketConversion(self.market_community))

        self.tick = Tick(MessageId(TraderId('0'), MessageNumber('message_number')),
                         OrderId(TraderId('0'), OrderNumber("order_number")), Price(63400), Quantity(30),
                         Timeout(float("inf")), Timestamp(float("inf")), True)
        self.ask = Ask(MessageId(TraderId('0'), MessageNumber('message_number')),
                       OrderId(TraderId('0'), OrderNumber("order_number")), Price(63400), Quantity(30),
                       Timeout(1462224447.117), Timestamp(1462224447.117))
        self.bid = Bid(MessageId(TraderId('0'), MessageNumber('message_number')),
                       OrderId(TraderId('0'), OrderNumber("order_number")), Price(63400), Quantity(30),
                       Timeout(1462224447.117), Timestamp(1462224447.117))
        self.proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            OrderId(TraderId('0'), OrderNumber('order_number')),
                                            OrderId(TraderId('0'), OrderNumber('order_number')),
                                            Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.accepted_trade = Trade.accept(MessageId(TraderId('0'), MessageNumber('message_number')),
                                           Timestamp(1462224447.117), self.proposed_trade)
        self.declined_trade = Trade.decline(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            Timestamp(1462224447.117), self.proposed_trade)
        self.counter_trade = Trade.counter(MessageId(TraderId('0'), MessageNumber('message_number')),
                                           Quantity(15), Timestamp(1462224447.117), self.proposed_trade)

    def test_get_master_members(self):
        # Test for get masters members
        master_key = "3081a7301006072a8648ce3d020106052b8104002703819200040159af0c0925034bba3b4ea26661828e09247236059" \
                     "c773dac29ac9fb84d50fa6bd8acc035127a6f5c11873915f9b9a460e116ecccccfc5db1b5d8ba86bd701886ea45d8db" \
                     "bb634906989395d366888d008f4119ad0e7f45b9dab7fb3d78a0065c5f7a866b78cb8e59b9a7d048cc0d650c5a86bdf" \
                     "dabb434396d23945d1239f88de4935467424c7cc02b6579e45f63ee".decode("HEX")
        self.assertEquals(self.dispersy.get_member(public_key=master_key),
                          MarketCommunity.get_master_members(self.dispersy)[0])

    def test_lookup_ip(self):
        # Test for lookup ip
        self.market_community.update_ip(TraderId('0'), ("1.1.1.1", 0))
        self.assertEquals(("1.1.1.1", 0), self.market_community.lookup_ip(TraderId('0')))

    def test_create_ask(self):
        # Test for create ask
        self.market_community.create_ask(20, 100, 0.0)
        self.assertEquals(1, len(self.market_community.order_book._asks))
        self.assertEquals(0, len(self.market_community.order_book._bids))

    def test_on_ask(self):
        # Test for on ask
        meta = self.market_community.get_meta_message(u"ask")
        message = meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            payload=self.ask.to_network()[1] + (
                Ttl.default(), SocketAddress(self.dispersy.wan_address[0], self.dispersy.wan_address[1]))
        )
        self.market_community.on_ask([message])
        self.assertEquals(1, len(self.market_community.order_book._asks))
        self.assertEquals(0, len(self.market_community.order_book._bids))

    def test_create_bid(self):
        # Test for create ask
        self.market_community.create_bid(20, 100, 0.0)
        self.assertEquals(0, len(self.market_community.order_book._asks))
        self.assertEquals(1, len(self.market_community.order_book._bids))

    def test_on_bid(self):
        # Test for on bid
        meta = self.market_community.get_meta_message(u"bid")
        message = meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            payload=self.bid.to_network()[1] + (
                Ttl.default(), SocketAddress(self.dispersy.wan_address[0], self.dispersy.wan_address[1]))
        )
        self.market_community.on_bid([message])
        self.assertEquals(0, len(self.market_community.order_book._asks))
        self.assertEquals(1, len(self.market_community.order_book._bids))

    def test_check_history(self):
        # Test for check history
        self.assertTrue(self.market_community.check_history(self.tick))
        self.assertFalse(self.market_community.check_history(self.tick))

    def test_on_proposed_trade(self):
        # Test for on proposed trade
        self.market_community.update_ip(TraderId('0'), ('2.2.2.2', 2))
        self.market_community.update_ip(TraderId('1'), ('3.3.3.3', 3))
        destination, payload = self.proposed_trade.to_network()
        candidate = Candidate(self.market_community.lookup_ip(destination[0]), False)
        meta = self.market_community.get_meta_message(u"proposed-trade")
        message = meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )
        self.market_community.on_proposed_trade([message])

    def test_on_accepted_trade(self):
        # Test for on accepted trade
        self.market_community.update_ip(TraderId('0'), ('2.2.2.2', 2))
        self.market_community.update_ip(TraderId('1'), ('3.3.3.3', 3))
        destination, payload = self.accepted_trade.to_network()
        payload += (Ttl.default(),)
        meta = self.market_community.get_meta_message(u"accepted-trade")
        message = meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            payload=payload
        )
        self.market_community.on_accepted_trade([message])

    def test_on_declined_trade(self):
        # Test for on declined trade
        self.market_community.update_ip(TraderId('0'), ('2.2.2.2', 2))
        self.market_community.update_ip(TraderId('1'), ('3.3.3.3', 3))
        destination, payload = self.declined_trade.to_network()
        candidate = Candidate(self.market_community.lookup_ip(destination[0]), False)
        meta = self.market_community.get_meta_message(u"declined-trade")
        message = meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )
        self.market_community.on_declined_trade([message])

    def test_on_counter_trade(self):
        # Test for on counter trade
        self.market_community.update_ip(TraderId('0'), ('2.2.2.2', 2))
        self.market_community.update_ip(TraderId('1'), ('3.3.3.3', 3))
        destination, payload = self.counter_trade.to_network()
        candidate = Candidate(self.market_community.lookup_ip(destination[0]), False)
        meta = self.market_community.get_meta_message(u"counter-trade")
        message = meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )
        self.market_community.on_counter_trade([message])

    def test_send_proposed_trade(self):
        # Test for send proposed trade
        self.market_community.update_ip(TraderId('0'), ('2.2.2.2', 2))
        self.market_community.update_ip(TraderId('1'), ('3.3.3.3', 3))
        self.market_community.send_proposed_trade(self.proposed_trade)

    def test_send_accepted_trade(self):
        # Test for send accepted trade
        self.market_community.send_accepted_trade(self.accepted_trade)

    def test_send_declined_trade(self):
        # Test for send declined trade
        self.market_community.update_ip(TraderId('0'), ('2.2.2.2', 2))
        self.market_community.update_ip(TraderId('1'), ('3.3.3.3', 3))
        self.market_community.send_declined_trade(self.declined_trade)

    def test_send_counter_trade(self):
        # Test for send counter trade
        self.market_community.update_ip(TraderId('0'), ('2.2.2.2', 2))
        self.market_community.update_ip(TraderId('1'), ('3.3.3.3', 3))
        self.market_community.send_counter_trade(self.counter_trade)

    def tearDown(self):
        # Closing and unlocking dispersy database for other tests in test suite
        self.dispersy._database.close()


if __name__ == '__main__':
    unittest.main()
