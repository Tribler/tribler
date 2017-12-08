import hashlib

from twisted.internet.defer import inlineCallbacks, Deferred

from Tribler.Test.twisted_thread import deferred
from Tribler.Test.Community.AbstractTestCommunity import AbstractTestCommunity
from Tribler.Test.Core.base_test import MockObject
from Tribler.community.market.community import MarketCommunity, ProposedTradeRequestCache
from Tribler.community.market.core.message import TraderId, MessageId, MessageNumber
from Tribler.community.market.core.order import OrderId, OrderNumber, Order
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade, CounterTrade
from Tribler.community.market.core.transaction import StartTransaction
from Tribler.community.market.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from Tribler.dispersy.candidate import Candidate, WalkCandidate
from Tribler.dispersy.crypto import ECCrypto
from Tribler.dispersy.member import Member
from Tribler.dispersy.message import DelayMessageByProof, Message, DropMessage
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class AbstractTestMarketCommunity(AbstractTestCommunity):
    """Market Community test cases."""

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(AbstractTestMarketCommunity, self).setUp(annotate=annotate)

        dummy1_wallet = DummyWallet1()
        dummy2_wallet = DummyWallet2()

        self.market_community = MarketCommunity(self.dispersy, self.master_member, self.member)
        self.market_community.initialize(wallets={dummy1_wallet.get_identifier(): dummy1_wallet,
                                                  dummy2_wallet.get_identifier(): dummy2_wallet}, use_database=False)
        self.market_community.use_local_address = True
        self.dispersy._lan_address = ("127.0.0.1", 1234)
        self.dispersy._endpoint.open(self.dispersy)

        self.dispersy.attach_community(self.market_community)

        eccrypto = ECCrypto()
        ec = eccrypto.generate_key(u"curve25519")
        member = Member(self.dispersy, ec, 1)

        trader_id = hashlib.sha1(member.public_key).digest().encode('hex')
        self.ask = Ask(OrderId(TraderId(trader_id), OrderNumber(1234)), Price(63400, 'DUM1'), Quantity(30, 'DUM2'),
                       Timeout(3600), Timestamp.now())
        self.bid = Bid(OrderId(TraderId(trader_id), OrderNumber(1235)), Price(343, 'DUM1'), Quantity(22, 'DUM2'),
                       Timeout(3600), Timestamp.now())
        self.order = Order(OrderId(TraderId(self.market_community.mid), OrderNumber(24)), Price(20, 'DUM1'),
                           Quantity(30, 'DUM2'), Timeout(3600.0), Timestamp.now(), False)
        self.proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            OrderId(TraderId('0'), OrderNumber(23)),
                                            OrderId(TraderId(self.market_community.mid), OrderNumber(24)),
                                            Price(20, 'DUM1'), Quantity(30, 'DUM2'), Timestamp.now())


