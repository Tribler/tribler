import logging
from abc import ABCMeta, abstractmethod
from time import time

from Tribler.community.market.core.order import Order
from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tickentry import TickEntry
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade


class MatchingStrategy(object):
    """Matching strategy base class"""
    __metaclass__ = ABCMeta

    def __init__(self, order_book):
        """
        :param order_book: The order book to search in
        :type order_book: OrderBook
        """
        super(MatchingStrategy, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        assert isinstance(order_book, OrderBook), type(order_book)

        self.order_book = order_book

    @abstractmethod
    def match_order(self, order):
        """
        :param order: The order to match against
        :type order: Order
        :return: The proposed trades
        :rtype: [ProposedTrade]
        """
        return


class PriceTimeStrategy(MatchingStrategy):
    """Strategy that uses the price time method for picking ticks"""

    def match_order(self, order):
        """
        :param order: The order to match against
        :type order: Order
        :return: The proposed trades
        :rtype: [ProposedTrade]
        """
        assert isinstance(order, Order), type(order)

        if order.is_ask():
            quantity_to_trade, proposed_trades = self._match_ask(order)
        else:
            quantity_to_trade, proposed_trades = self._match_bid(order)

        if quantity_to_trade > Quantity(0, quantity_to_trade.wallet_id):
            self._logger.debug("Quantity not matched: %i", int(quantity_to_trade))

        return proposed_trades

    def _match_ask(self, order):
        proposed_trades = []
        quantity_to_trade = order.available_quantity

        if order.price <= self.order_book.get_bid_price(order.price.wallet_id, order.total_quantity.wallet_id) \
                and quantity_to_trade > Quantity(0, quantity_to_trade.wallet_id):
            # Scan the price levels in the order book
            quantity_to_trade, proposed_trades = self._search_for_quantity_in_order_book(
                self.order_book.get_bid_price(order.price.wallet_id, order.total_quantity.wallet_id),
                self.order_book.get_bid_price_level(order.price.wallet_id, order.total_quantity.wallet_id),
                quantity_to_trade,
                order)
        return quantity_to_trade, proposed_trades

    def _match_bid(self, order):
        proposed_trades = []
        quantity_to_trade = order.available_quantity

        if order.price >= self.order_book.get_ask_price(order.price.wallet_id, order.total_quantity.wallet_id) \
                and quantity_to_trade > Quantity(0, quantity_to_trade.wallet_id):
            # Scan the price levels in the order book
            quantity_to_trade, proposed_trades = self._search_for_quantity_in_order_book(
                self.order_book.get_ask_price(order.price.wallet_id, order.total_quantity.wallet_id),
                self.order_book.get_ask_price_level(order.price.wallet_id, order.total_quantity.wallet_id),
                quantity_to_trade,
                order)
        return quantity_to_trade, proposed_trades

    def _search_for_quantity_in_order_book(self, price, price_level, quantity_to_trade, order):
        """
        Search through the price levels in the order book

        :param price: The price of the price level
        :param price_level: The price level to search in
        :param quantity_to_trade: The quantity still to be matched
        :param order: The order to match for
        :type price: Price
        :type price_level: PriceLevel
        :type quantity_to_trade: Quantity
        :type order: Order
        :return: The quantity to trade and the proposed trades
        :rtype: Quantity, [ProposedTrade]
        """
        if price_level is None:  # Last price level
            return quantity_to_trade, []

        assert isinstance(price, Price), type(price)
        assert isinstance(price_level, PriceLevel), type(price_level)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(order, Order), type(order)

        self._logger.debug("Searching in price level: %f", float(price))

        if quantity_to_trade <= price_level.depth:  # All the quantity can be matched in this price level
            quantity_to_trade, proposed_trades = self._search_for_quantity_in_price_level(price_level.first_tick,
                                                                                          quantity_to_trade,
                                                                                          order)
        else:  # Not all the quantity can be matched in this price level
            quantity_to_trade, proposed_trades = self._search_for_quantity_in_order_book_partial(price,
                                                                                                 price_level,
                                                                                                 quantity_to_trade,
                                                                                                 order)
        return quantity_to_trade, proposed_trades

    def _search_for_quantity_in_order_book_partial(self, price, price_level, quantity_to_trade, order):
        # Not all the quantity can be matched in this price level
        quantity_to_trade, proposed_trades = self._search_for_quantity_in_price_level(price_level.first_tick,
                                                                                      quantity_to_trade,
                                                                                      order)
        if order.is_ask():
            return self._search_for_quantity_in_order_book_partial_ask(price, quantity_to_trade,
                                                                       proposed_trades, order)
        else:
            return self._search_for_quantity_in_order_book_partial_bid(price, quantity_to_trade,
                                                                       proposed_trades, order)

    def _search_for_quantity_in_order_book_partial_ask(self, price, quantity_to_trade, proposed_trades,
                                                       order):
        # Select the next price level
        try:
            # Search the next price level
            next_price, next_price_level = self.order_book.bids.\
                get_price_level_list(price.wallet_id, quantity_to_trade.wallet_id).prev_item(price)
        except IndexError:
            return quantity_to_trade, proposed_trades

        if order.price > next_price:  # Price is too low
            return quantity_to_trade, proposed_trades

        quantity_to_trade, trades = self._search_for_quantity_in_order_book(next_price,
                                                                            next_price_level,
                                                                            quantity_to_trade,
                                                                            order)
        proposed_trades = proposed_trades + trades
        return quantity_to_trade, proposed_trades

    def _search_for_quantity_in_order_book_partial_bid(self, price, quantity_to_trade, proposed_trades,
                                                       order):
        # Select the next price level
        try:
            # Search the next price level
            next_price, next_price_level = self.order_book.asks.\
                get_price_level_list(price.wallet_id, quantity_to_trade.wallet_id).succ_item(price)
        except IndexError:
            return quantity_to_trade, proposed_trades

        if order.price < next_price:  # Price is too high
            return quantity_to_trade, proposed_trades

        quantity_to_trade, trades = self._search_for_quantity_in_order_book(next_price,
                                                                            next_price_level,
                                                                            quantity_to_trade,
                                                                            order)
        proposed_trades = proposed_trades + trades
        return quantity_to_trade, proposed_trades

    def _search_for_quantity_in_price_level(self, tick_entry, quantity_to_trade, order):
        """
        Search through the tick entries in the price levels

        :param tick_entry: The tick entry to match against
        :param quantity_to_trade: The quantity still to be matched
        :param order: The order to match for
        :type tick_entry: TickEntry
        :type quantity_to_trade: Quantity
        :type order: Order
        :return: The quantity to trade and the proposed trades
        :rtype: Quantity, [ProposedTrade]
        """
        if tick_entry is None:  # Last tick
            return quantity_to_trade, []

        # Check if order and tick entry have the same trader id / origin
        if order.order_id.trader_id == tick_entry.order_id.trader_id:
            return quantity_to_trade, []

        assert isinstance(tick_entry, TickEntry), type(tick_entry)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(order, Order), type(order)

        if tick_entry.order_id in order.reserved_ticks:  # Tick is already reserved for this order
            return self._search_for_quantity_in_price_level(tick_entry.next_tick, quantity_to_trade, order)

        if quantity_to_trade <= tick_entry.quantity:  # All the quantity can be matched in this tick
            quantity_to_trade, proposed_trades = self._search_for_quantity_in_price_level_total(tick_entry,
                                                                                                quantity_to_trade,
                                                                                                order)
        else:  # Not all the quantity can be matched in this tick
            quantity_to_trade, proposed_trades = self._search_for_quantity_in_price_level_partial(tick_entry,
                                                                                                  quantity_to_trade,
                                                                                                  order)

        return quantity_to_trade, proposed_trades

    def _search_for_quantity_in_price_level_total(self, tick_entry, quantity_to_trade, order):
        trading_quantity = quantity_to_trade
        quantity_to_trade = Quantity(0, quantity_to_trade.wallet_id)

        self._logger.debug("Match with the id (%s) was found for order (%s). Price: %i, Quantity: %i)",
                           str(tick_entry.order_id), str(order.order_id),
                           float(tick_entry.price), int(trading_quantity))
        order.reserve_quantity_for_tick(tick_entry.tick.order_id, trading_quantity)

        proposed_trades = [Trade.propose(
            self.order_book.message_repository.next_identity(),
            order.order_id,
            tick_entry.order_id,
            tick_entry.price,
            trading_quantity,
            Timestamp.now()
        )]

        return quantity_to_trade, proposed_trades

    def _search_for_quantity_in_price_level_partial(self, tick_entry, quantity_to_trade, order):
        quantity_to_trade -= tick_entry.quantity

        self._logger.debug("Match with the id (%s) was found for order (%s) ", str(tick_entry.order_id),
                           str(order.order_id))
        order.reserve_quantity_for_tick(tick_entry.tick.order_id, tick_entry.quantity)

        proposed_trades = [Trade.propose(
            self.order_book.message_repository.next_identity(),
            order.order_id,
            tick_entry.order_id,
            tick_entry.price,
            tick_entry.quantity,
            Timestamp.now()
        )]

        # Search the next tick
        quantity_to_trade, trades = self._search_for_quantity_in_price_level(tick_entry.next_tick,
                                                                             quantity_to_trade,
                                                                             order)

        proposed_trades = proposed_trades + trades
        return quantity_to_trade, proposed_trades


class MatchingEngine(object):
    """Matches ticks and orders to the order book"""

    def __init__(self, matching_strategy):
        """
        :param matching_strategy: The strategy to use
        :type matching_strategy: MatchingStrategy
        """
        super(MatchingEngine, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        assert isinstance(matching_strategy, MatchingStrategy), type(matching_strategy)
        self.matching_strategy = matching_strategy

    def match_order(self, order):
        """
        :param order: The order to match against
        :type order: Order
        :return: The proposed trades
        :rtype: [ProposedTrade]
        """
        assert isinstance(order, Order), type(order)
        now = time()
        proposed_trades = self.matching_strategy.match_order(order)
        diff = time() - now
        self._logger.debug("Matching engine completed in %.2f seconds", diff)
        return proposed_trades
