from Tribler.Test.ipv8_base import TestBase
from Tribler.Test.mocking.ipv8 import MockIPv8
from Tribler.Test.util.ipv8_util import twisted_wrapper
from Tribler.community.market.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from Tribler.community.market.community import MarketCommunity
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

        return MockIPv8(u"curve25519", MarketCommunity,
                        is_matchmaker=True, wallets=wallets, use_database=False, working_directory=u":memory:")


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

    @twisted_wrapper
    def test_create_ask(self):
        """
        Test creating an ask and sending it to others
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.create_ask(1, 'DUM1', 2, 'DUM2', 3600)

        yield self.deliver_messages()

        orders = self.nodes[0].overlay.order_manager.order_repository.find_all()
        self.assertTrue(orders)
        self.assertTrue(orders[0].is_ask())
        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)

    @twisted_wrapper
    def test_create_bid(self):
        """
        Test creating a bid and sending it to others
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.create_bid(1, 'DUM1', 2, 'DUM2', 3600)

        yield self.deliver_messages()

        orders = self.nodes[0].overlay.order_manager.order_repository.find_all()
        self.assertTrue(orders)
        self.assertFalse(orders[0].is_ask())
        self.assertEqual(len(self.nodes[2].overlay.order_book.bids), 1)

    @twisted_wrapper
    def test_decline_trade(self):
        """
        Test declining a trade
        """
        self.nodes[0].overlay.disable_matchmaker()
        yield self.introduce_nodes()

        order = self.nodes[0].overlay.create_ask(1, 'DUM1', 1, 'DUM2', 3600)
        order._traded_quantity._quantity = 1  # So it looks like this order has already been fulfilled

        yield self.deliver_messages()

        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)
        self.nodes[1].overlay.create_bid(1, 'DUM1', 1, 'DUM2', 3600)

        yield self.deliver_messages()

        # The ask should be removed since this node thinks the order is already completed
        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 0)

    @twisted_wrapper
    def test_counter_trade(self):
        """
        Test making a counter trade
        """
        self.nodes[0].overlay.disable_matchmaker()
        yield self.introduce_nodes()

        order = self.nodes[0].overlay.create_ask(2, 'DUM1', 2, 'DUM2', 3600)
        order._traded_quantity._quantity = 1  # Partially fulfill this order

        yield self.deliver_messages(timeout=.4)

        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)
        self.nodes[1].overlay.create_bid(2, 'DUM1', 2, 'DUM2', 3600)

        yield self.deliver_messages(timeout=.4)

        self.assertTrue(self.nodes[0].overlay.transaction_manager.find_all())
        self.assertTrue(self.nodes[1].overlay.transaction_manager.find_all())

    @twisted_wrapper
    def test_e2e_trade(self):
        """
        Test trading between two persons, with a matchmaker
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.create_ask(1, 'DUM1', 1, 'DUM2', 3600)
        self.nodes[1].overlay.create_bid(1, 'DUM1', 1, 'DUM2', 3600)

        yield self.deliver_messages(timeout=.5)

        # Compute reputation
        self.nodes[0].overlay.compute_reputation()

        # Verify that the trade has been made
        self.assertTrue(self.nodes[0].overlay.transaction_manager.find_all())
        self.assertTrue(self.nodes[1].overlay.transaction_manager.find_all())

        balance1 = yield self.nodes[0].overlay.wallets['DUM1'].get_balance()
        balance2 = yield self.nodes[0].overlay.wallets['DUM2'].get_balance()
        self.assertEqual(balance1['available'], 1001)
        self.assertEqual(balance2['available'], 999)

        balance1 = yield self.nodes[1].overlay.wallets['DUM1'].get_balance()
        balance2 = yield self.nodes[1].overlay.wallets['DUM2'].get_balance()
        self.assertEqual(balance1['available'], 999)
        self.assertEqual(balance2['available'], 1001)

    @twisted_wrapper
    def test_cancel(self):
        """
        Test cancelling an order
        """
        yield self.introduce_nodes()

        ask_order = self.nodes[0].overlay.create_ask(1, 'DUM1', 1, 'DUM2', 3600)

        yield self.deliver_messages(timeout=.4)

        self.nodes[0].overlay.cancel_order(ask_order.order_id)

        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].overlay.order_manager.order_repository.find_by_id(ask_order.order_id).cancelled)

    @twisted_wrapper
    def test_failing_payment(self):
        """
        Test trading between two persons when a payment fails
        """
        yield self.introduce_nodes()

        for node_nr in [0, 1]:
            self.nodes[node_nr].overlay.wallets['DUM1'].transfer = lambda *_: fail(RuntimeError("oops"))
            self.nodes[node_nr].overlay.wallets['DUM2'].transfer = lambda *_: fail(RuntimeError("oops"))

        self.nodes[0].overlay.create_ask(1, 'DUM1', 1, 'DUM2', 3600)
        self.nodes[1].overlay.create_bid(1, 'DUM1', 1, 'DUM2', 3600)

        yield self.deliver_messages(timeout=.4)

        self.assertEqual(self.nodes[0].overlay.transaction_manager.find_all()[0].status, "error")
        self.assertEqual(self.nodes[1].overlay.transaction_manager.find_all()[0].status, "error")


class TestMarketCommunityTwoNodes(TestMarketCommunityBase):
    __testing__ = True

    @twisted_wrapper
    def test_e2e_trade(self):
        """
        Test a direct trade between two nodes
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.create_ask(1, 'DUM1', 1, 'DUM2', 3600)
        self.nodes[1].overlay.create_bid(1, 'DUM1', 1, 'DUM2', 3600)

        yield self.deliver_messages(timeout=.5)

        # Verify that the trade has been made
        self.assertTrue(self.nodes[0].overlay.transaction_manager.find_all())
        self.assertTrue(self.nodes[1].overlay.transaction_manager.find_all())

        balance1 = yield self.nodes[0].overlay.wallets['DUM1'].get_balance()
        balance2 = yield self.nodes[0].overlay.wallets['DUM2'].get_balance()
        self.assertEqual(balance1['available'], 1001)
        self.assertEqual(balance2['available'], 999)

        balance1 = yield self.nodes[1].overlay.wallets['DUM1'].get_balance()
        balance2 = yield self.nodes[1].overlay.wallets['DUM2'].get_balance()
        self.assertEqual(balance1['available'], 999)
        self.assertEqual(balance2['available'], 1001)
