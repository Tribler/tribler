import logging
from abc import ABCMeta, abstractmethod
from time import time

from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tickentry import TickEntry


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
    def match(self, price, quantity, is_ask):
        """
        :param price: The price to match against
        :param quantity: The quantity that should be matched
        :param is_ask: Whether the object we want to match is an ask
        :type price: Price
        :type quantity: Quantity
        :type is_ask: Bool
        :return: A list of tuples containing the ticks and the matched quantity
        :rtype: [(Tick, Quantity)]
        """
        return


class PriceTimeStrategy(MatchingStrategy):
    """Strategy that uses the price time method for picking ticks"""

    def match(self, price, quantity, is_ask):
        """
        :param price: The price to match against
        :param quantity: The quantity that should be matched
        :param is_ask: Whether the object we want to match is an ask
        :type price: Price
        :type quantity: Quantity
        :type is_ask: Bool
        :return: A list of tuples containing the ticks and the matched quantity
        :rtype: [(Tick, Quantity)]
        """
        matched_ticks = self._match_ask(price, quantity, is_ask) if is_ask else self._match_bid(price, quantity, is_ask)

        return matched_ticks

    def _match_ask(self, price, quantity, is_ask):
        matched_ticks = []

        if price <= self.order_book.get_bid_price(price.wallet_id, quantity.wallet_id) \
                and quantity > Quantity(0, quantity.wallet_id):
            # Scan the price levels in the order book
            matched_ticks = self._search_for_quantity_in_order_book(
                self.order_book.get_bid_price(price.wallet_id, quantity.wallet_id),
                self.order_book.get_bid_price_level(price.wallet_id, quantity.wallet_id),
                quantity, price, is_ask)
        return matched_ticks

    def _match_bid(self, price, quantity, is_ask):
        matched_ticks = []

        if price >= self.order_book.get_ask_price(price.wallet_id, quantity.wallet_id) \
                and quantity > Quantity(0, quantity.wallet_id):
            # Scan the price levels in the order book
            matched_ticks = self._search_for_quantity_in_order_book(
                self.order_book.get_ask_price(price.wallet_id, quantity.wallet_id),
                self.order_book.get_ask_price_level(price.wallet_id, quantity.wallet_id),
                quantity, price, is_ask)
        return matched_ticks

    def _search_for_quantity_in_order_book(self, price, price_level, quantity_to_trade, tick_price, is_ask):
        """
        Search through the price levels in the order book

        :param price: The price of the price level
        :param price_level: The price level to search in
        :param quantity_to_trade: The quantity still to be matched
        :param tick_price: The price of the tick being matched
        :param is_ask: Whether our tick being matched is an ask
        :type price: Price
        :type price_level: PriceLevel
        :type quantity_to_trade: Quantity
        :type tick_price: Price
        :type is_ask: bool
        :return: A list of tuples containing the ticks and the matched quantity
        :rtype: [(Tick, Quantity)]
        """
        if price_level is None:  # Last price level
            return []

        assert isinstance(price, Price), type(price)
        assert isinstance(price_level, PriceLevel), type(price_level)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(tick_price, Price), type(tick_price)
        assert isinstance(is_ask, bool), type(is_ask)

        self._logger.debug("Searching in price level: %f", float(price))

        if quantity_to_trade <= price_level.depth:  # All the quantity can be matched in this price level
            return self._search_for_quantity_in_price_level(price_level.first_tick,
                                                            quantity_to_trade,
                                                            tick_price, is_ask)
        else:  # Not all the quantity can be matched in this price level
            return self._search_for_quantity_in_order_book_partial(price, price_level, quantity_to_trade,
                                                                   tick_price, is_ask)

    def _search_for_quantity_in_order_book_partial(self, price, price_level, quantity_to_trade, tick_price, is_ask):
        # Not all the quantity can be matched in this price level
        matching_ticks = self._search_for_quantity_in_price_level(price_level.first_tick, quantity_to_trade, tick_price, is_ask)
        if is_ask:
            return self._search_for_quantity_in_order_book_partial_ask(price, quantity_to_trade,
                                                                       matching_ticks, tick_price, is_ask)
        else:
            return self._search_for_quantity_in_order_book_partial_bid(price, quantity_to_trade,
                                                                       matching_ticks, tick_price, is_ask)

    def _search_for_quantity_in_order_book_partial_ask(self, price, quantity_to_trade, matching_ticks,
                                                       tick_price, is_ask):
        # Select the next price level
        try:
            # Search the next price level
            next_price, next_price_level = self.order_book.bids.\
                get_price_level_list(price.wallet_id, quantity_to_trade.wallet_id).prev_item(price)
        except IndexError:
            return matching_ticks

        if tick_price > next_price:  # Price is too low
            return matching_ticks

        matching_ticks += self._search_for_quantity_in_order_book(next_price, next_price_level, quantity_to_trade,
                                                                  tick_price, is_ask)

        return matching_ticks

    def _search_for_quantity_in_order_book_partial_bid(self, price, quantity_to_trade, matching_ticks,
                                                       tick_price, is_ask):
        # Select the next price level
        try:
            # Search the next price level
            next_price, next_price_level = self.order_book.asks.\
                get_price_level_list(price.wallet_id, quantity_to_trade.wallet_id).succ_item(price)
        except IndexError:
            return matching_ticks

        if tick_price < next_price:  # Price is too high
            return matching_ticks

        matching_ticks += self._search_for_quantity_in_order_book(next_price, next_price_level, quantity_to_trade,
                                                                  tick_price, is_ask)

        return matching_ticks

    def _search_for_quantity_in_price_level(self, tick_entry, quantity_to_trade, tick_price, is_ask):
        """
        Search through the tick entries in the price levels

        :param tick_entry: The tick entry to match against
        :param quantity_to_trade: The quantity still to be matched
        :param tick_price: The price of the tick being matched
        :param is_ask: Whether our tick being matched is an ask
        :type tick_entry: TickEntry
        :type quantity_to_trade: Quantity
        :type tick_price: Price
        :type is_ask: bool
        :return: A list of tuples containing the ticks and the matched quantity
        :rtype: [(Tick, Quantity)]
        """
        if tick_entry is None:  # Last tick
            return []

        # TODO check whether you are not matching with yourself!
        # Check if order and tick entry have the same trader id / origin
        #if order.order_id.trader_id == tick_entry.order_id.trader_id:
        #    return quantity_to_trade, []

        assert isinstance(tick_entry, TickEntry), type(tick_entry)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(tick_price, Price), type(tick_price)
        assert isinstance(is_ask, bool), type(is_ask)

        if quantity_to_trade <= tick_entry.quantity:  # All the quantity can be matched in this tick
            return self._search_for_quantity_in_price_level_total(tick_entry, quantity_to_trade, tick_price, is_ask)
        else:  # Not all the quantity can be matched in this tick
            return self._search_for_quantity_in_price_level_partial(tick_entry, quantity_to_trade, tick_price, is_ask)

    def _search_for_quantity_in_price_level_total(self, tick_entry, quantity_to_trade, tick_price, is_ask):
        trading_quantity = quantity_to_trade

        self._logger.debug("Match with the id (%s) was found: price %i, quantity %i",
                           str(tick_entry.order_id), float(tick_entry.price), int(trading_quantity))

        return [(tick_entry.tick, trading_quantity)]

    def _search_for_quantity_in_price_level_partial(self, tick_entry, quantity_to_trade, tick_price, is_ask):
        quantity_to_trade -= tick_entry.quantity

        self._logger.debug("Match with the id (%s) was found: price %i, quantity %i",
                           str(tick_entry.order_id), float(tick_entry.price), int(tick_entry.quantity))

        matching_ticks = [(tick_entry.tick, tick_entry.quantity)]

        # Search the next tick
        matching_ticks += self._search_for_quantity_in_price_level(tick_entry.next_tick, quantity_to_trade,
                                                                   tick_price, is_ask)
        return matching_ticks


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

    def match(self, price, quantity, is_ask):
        """
        :param price: The price to match against
        :param quantity: The quantity that should be matched
        :param is_ask: Whether the object we want to match is an ask
        :type price: Price
        :type quantity: Quantity
        :type is_ask: Bool
        :return: A list of tuples containing the ticks and the matched quantity
        :rtype: [(Tick, Quantity)]
        """
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(is_ask, bool), type(is_ask)
        now = time()
        matched_ticks = self.matching_strategy.match(price, quantity, is_ask)
        diff = time() - now
        self._logger.debug("Matching engine completed in %.2f seconds", diff)
        return matched_ticks
