from Tribler.Core.Modules.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from Tribler.Core.Modules.wallet.tc_wallet import TrustchainWallet
from Tribler.community.market.community import MarketCommunity, PingRequestCache
from Tribler.pyipv8.ipv8.test.base import TestBase
from Tribler.pyipv8.ipv8.test.mocking.ipv8 import MockIPv8
from Tribler.pyipv8.ipv8.test.util import twisted_wrapper
from twisted.internet.defer import fail


class TestMarketCommunityBase(TestBase):
    __testing__ = False
    NUM_NODES = 2

    def setUp(self):
        super(TestMarketCommunityBase, self).setUp()
        self.initialize(MarketCommunity, self.NUM_NODES)
        for node in self.nodes:
            node.overlay._use_main_thread = False

    def create_node(self):
        dum1_wallet = DummyWallet1()
        dum2_wallet = DummyWallet2()
        dum1_wallet.MONITOR_DELAY = 0
        dum2_wallet.MONITOR_DELAY = 0

        wallets = {'DUM1': dum1_wallet, 'DUM2': dum2_wallet}

        mock_ipv8 = MockIPv8(u"curve25519", MarketCommunity, create_trustchain=True,
                             is_matchmaker=True, wallets=wallets, use_database=False, working_directory=u":memory:")
        tc_wallet = TrustchainWallet(mock_ipv8.trustchain)
        mock_ipv8.overlay.wallets['MB'] = tc_wallet

        return mock_ipv8