class CommunityTestSuite(AbstractTestMarketCommunity):
    @blocking_call_on_reactor_thread
    def test_get_master_members(self):
        """
        Test retrieval of the master members of the Market community
        """
        self.assertTrue(MarketCommunity.get_master_members(self.dispersy))

    @blocking_call_on_reactor_thread
    def test_disable_matchmaker(self):
        """
        Test the disabling of the matchmaker functionality
        """
        self.market_community.disable_matchmaker()
        self.assertIsNone(self.market_community.order_book)
        self.assertFalse(self.market_community.is_matchmaker)

    @deferred(timeout=10)
    def test_add_matchmaker(self):
        """
        Test adding a matchmaker to the market
        """
        test_deferred = Deferred()
        self.market_community.pending_matchmaker_deferreds.append(test_deferred)
        self.market_community.get_candidate = lambda *_: 'a'
        self.market_community.add_matchmaker(None)
        return test_deferred

    @blocking_call_on_reactor_thread
    def test_should_sign(self):
        """
        Test the should_sign method of the market
        """
        message = MockObject()
        message.payload = MockObject()
        message.payload.block = MockObject()
        message.payload.block.transaction = {"type": "abc"}
        self.assertFalse(self.market_community.should_sign(message))

    @blocking_call_on_reactor_thread
    def test_proposed_trade_cache_timeout(self):
        """
        Test the timeout method of a proposed trade request in the cache
        """
        ask = Ask(OrderId(TraderId(self.market_community.mid), OrderNumber(24)),
                  Price(63400, 'DUM1'), Quantity(30, 'DUM2'), Timeout(3600), Timestamp.now())
        order = Order(OrderId(TraderId("0"), OrderNumber(23)), Price(20, 'DUM1'), Quantity(30, 'DUM2'),
                      Timeout(3600.0), Timestamp.now(), False)
        self.market_community.order_book.insert_ask(ask)
        self.assertEqual(len(self.market_community.order_book.asks), 1)
        self.market_community.order_manager.order_repository.add(order)
        order.reserve_quantity_for_tick(self.proposed_trade.recipient_order_id, Quantity(30, 'DUM2'))
        self.market_community.order_manager.order_repository.update(order)

        mocked_match_message = MockObject()
        mocked_match_message.payload = MockObject()
        mocked_match_message.payload.matchmaker_trader_id = 'a'
        self.market_community.incoming_match_messages['a'] = mocked_match_message

        def mocked_send_decline(*_):
            mocked_send_decline.called = True

        mocked_send_decline.called = False
        self.market_community.send_decline_match_message = mocked_send_decline

        cache = ProposedTradeRequestCache(self.market_community, self.proposed_trade, 'a')
        cache.on_timeout()
        self.assertTrue(mocked_send_decline.called)

    def get_offer_sync(self, tick):
        meta = self.market_community.get_meta_message(u"offer-sync")
        candidate = Candidate(self.market_community.lookup_ip(TraderId(self.market_community.mid)), False)
        return meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            destination=(candidate,),
            payload=tick.to_network() + (Ttl(1),) + ("127.0.0.1", 1234) + (isinstance(tick, Ask),)
        )

    def get_start_transaction_msg(self):
        transaction = self.market_community.transaction_manager.create_from_proposed_trade(self.proposed_trade, 'abcd')
        start_transaction = StartTransaction(self.market_community.message_repository.next_identity(),
                                             transaction.transaction_id, transaction.order_id,
                                             self.proposed_trade.order_id, self.proposed_trade.proposal_id,
                                             self.proposed_trade.price, self.proposed_trade.quantity, Timestamp.now())

        meta = self.market_community.get_meta_message(u"start-transaction")
        candidate = Candidate(self.market_community.lookup_ip(TraderId(self.market_community.mid)), False)
        return meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            destination=(candidate,),
            payload=start_transaction.to_network()
        )

    @blocking_call_on_reactor_thread
    def test_verify_offer_creation(self):
        """
        Test creation of an offer in the community
        """
        self.assertRaises(RuntimeError, self.market_community.verify_offer_creation,
                          Price(3, 'MC'), 'ABC', Quantity(4, 'BTC'), 'ABC')
        self.assertRaises(RuntimeError, self.market_community.verify_offer_creation,
                          Price(3, 'MC'), 'ABC', Quantity(4, 'BTC'), 'MC')
        self.assertRaises(RuntimeError, self.market_community.verify_offer_creation,
                          Price(1, 'DUM1'), 'DUM1', Quantity(1, 'BTC'), 'BTC')
        self.assertRaises(RuntimeError, self.market_community.verify_offer_creation,
                          Price(0.1, 'DUM1'), 'DUM1', Quantity(1, 'DUM2'), 'DUM2')
        self.assertRaises(RuntimeError, self.market_community.verify_offer_creation,
                          Price(1, 'DUM1'), 'DUM1', Quantity(0.1, 'DUM2'), 'DUM2')

    @blocking_call_on_reactor_thread
    def test_check_message(self):
        """
        Test the general check of the validity of a message in the market community
        """
        self.market_community.update_ip(TraderId(self.market_community.mid), ('2.2.2.2', 2))
        proposed_trade_msg = self.get_proposed_trade_msg()
        self.market_community.timeline.check = lambda _: (True, None)
        [self.assertIsInstance(msg, Message.Implementation)
         for msg in self.market_community.check_message([proposed_trade_msg])]

        self.market_community.timeline.check = lambda _: (False, None)
        [self.assertIsInstance(msg, DelayMessageByProof)
         for msg in self.market_community.check_message([proposed_trade_msg])]

    @blocking_call_on_reactor_thread
    def test_check_trade_message(self):
        """
        Test the general check of the validity of a trade message in the market community
        """
        self.proposed_trade.recipient_order_id._trader_id = TraderId("abcdef")
        self.market_community.update_ip(TraderId(self.market_community.mid), ('2.2.2.2', 2))
        self.market_community.update_ip(TraderId("abcdef"), ('2.2.2.2', 2))
        self.market_community.timeline.check = lambda _: (False, None)
        [self.assertIsInstance(msg, DelayMessageByProof) for msg in
         self.market_community.check_trade_message([self.get_proposed_trade_msg()])]

        self.market_community.timeline.check = lambda _: (True, None)
        [self.assertIsInstance(msg, DropMessage) for msg in
         self.market_community.check_trade_message([self.get_proposed_trade_msg()])]

        self.proposed_trade.recipient_order_id._trader_id = TraderId(self.market_community.mid)
        self.market_community.timeline.check = lambda _: (True, None)
        [self.assertIsInstance(msg, DropMessage) for msg in
         self.market_community.check_trade_message([self.get_proposed_trade_msg()])]

        self.market_community.order_manager.order_repository.add(self.order)
        self.market_community.timeline.check = lambda _: (True, None)
        [self.assertIsInstance(msg, Message.Implementation) for msg in
         self.market_community.check_trade_message([self.get_proposed_trade_msg()])]

    @blocking_call_on_reactor_thread
    def test_check_transaction_message(self):
        """
        Test the general check of the validity of a trade message in the market community
        """
        self.market_community.update_ip(TraderId(self.market_community.mid), ('2.2.2.2', 2))
        self.market_community.timeline.check = lambda _: (False, None)
        [self.assertIsInstance(msg, DelayMessageByProof) for msg in
         self.market_community.check_transaction_message([self.get_start_transaction_msg()])]

        self.market_community.timeline.check = lambda _: (True, None)
        [self.assertIsInstance(msg, DropMessage) for msg in
         self.market_community.check_trade_message([self.get_start_transaction_msg()])]

    @blocking_call_on_reactor_thread
    def test_send_proposed_trade(self):
        """
        Test sending a proposed trade
        """
        self.market_community.update_ip(TraderId(self.market_community.mid), ('127.0.0.1', 1234))
        self.assertEqual(self.market_community.send_proposed_trade(self.proposed_trade, 'a'), True)

    @blocking_call_on_reactor_thread
    def test_send_counter_trade(self):
        """
        Test sending a counter trade
        """
        self.market_community.update_ip(TraderId('b'), ('127.0.0.1', 1234))
        counter_trade = CounterTrade(MessageId(TraderId('a'), MessageNumber('2')), self.order.order_id,
                                     OrderId(TraderId('b'), OrderNumber(3)), 1235, Price(3, 'MC'), Quantity(4, 'BTC'),
                                     Timestamp.now())
        self.market_community.send_counter_trade(counter_trade)

    @blocking_call_on_reactor_thread
    def test_start_transaction(self):
        """
        Test the start transaction method
        """
        self.market_community.order_manager.order_repository.add(self.order)
        self.market_community.update_ip(TraderId('0'), ("127.0.0.1", 1234))
        self.market_community.start_transaction(self.proposed_trade, 'a')
        self.assertEqual(len(self.market_community.transaction_manager.find_all()), 1)

    @blocking_call_on_reactor_thread
    def test_on_introduction_request(self):
        """
        Test that when we receive an intro request with a orders bloom filter, we send an order sync back
        """
        def send_info(_):
            send_info.called = True

        send_info.called = False

        candidate = WalkCandidate(("127.0.0.1", 1234), False, ("127.0.0.1", 1234), ("127.0.0.1", 1234), u"public")
        candidate.associate(self.market_community.my_member)
        payload = self.market_community.create_introduction_request(candidate, True).payload

        self.market_community.send_info = send_info

        message = MockObject()
        message.payload = payload
        message.candidate = candidate
        self.market_community.on_introduction_request([message])
        self.assertTrue(send_info.called)

    @blocking_call_on_reactor_thread
    def test_lookup_ip(self):
        # Test for lookup ip
        self.market_community.update_ip(TraderId('0'), ("1.1.1.1", 0))
        self.assertEquals(("1.1.1.1", 0), self.market_community.lookup_ip(TraderId('0')))

    @blocking_call_on_reactor_thread
    def test_get_wallet_address(self):
        """
        Test the retrieval of a wallet address
        """
        self.assertRaises(ValueError, self.market_community.get_wallet_address, 'ABCD')
        self.assertTrue(self.market_community.get_wallet_address('DUM1'))

    @blocking_call_on_reactor_thread
    def test_create_ask(self):
        # Test for create ask
        self.assertRaises(RuntimeError, self.market_community.create_ask, 20, 'DUM2', 100, 'DUM2', 0.0)
        self.assertRaises(RuntimeError, self.market_community.create_ask, 20, 'NOTEXIST', 100, 'DUM2', 0.0)
        self.assertRaises(RuntimeError, self.market_community.create_ask, 20, 'DUM2', 100, 'NOTEXIST', 0.0)
        self.assertTrue(self.market_community.create_ask(20, 'DUM1', 100, 'DUM2', 3600))
        self.assertEquals(1, len(self.market_community.order_book._asks))
        self.assertEquals(0, len(self.market_community.order_book._bids))

    @blocking_call_on_reactor_thread
    def test_create_bid(self):
        # Test for create bid
        self.assertRaises(RuntimeError, self.market_community.create_bid, 20, 'DUM2', 100, 'DUM2', 0.0)
        self.assertRaises(RuntimeError, self.market_community.create_bid, 20, 'NOTEXIST', 100, 'DUM2', 0.0)
        self.assertRaises(RuntimeError, self.market_community.create_bid, 20, 'DUM2', 100, 'NOTEXIST', 0.0)
        self.assertTrue(self.market_community.create_bid(20, 'DUM1', 100, 'DUM2', 3600))
        self.assertEquals(0, len(self.market_community.order_book.asks))
        self.assertEquals(1, len(self.market_community.order_book.bids))

    def get_proposed_trade_msg(self):
        destination, payload = self.proposed_trade.to_network()
        payload += ("127.0.0.1", 1234)
        candidate = Candidate(self.market_community.lookup_ip(destination), False)
        meta = self.market_community.get_meta_message(u"proposed-trade")
        message = meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )
        return message

    @blocking_call_on_reactor_thread
    def test_on_proposed_trade_accept(self):
        """
        Test whether we accept a trade when we receive a correct proposed trade message
        """
        def mocked_start_transaction(*_):
            mocked_start_transaction.called = True

        mocked_start_transaction.called = False

        self.market_community.update_ip(TraderId(self.market_community.mid), ('2.2.2.2', 2))
        self.market_community.start_transaction = mocked_start_transaction
        self.market_community.order_manager.order_repository.add(self.order)

        self.market_community.on_proposed_trade([self.get_proposed_trade_msg()])
        self.assertTrue(mocked_start_transaction.called)

    @blocking_call_on_reactor_thread
    def test_on_proposed_trade_decline(self):
        """
        Test whether we decline a trade when we receive an invalid proposed trade message
        """
        def mocked_send_decline_trade(*_):
            mocked_send_decline_trade.called = True

        mocked_send_decline_trade.called = False

        self.market_community.update_ip(TraderId(self.market_community.mid), ('2.2.2.2', 2))
        self.market_community.send_declined_trade = mocked_send_decline_trade
        self.market_community.order_manager.order_repository.add(self.order)

        self.proposed_trade._price = Price(900, 'DUM1')
        self.market_community.on_proposed_trade([self.get_proposed_trade_msg()])
        self.assertTrue(mocked_send_decline_trade.called)

    @blocking_call_on_reactor_thread
    def test_on_proposed_trade_counter(self):
        """
        Test whether we send a counter trade when we receive a proposed trade message
        """
        def mocked_send_counter_trade(*_):
            mocked_send_counter_trade.called = True

        mocked_send_counter_trade.called = False

        self.market_community.update_ip(TraderId(self.market_community.mid), ('2.2.2.2', 2))
        self.market_community.send_counter_trade = mocked_send_counter_trade
        self.market_community.order_manager.order_repository.add(self.order)

        self.proposed_trade._quantity = Quantity(100000, 'DUM2')
        self.market_community.on_proposed_trade([self.get_proposed_trade_msg()])
        self.assertTrue(mocked_send_counter_trade.called)

    @blocking_call_on_reactor_thread
    def test_compute_reputation(self):
        """
        Test the compute_reputation method
        """
        self.market_community.persistence = MockObject()
        self.market_community.persistence.get_all_blocks = lambda: []
        self.market_community.persistence.close = lambda: None
        self.market_community.compute_reputation()
        self.assertFalse(self.market_community.reputation_dict)

    @blocking_call_on_reactor_thread
    def test_abort_transaction(self):
        """
        Test aborting a transaction
        """
        self.order.reserve_quantity_for_tick(OrderId(TraderId('0'), OrderNumber(23)), Quantity(30, 'DUM2'))
        self.market_community.order_manager.order_repository.add(self.order)
        self.market_community.update_ip(TraderId('0'), ("127.0.0.1", 1234))
        self.market_community.start_transaction(self.proposed_trade, 'a')
        transaction = self.market_community.transaction_manager.find_all()[0]
        self.assertTrue(transaction)
        self.assertEqual(self.order.reserved_quantity, Quantity(30, 'DUM2'))
        self.market_community.abort_transaction(transaction)

        order = self.market_community.order_manager.order_repository.find_by_id(transaction.order_id)
        self.assertEqual(order.reserved_quantity, Quantity(0, 'DUM2'))
