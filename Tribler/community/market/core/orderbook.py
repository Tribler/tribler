import logging
import time

from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from twisted.internet import reactor
from twisted.internet.defer import fail
from twisted.internet.task import deferLater
from twisted.python.failure import Failure

from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.side import Side
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.database import MarketDB
from Tribler.dispersy.taskmanager import TaskManager


class OrderBook(TaskManager):
    """
    OrderBook is used for searching through all the orders and giving an indication to the user of what other offers
    are out there.
    """

    def __init__(self):
        super(OrderBook, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self._bids = Side()
        self._asks = Side()
        self.completed_orders = []

    def timeout_ask(self, order_id):
        ask = self.get_ask(order_id).tick
        self.remove_tick(order_id)
        return ask

    def timeout_bid(self, order_id):
        bid = self.get_bid(order_id).tick
        self.remove_tick(order_id)
        return bid

    def on_timeout_error(self, _):
        pass

    def on_invalid_tick_insert(self, _):
        self._logger.warning("Invalid tick inserted in order book.")

    def insert_ask(self, ask):
        """
        :type ask: Ask
        """
        assert isinstance(ask, Ask), type(ask)

        if not self._asks.tick_exists(ask.order_id) and ask.order_id not in self.completed_orders and ask.is_valid():
            self._asks.insert_tick(ask)
            timeout_delay = float(ask.timestamp) + float(ask.timeout) - time.time()
            task = deferLater(reactor, timeout_delay, self.timeout_ask, ask.order_id)
            self.register_task("ask_%s_timeout" % ask.order_id, task)
            return task.addErrback(self.on_timeout_error)
        return fail(Failure(RuntimeError("ask invalid"))).addErrback(self.on_invalid_tick_insert)

    def remove_ask(self, order_id):
        """
        :type order_id: OrderId
        """
        assert isinstance(order_id, OrderId), type(order_id)

        if self._asks.tick_exists(order_id):
            self.cancel_pending_task("ask_%s_timeout" % order_id)
            self._asks.remove_tick(order_id)

    def insert_bid(self, bid):
        """
        :type bid: Bid
        """
        assert isinstance(bid, Bid), type(bid)

        if not self._bids.tick_exists(bid.order_id) and bid.order_id not in self.completed_orders and bid.is_valid():
            self._bids.insert_tick(bid)
            timeout_delay = float(bid.timestamp) + float(bid.timeout) - time.time()
            task = deferLater(reactor, timeout_delay, self.timeout_bid, bid.order_id)
            self.register_task("bid_%s_timeout" % bid.order_id, task)
            return task.addErrback(self.on_timeout_error)
        return fail(Failure(RuntimeError("bid invalid"))).addErrback(self.on_invalid_tick_insert)

    def remove_bid(self, order_id):
        """
        :type order_id: OrderId
        """
        assert isinstance(order_id, OrderId), type(order_id)

        if self._bids.tick_exists(order_id):
            self.cancel_pending_task("bid_%s_timeout" % order_id)
            self._bids.remove_tick(order_id)

    def update_ticks(self, ask_order_dict, bid_order_dict, traded_quantity, unreserve=True):
        """
        Update ticks according to a TradeChain block containing the status of the ask/bid orders.

        :type ask_order_dict: dict
        :type bid_order_dict: dict
        :type traded_quantity: Quantity
        :type unreserve: bool
        """
        assert isinstance(ask_order_dict, dict), type(ask_order_dict)
        assert isinstance(bid_order_dict, dict), type(bid_order_dict)
        assert isinstance(traded_quantity, Quantity), type(traded_quantity)
        assert isinstance(unreserve, bool), type(unreserve)

        ask_order_id = OrderId(TraderId(ask_order_dict["trader_id"]), OrderNumber(ask_order_dict["order_number"]))
        bid_order_id = OrderId(TraderId(bid_order_dict["trader_id"]), OrderNumber(bid_order_dict["order_number"]))

        self._logger.debug("Updating ticks in order book: %s and %s (traded quantity: %s)",
                           str(ask_order_id), str(bid_order_id), str(traded_quantity))

        # Update ask tick
        new_ask_quantity = Quantity(ask_order_dict["quantity"] - ask_order_dict["traded_quantity"],
                                    ask_order_dict["quantity_type"])
        if self.tick_exists(ask_order_id) and new_ask_quantity <= self.get_tick(ask_order_id).quantity:
            tick = self.get_tick(ask_order_id)
            tick.quantity = new_ask_quantity
            if unreserve:
                tick.release_for_matching(traded_quantity)
            if tick.quantity <= Quantity(0, ask_order_dict["quantity_type"]):
                self.remove_tick(tick.order_id)
                self.completed_orders.append(tick.order_id)
        elif not self.tick_exists(ask_order_id) and new_ask_quantity > Quantity(0, ask_order_dict["quantity_type"]):
            ask = Ask(ask_order_id, Price(ask_order_dict["price"], ask_order_dict["price_type"]),
                      new_ask_quantity, Timeout(ask_order_dict["timeout"]), Timestamp(ask_order_dict["timestamp"]))
            self.insert_ask(ask)

        # Update bid tick
        new_bid_quantity = Quantity(bid_order_dict["quantity"] - bid_order_dict["traded_quantity"],
                                    bid_order_dict["quantity_type"])
        if self.tick_exists(bid_order_id) and new_bid_quantity <= self.get_tick(bid_order_id).quantity:
            tick = self.get_tick(bid_order_id)
            tick.quantity = new_bid_quantity
            if unreserve:
                tick.release_for_matching(traded_quantity)
            if tick.quantity <= Quantity(0, bid_order_dict["quantity_type"]):
                self.remove_tick(tick.order_id)
                self.completed_orders.append(tick.order_id)
        elif not self.tick_exists(bid_order_id) and new_bid_quantity > Quantity(0, bid_order_dict["quantity_type"]):
            bid = Bid(bid_order_id, Price(bid_order_dict["price"], bid_order_dict["price_type"]),
                      new_bid_quantity, Timeout(bid_order_dict["timeout"]), Timestamp(bid_order_dict["timestamp"]))
            self.insert_bid(bid)

    def tick_exists(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the tick exists, False otherwise
        :rtype: bool
        """
        assert isinstance(order_id, OrderId), type(order_id)

        is_ask = self._asks.tick_exists(order_id)
        is_bid = self._bids.tick_exists(order_id)

        return is_ask or is_bid

    def get_ask(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :rtype: TickEntry
        """
        assert isinstance(order_id, OrderId), type(order_id)

        return self._asks.get_tick(order_id)

    def get_bid(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :rtype: TickEntry
        """
        assert isinstance(order_id, OrderId), type(order_id)

        return self._bids.get_tick(order_id)

    def get_tick(self, order_id):
        """
        Return a tick with the specified order id.
        :param order_id: The order id to search for
        :type order_id: OrderId
        :rtype: TickEntry
        """
        assert isinstance(order_id, OrderId), type(order_id)

        return self._bids.get_tick(order_id) or self._asks.get_tick(order_id)

    def ask_exists(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the ask exists, False otherwise
        :rtype: bool
        """
        assert isinstance(order_id, OrderId), type(order_id)

        return self._asks.tick_exists(order_id)

    def bid_exists(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the bid exists, False otherwise
        :rtype: bool
        """
        assert isinstance(order_id, OrderId), type(order_id)

        return self._bids.tick_exists(order_id)

    def remove_tick(self, order_id):
        """
        :type order_id: OrderId
        """
        assert isinstance(order_id, OrderId), type(order_id)

        self._logger.debug("Removing tick %s from order book", order_id)

        self.remove_ask(order_id)
        self.remove_bid(order_id)

    @property
    def asks(self):
        """
        Return the asks side
        :rtype: Side
        """
        return self._asks

    @property
    def bids(self):
        """
        Return the bids side
        :rtype: Side
        """
        return self._bids

    def get_bid_price(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price an ask needs to have to make a trade
        :rtype: Price
        """
        return self._bids.get_max_price(price_wallet_id, quantity_wallet_id)

    def get_ask_price(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price a bid needs to have to make a trade
        :rtype: Price
        """
        return self._asks.get_min_price(price_wallet_id, quantity_wallet_id)

    def get_bid_ask_spread(self, price_wallet_id, quantity_wallet_id):
        """
        Return the spread between the bid and the ask price
        :rtype: Price
        """
        return self.get_ask_price(price_wallet_id, quantity_wallet_id) - \
               self.get_bid_price(price_wallet_id, quantity_wallet_id)

    def get_mid_price(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price in between the bid and the ask price
        :rtype: Price
        """
        ask_price = int(self.get_ask_price(price_wallet_id, quantity_wallet_id))
        bid_price = int(self.get_bid_price(price_wallet_id, quantity_wallet_id))
        return Price((ask_price + bid_price) / 2, price_wallet_id)

    def bid_side_depth(self, price):
        """
        Return the depth of the price level with the given price on the bid side

        :param price: The price for the price level
        :type price: Price
        :return: The depth at that price level
        :rtype: Quantity
        """
        assert isinstance(price, Price), type(price)
        return self._bids.get_price_level(price).depth

    def ask_side_depth(self, price):
        """
        Return the depth of the price level with the given price on the ask side

        :param price: The price for the price level
        :type price: Price
        :return: The depth at that price level
        :rtype: Quantity
        """
        assert isinstance(price, Price), type(price)
        return self._asks.get_price_level(price).depth

    def get_bid_side_depth_profile(self, price_wallet_id, quantity_wallet_id):
        """
        format: [(<price>, <depth>), (<price>, <depth>), ...]

        :return: The depth profile
        :rtype: list
        """
        profile = []
        for key, value in self._bids.get_price_level_list(price_wallet_id, quantity_wallet_id).items():
            profile.append((key, value.depth))
        return profile

    def get_ask_side_depth_profile(self, price_wallet_id, quantity_wallet_id):
        """
        format: [(<price>, <depth>), (<price>, <depth>), ...]

        :return: The depth profile
        :rtype: list
        """
        profile = []
        for key, value in self._asks.get_price_level_list(price_wallet_id, quantity_wallet_id).items():
            profile.append((key, value.depth))
        return profile

    def bid_relative_price(self, price):
        """
        :param price: The price to be relative to
        :type price: Price
        :return: The relative price
        :rtype: Price
        """
        assert isinstance(price, Price), type(price)
        return self.get_bid_price('BTC', 'MC') - price

    def ask_relative_price(self, price):
        """
        :param price: The price to be relative to
        :type price: Price
        :return: The relative price
        :rtype: Price
        """
        assert isinstance(price, Price), type(price)
        return self.get_ask_price('BTC', 'MC') - price

    def relative_tick_price(self, tick):
        """
        :param tick: The tick with the price to be relative to
        :type tick: Tick
        :return: The relative price
        :rtype: Price
        """
        assert isinstance(tick, Tick), type(tick)

        if tick.is_ask():
            return self.ask_relative_price(tick.price)
        else:
            return self.bid_relative_price(tick.price)

    def get_bid_price_level(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price level that an ask has to match to make a trade
        :rtype: PriceLevel
        """
        return self._bids.get_max_price_list(price_wallet_id, quantity_wallet_id)

    def get_ask_price_level(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price level that a bid has to match to make a trade
        :rtype: PriceLevel
        """
        return self._asks.get_min_price_list(price_wallet_id, quantity_wallet_id)

    def get_order_ids(self):
        """
        Return all IDs of the orders in the orderbook, both asks and bids. The returned list is sorted.

        :rtype: [OrderId]
        """
        return sorted(self.get_bid_ids() + self.get_ask_ids())

    def get_ask_ids(self):
        ids = []

        for price_wallet_id, quantity_wallet_id in self.asks.get_price_level_list_wallets():
            for _, price_level in self.asks.get_price_level_list(price_wallet_id, quantity_wallet_id).items():
                for ask in price_level:
                    ids.append(ask.tick.order_id)

        return sorted(ids)

    def get_bid_ids(self):
        ids = []

        for price_wallet_id, quantity_wallet_id in self.bids.get_price_level_list_wallets():
            for _, price_level in self.bids.get_price_level_list(price_wallet_id, quantity_wallet_id).items():
                for bid in price_level:
                    ids.append(bid.tick.order_id)

        return sorted(ids)

    def __str__(self):
        res_str = ''
        res_str += "------ Bids -------\n"
        for price_wallet_id, quantity_wallet_id in self.bids.get_price_level_list_wallets():
            for _, value in self._bids.get_price_level_list(price_wallet_id, quantity_wallet_id).items(reverse=True):
                res_str += '%s' % value
        res_str += "\n------ Asks -------\n"
        for price_wallet_id, quantity_wallet_id in self.asks.get_price_level_list_wallets():
            for _, value in self._asks.get_price_level_list(price_wallet_id, quantity_wallet_id).items():
                res_str += '%s' % value
        res_str += "\n"
        return res_str

    def cancel_all_pending_tasks(self):
        super(OrderBook, self).cancel_all_pending_tasks()
        for order_id in self.get_order_ids():
            self.get_tick(order_id).cancel_all_pending_tasks()


class DatabaseOrderBook(OrderBook):
    """
    This class adds support for a persistency backend to store ticks.
    For now, it only provides methods to save all ticks to the database or to restore all ticks from the database.
    """
    def __init__(self, database):
        super(DatabaseOrderBook, self).__init__()

        assert isinstance(database, MarketDB)

        self.database = database

    def save_to_database(self):
        """
        Write all ticks to the database
        """
        self.database.delete_all_ticks()
        for order_id in self.get_order_ids():
            tick = self.get_tick(order_id)
            if tick.is_valid():
                self.database.add_tick(tick.tick)

    def restore_from_database(self):
        """
        Restore ticks from the database
        """
        for tick in self.database.get_ticks():
            if not self.tick_exists(tick.order_id) and tick.is_valid():
                self.insert_ask(tick) if tick.is_ask() else self.insert_bid(tick)