class TestMarketCommunity(TestMarketCommunityBase):
    __testing__ = True
    NUM_NODES = 3

    def setUp(self):
        super(TestMarketCommunity, self).setUp()

        self.nodes[0].overlay.disable_matchmaker()
        self.nodes[1].overlay.disable_matchmaker()

    @twisted_wrapper
    def test_info_message(self):
        """
        Test sending info messages to other traders
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.send_info(self.nodes[1].my_peer)

        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].overlay.matchmakers)
        self.assertTrue(self.nodes[1].overlay.matchmakers)

    @twisted_wrapper(2)
    def test_create_ask(self):
        """
        Test creating an ask and sending it to others
        """
        yield self.introduce_nodes()

        yield self.nodes[0].overlay.create_ask(1, 'DUM1', 2, 'DUM2', 3600)

        yield self.sleep(0.5)

        orders = self.nodes[0].overlay.order_manager.order_repository.find_all()
        self.assertTrue(orders)
        self.assertTrue(orders[0].verified)
        self.assertTrue(orders[0].is_ask())
        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)

    @twisted_wrapper(2)
    def test_create_bid(self):
        """
        Test creating a bid and sending it to others
        """
        yield self.introduce_nodes()

        yield self.nodes[0].overlay.create_bid(1, 'DUM1', 2, 'DUM2', 3600)

        yield self.sleep(0.5)

        orders = self.nodes[0].overlay.order_manager.order_repository.find_all()
        self.assertTrue(orders)
        self.assertTrue(orders[0].verified)
        self.assertFalse(orders[0].is_ask())
        self.assertEqual(len(self.nodes[2].overlay.order_book.bids), 1)

    @twisted_wrapper(2)
    def test_decline_trade(self):
        """
        Test declining a trade
        """
        self.nodes[0].overlay.disable_matchmaker()
        yield self.introduce_nodes()

        order = yield self.nodes[0].overlay.create_ask(1, 'DUM1', 1, 'DUM2', 3600)
        order._traded_quantity._amount = 1  # So it looks like this order has already been fulfilled

        yield self.sleep(0.5)

        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)
        self.nodes[1].overlay.create_bid(1, 'DUM1', 1, 'DUM2', 3600)

        yield self.sleep(0.5)

        # The ask should be removed since this node thinks the order is already completed
        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 0)

    @twisted_wrapper(2)
    def test_counter_trade(self):
        """
        Test making a counter trade
        """
        self.nodes[0].overlay.disable_matchmaker()
        yield self.introduce_nodes()

        order = yield self.nodes[0].overlay.create_ask(2, 'DUM1', 2, 'DUM2', 3600)
        order._traded_quantity._amount = 1  # Partially fulfill this order

        yield self.sleep(0.5)  # Give it some time to complete the trade

        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)
        self.nodes[1].overlay.create_bid(2, 'DUM1', 2, 'DUM2', 3600)

        yield self.sleep(0.5)

        self.assertTrue(self.nodes[0].overlay.transaction_manager.find_all())
        self.assertTrue(self.nodes[1].overlay.transaction_manager.find_all())

    @twisted_wrapper(2)
    def test_e2e_trade(self):
        """
        Test trading dummy tokens against bandwidth tokens between two persons, with a matchmaker
        """
        yield self.introduce_nodes()

        yield self.nodes[0].overlay.create_ask(1, 'DUM1', 100, 'MB', 3600)
        yield self.nodes[1].overlay.create_bid(1, 'DUM1', 100, 'MB', 3600)

        yield self.sleep(0.5)  # Give it some time to complete the trade

        # Compute reputation
        self.nodes[0].overlay.compute_reputation()

        # Verify that the trade has been made
        self.assertTrue(self.nodes[0].overlay.transaction_manager.find_all())
        self.assertTrue(self.nodes[1].overlay.transaction_manager.find_all())

        balance1 = yield self.nodes[0].overlay.wallets['DUM1'].get_balance()
        balance2 = yield self.nodes[0].overlay.wallets['MB'].get_balance()
        self.assertEqual(balance1['available'], 1100)
        self.assertEqual(balance2['available'], -100)

        balance1 = yield self.nodes[1].overlay.wallets['DUM1'].get_balance()
        balance2 = yield self.nodes[1].overlay.wallets['MB'].get_balance()
        self.assertEqual(balance1['available'], 900)
        self.assertEqual(balance2['available'], 100)

    @twisted_wrapper
    def test_cancel(self):
        """
        Test cancelling an order
        """
        yield self.introduce_nodes()

        ask_order = yield self.nodes[0].overlay.create_ask(1, 'DUM1', 1, 'DUM2', 3600)

        self.nodes[0].overlay.cancel_order(ask_order.order_id)

        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].overlay.order_manager.order_repository.find_by_id(ask_order.order_id).cancelled)

    @twisted_wrapper(2)
    def test_failing_payment(self):
        """
        Test trading between two persons when a payment fails
        """
        yield self.introduce_nodes()

        for node_nr in [0, 1]:
            self.nodes[node_nr].overlay.wallets['DUM1'].transfer = lambda *_: fail(RuntimeError("oops"))
            self.nodes[node_nr].overlay.wallets['DUM2'].transfer = lambda *_: fail(RuntimeError("oops"))

        yield self.nodes[0].overlay.create_ask(1, 'DUM1', 1, 'DUM2', 3600)
        yield self.nodes[1].overlay.create_bid(1, 'DUM1', 1, 'DUM2', 3600)

        yield self.sleep(0.5)

        self.assertEqual(self.nodes[0].overlay.transaction_manager.find_all()[0].status, "error")
        self.assertEqual(self.nodes[1].overlay.transaction_manager.find_all()[0].status, "error")

    @twisted_wrapper(3)
    def test_proposed_trade_timeout(self):
        """
        Test whether we unreserve the quantity if a proposed trade timeouts
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.decode_map[chr(10)] = lambda *_: None

        ask_order = yield self.nodes[0].overlay.create_ask(1, 'DUM1', 1, 'DUM2', 3600)
        bid_order = yield self.nodes[1].overlay.create_bid(1, 'DUM1', 1, 'DUM2', 3600)

        yield self.deliver_messages(timeout=.5)

        outstanding = self.nodes[1].overlay.get_outstanding_proposals(bid_order.order_id, ask_order.order_id)
        self.assertTrue(outstanding)
        outstanding[0][1].on_timeout()

        yield self.deliver_messages(timeout=.5)

        ask_tick_entry = self.nodes[2].overlay.order_book.get_tick(ask_order.order_id)
        bid_tick_entry = self.nodes[2].overlay.order_book.get_tick(bid_order.order_id)
        self.assertEqual(bid_tick_entry.reserved_for_matching.amount, 0)
        self.assertEqual(ask_tick_entry.reserved_for_matching.amount, 0)

    @twisted_wrapper(4)
    def test_orderbook_sync(self):
        """
        Test whether orderbooks are synchronized with a new node
        """
        yield self.introduce_nodes()

        ask_order = yield self.nodes[0].overlay.create_ask(100, 'DUM1', 2, 'DUM2', 3600)
        bid_order = yield self.nodes[1].overlay.create_bid(1, 'DUM1', 2, 'DUM2', 3600)

        yield self.deliver_messages(timeout=.5)

        # Add a node that crawls the matchmaker
        self.add_node_to_experiment(self.create_node())
        self.nodes[3].discovery.take_step()
        yield self.deliver_messages(timeout=.5)
        yield self.sleep(0.2)  # For processing the tick blocks

        self.assertTrue(self.nodes[3].overlay.order_book.get_tick(ask_order.order_id))
        self.assertTrue(self.nodes[3].overlay.order_book.get_tick(bid_order.order_id))

        # Add another node that crawls our newest node
        self.add_node_to_experiment(self.create_node())
        self.nodes[4].overlay.send_orderbook_sync(self.nodes[3].overlay.my_peer)
        yield self.deliver_messages(timeout=.5)
        yield self.sleep(0.2)  # For processing the tick blocks

        self.assertTrue(self.nodes[4].overlay.order_book.get_tick(ask_order.order_id))
        self.assertTrue(self.nodes[4].overlay.order_book.get_tick(bid_order.order_id))


