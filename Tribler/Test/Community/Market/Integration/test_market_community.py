from tempfile import mkdtemp

from shutil import rmtree
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred
from twisted.internet.task import deferLater
from twisted.internet import reactor

from Tribler.Test.Core.base_test import MockObject
from Tribler.community.market.community import OrderId
from Tribler.community.market.conversion import OrderNumber
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade
from Tribler.dispersy.tests.dispersytestclass import DispersyTestFunc
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.community.market.community import MarketCommunity, ProposedTradeRequestCache
from Tribler.dispersy.tests.debugcommunity.node import DebugNode
from Tribler.community.market.wallet.dummy_wallet import DummyWallet1, DummyWallet2


class TestMarketCommunity(DispersyTestFunc):
    """
    This class contains various Dispersy live tests for the market community.
    These tests are able to control each message and parse them at will.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield DispersyTestFunc.setUp(self)

        self.temp_dir = mkdtemp(suffix="_iom_tests")

        self.node_a, self.node_b = yield self.create_nodes(2)

        dummy1_a = DummyWallet1()
        dummy1_b = DummyWallet1()
        dummy2_a = DummyWallet2()
        dummy2_b = DummyWallet2()

        self.node_a.community.wallets = {dummy1_a.get_identifier(): dummy1_a, dummy2_a.get_identifier(): dummy2_a}
        self.node_b.community.wallets = {dummy1_b.get_identifier(): dummy1_b, dummy2_b.get_identifier(): dummy2_b}

    def tearDown(self):
        DispersyTestFunc.tearDown(self)
        rmtree(unicode(self.temp_dir), ignore_errors=True)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def create_nodes(self, *args, **kwargs):
        nodes = yield super(TestMarketCommunity, self).create_nodes(*args, community_class=MarketCommunity,
                                                                    memory_database=False, **kwargs)
        for outer in nodes:
            for inner in nodes:
                if outer != inner:
                    outer.send_identity(inner)

        returnValue(nodes)

    @inlineCallbacks
    def introduce_nodes(self, node_a, node_b):
        node_b.community.add_discovered_candidate(node_a.my_candidate)
        node_b.take_step()

        yield self.parse_assert_packets(node_a)  # Introduction request
        yield self.parse_assert_packets(node_b)  # Introduction response
        yield deferLater(reactor, 0.05, lambda: None)

    @inlineCallbacks
    def create_send_ask(self, ask_node, bid_node):
        order = ask_node.community.create_ask(10, 'DUM1', 10, 'DUM2', 3600)
        yield self.parse_assert_packets(bid_node)
        self.assertEqual(len(bid_node.community.order_book.asks), 1)
        returnValue(order)

    def _create_node(self, dispersy, community_class, c_master_member):
        return DebugNode(self, dispersy, community_class, c_master_member, curve=u"curve25519")

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def parse_assert_packets(self, node):
        yield deferLater(reactor, 0.05, lambda: None)
        packets = node.process_packets()
        self.assertIsNotNone(packets)
        yield deferLater(reactor, 0.05, lambda: None)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_accept_trade(self):
        """
        Test whether a trade is made between two nodes
        """
        deferred = Deferred()

        def mocked_start_transaction(*_):
            deferred.callback(None)

        self.node_b.community.start_transaction = mocked_start_transaction
        yield self.introduce_nodes(self.node_a, self.node_b)
        yield self.create_send_ask(self.node_a, self.node_b)

        # Send a proposed trade message
        self.node_b.community.create_bid(10, 'DUM1', 10, 'DUM2', 3600)
        yield self.parse_assert_packets(self.node_a)  # Parse the bid message
        yield self.parse_assert_packets(self.node_b)
        yield deferred

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_counter_trade(self):
        """
        Test whether a counter trade is made between two nodes
        """
        deferred = Deferred()

        def mocked_start_transaction(*_):
            deferred.callback(None)

        self.node_a.community.matching_enabled = False
        self.node_b.community.matching_enabled = False

        self.node_a.community.start_transaction = mocked_start_transaction
        yield self.introduce_nodes(self.node_a, self.node_b)
        yield self.create_send_ask(self.node_a, self.node_b)

        # Send a proposed trade message
        self.node_b.community.create_bid(10, 'DUM1', 10, 'DUM2', 3600)
        yield self.parse_assert_packets(self.node_a)  # Parse the bid message
        yield self.parse_assert_packets(self.node_b)

        order_a = self.node_a.community.order_manager.order_repository.find_all()[0]
        order_b = self.node_b.community.order_manager.order_repository.find_all()[0]
        order_b._traded_quantity = Quantity(5, 'DUM2')
        self.node_b.community.order_manager.order_repository.update(order_b)
        order_a.reserve_quantity_for_tick(order_b.order_id, order_a.total_quantity)
        self.node_a.community.order_manager.order_repository.update(order_a)
        proposed_trade = Trade.propose(self.node_b.community.order_book.message_repository.next_identity(),
                                       order_a.order_id, order_b.order_id, Price(10, 'DUM1'),
                                       order_a.total_quantity, Timestamp.now())
        self.node_a.community.send_proposed_trade(proposed_trade)

        yield self.parse_assert_packets(self.node_b)
        yield self.parse_assert_packets(self.node_a)

        yield deferred

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_decline_trade(self):
        """
        Test whether a decline trade is sent between nodes if the price of a proposed trade is not right
        """
        yield self.introduce_nodes(self.node_a, self.node_b)
        yield self.create_send_ask(self.node_a, self.node_b)

        self.node_b.community.create_bid(9, 'DUM1', 10, 'DUM2', 3600)
        yield self.parse_assert_packets(self.node_a)  # Parse the bid message

        order_a = self.node_a.community.order_manager.order_repository.find_all()[0]
        order_b = self.node_b.community.order_manager.order_repository.find_all()[0]
        order_b.reserve_quantity_for_tick(order_a.order_id, order_b.total_quantity)
        self.node_b.community.order_manager.order_repository.update(order_b)
        proposed_trade = Trade.propose(self.node_b.community.order_book.message_repository.next_identity(),
                                       order_b.order_id, order_a.order_id, Price(9, 'DUM1'),
                                       order_b.total_quantity, Timestamp.now())
        self.node_b.community.send_proposed_trade(proposed_trade)
        deferred = Deferred()

        def mocked_remove(_):
            deferred.callback(None)

        self.node_b.community.order_book.remove_tick = mocked_remove

        yield self.parse_assert_packets(self.node_a)
        yield self.parse_assert_packets(self.node_b)
        yield deferred

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_cancel_order(self):
        """
        Test whether a cancel-order message is sent between nodes if we cancel an order
        """
        yield self.introduce_nodes(self.node_a, self.node_b)
        order = yield self.create_send_ask(self.node_a, self.node_b)

        self.node_a.community.cancel_order(order.order_id)
        yield self.parse_assert_packets(self.node_b)
        self.assertEqual(len(self.node_b.community.order_book.asks), 0)