class TestMarketCommunityTwoNodes(TestMarketCommunityBase):
    __testing__ = True

    @twisted_wrapper(2)
    def test_e2e_trade(self):
        """
        Test a direct trade between two nodes
        """
        yield self.introduce_nodes()

        yield self.nodes[0].overlay.create_ask(10, 'DUM1', 13, 'DUM2', 3600)
        yield self.nodes[1].overlay.create_bid(10, 'DUM1', 13, 'DUM2', 3600)

        yield self.sleep(0.5)

        # Verify that the trade has been made
        self.assertTrue(self.nodes[0].overlay.transaction_manager.find_all())
        self.assertTrue(self.nodes[1].overlay.transaction_manager.find_all())

        balance1 = yield self.nodes[0].overlay.wallets['DUM1'].get_balance()
        balance2 = yield self.nodes[0].overlay.wallets['DUM2'].get_balance()
        self.assertEqual(balance1['available'], 1130)
        self.assertEqual(balance2['available'], 9987)

        balance1 = yield self.nodes[1].overlay.wallets['DUM1'].get_balance()
        balance2 = yield self.nodes[1].overlay.wallets['DUM2'].get_balance()
        self.assertEqual(balance1['available'], 870)
        self.assertEqual(balance2['available'], 10013)

    @twisted_wrapper(4)
    def test_partial_trade(self):
        """
        Test a partial trade between two nodes
        """
        yield self.introduce_nodes()

        yield self.nodes[0].overlay.create_ask(1, 'DUM1', 2, 'DUM2', 3600)
        bid_order = yield self.nodes[1].overlay.create_bid(1, 'DUM1', 10, 'DUM2', 3600)

        yield self.sleep(0.5)

        # Verify that the trade has been made
        transactions1 = self.nodes[0].overlay.transaction_manager.find_all()
        transactions2 = self.nodes[1].overlay.transaction_manager.find_all()
        self.assertEqual(len(transactions1), 1)
        self.assertEqual(len(transactions2), 1)

        # There should be no reserved quantity for the bid tick
        for node_nr in [0, 1]:
            bid_tick_entry = self.nodes[node_nr].overlay.order_book.get_tick(bid_order.order_id)
            self.assertEqual(bid_tick_entry.reserved_for_matching.amount, 0)

        yield self.nodes[0].overlay.create_ask(1, 'DUM1', 8, 'DUM2', 3600)

        yield self.sleep(1)

        # Verify that the trade has been made
        self.assertEqual(len(self.nodes[0].overlay.transaction_manager.find_all()), 2)
        self.assertEqual(len(self.nodes[1].overlay.transaction_manager.find_all()), 2)

        for node_nr in [0, 1]:
            self.assertEqual(len(self.nodes[node_nr].overlay.order_book.asks), 0)
            self.assertEqual(len(self.nodes[node_nr].overlay.order_book.bids), 0)

    @twisted_wrapper
    def test_churn_matchmaker(self):
        """
        Test whether we finish constructing a tick as soon as the first matchmaker comes online
        """
        deferred = self.nodes[0].overlay.create_ask(1, 'DUM1', 2, 'DUM2', 3600)
        yield self.introduce_nodes()
        yield deferred

    @twisted_wrapper(2)
    def test_offline_matchmaker(self):
        """
        Test whether offline matchmakers are successfully removed
        """
        yield self.introduce_nodes()

        PingRequestCache.TIMEOUT_DELAY = 0.1
        self.nodes[1].overlay.decode_map[chr(20)] = lambda *_: None
        self.assertTrue(self.nodes[0].overlay.matchmakers)
        self.nodes[0].overlay.get_online_matchmaker()
        yield self.sleep(0.2)
        self.assertFalse(self.nodes[0].overlay.matchmakers)

    @twisted_wrapper
    def test_ping_pong(self):
        """
        Test the ping/pong mechanism of the market
        """
        yield self.nodes[0].overlay.ping_peer(self.nodes[1].overlay.my_peer)
