import logging
from time import time

from order import Order
from orderbook import OrderBook
from price import Price
from pricelevel import PriceLevel
from quantity import Quantity
from tickentry import TickEntry
from timestamp import Timestamp
from trade import Trade


class MatchingStrategy(object):
    """Matching strategy interface"""

    def __init__(self, order_book):
        """
        Initialise the matching strategy

        :param order_book: The order book to search in
        :type order_book: OrderBook
        """
        super(MatchingStrategy, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        assert isinstance(order_book, OrderBook), type(order_book)

        self.order_book = order_book

    def match_order(self, order):
        """
        Match an order against the order book

        :param order: The order to match against
        :type order: Order
        :return: The proposed trades and the active ticks
        :rtype: [ProposedTrade], [Tick]
        """
        return NotImplemented


class PriceTimeStrategy(MatchingStrategy):
    """Strategy that uses the price time method for picking ticks"""

    def match_order(self, order):
        """
        Match an order against the order book

        :param order: The order to match against
        :type order: Order
        :return: The proposed trades
        :rtype: ProposedTrade
        """
        assert isinstance(order, Order), type(order)

        proposed_trades = []

        price = order.price
        quantity_to_trade = order.available_quantity

        # Proposed ask ticks
        if order.is_ask():
            if price <= self.order_book.bid_price and quantity_to_trade > Quantity(0):
                best_price_level = self.order_book.bid_price_level

                # Scan the price levels in the order book
                quantity_to_trade, proposed_trades = self._search_for_quantity_in_order_book(self.order_book.bid_price,
                                                                                             best_price_level,
                                                                                             quantity_to_trade,
                                                                                             order)
        # Proposed bid ticks
        else:
            if price >= self.order_book.ask_price and quantity_to_trade > Quantity(0):
                best_price_level = self.order_book.ask_price_level

                # Scan the price levels in the order book
                quantity_to_trade, proposed_trades = self._search_for_quantity_in_order_book(self.order_book.ask_price,
                                                                                             best_price_level,
                                                                                             quantity_to_trade,
                                                                                             order)

        if quantity_to_trade > Quantity(0):
            self._logger.debug("Quantity not matched: %i", int(quantity_to_trade))

        return proposed_trades

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

        self._logger.debug("Searching in price level: %i", int(price))

        if quantity_to_trade <= price_level.depth:  # All the quantity can be matched in this price level
            first_tick = price_level.first_tick

            # Scan the ticks in the price level
            quantity_to_trade, proposed_trades = self._search_for_quantity_in_price_level(first_tick,
                                                                                          quantity_to_trade,
                                                                                          order)
        else:  # Not all the quantity can be matched in this price level
            first_tick = price_level.first_tick

            # Scan the ticks in the price level
            quantity_to_trade, proposed_trades = self._search_for_quantity_in_price_level(first_tick,
                                                                                          quantity_to_trade,
                                                                                          order)

            if order.is_ask():
                # Select the next price level
                next_price, next_price_level = self.order_book._bids._price_tree.prev_item(price)

                if order.price > next_price:  # Price is too low
                    return quantity_to_trade, proposed_trades

            else:
                # Select the next price level
                next_price, next_price_level = self.order_book._asks._price_tree.succ_item(price)

                if order.price < next_price:  # Price is too high
                    return quantity_to_trade, proposed_trades

            # Search the next price level
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

        assert isinstance(tick_entry, TickEntry), type(tick_entry)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(order, Order), type(order)

        if tick_entry.message_id not in order._reserved_ticks:  # Tick is already reserved for this order
            return self._search_for_quantity_in_price_level(tick_entry.next_tick(), quantity_to_trade, order)

        if not tick_entry.is_valid():  # Tick is time out or reserved
            return self._search_for_quantity_in_price_level(tick_entry.next_tick(), quantity_to_trade, order)

        trading_price = tick_entry.price
        trading_party = tick_entry.message_id

        if quantity_to_trade <= tick_entry.quantity:  # All the quantity can be matched in this tick
            trading_quantity = quantity_to_trade
            quantity_to_trade = Quantity(0)

            self._logger.debug("Match with the id (%s) was found for order (%s). Price: %i, Quantity: %i)",
                               str(trading_party), str(order.order_id), int(trading_price), int(trading_quantity))

            reserved = order.reserve_quantity_for_tick(tick_entry._tick)

            if not reserved:  # Error happened
                self._logger.warn("Something went wrong")
                return self._search_for_quantity_in_price_level(tick_entry.next_tick(), quantity_to_trade, order)

            proposed_trades = [Trade.propose(
                self.order_book.message_repository.next_identity(),
                order.order_id,
                trading_party,
                trading_price,
                trading_quantity,
                Timestamp.now()
            )]

        else:  # Not all the quantity can be matched in this tick
            trading_quantity = tick_entry.quantity
            quantity_to_trade -= trading_quantity

            self._logger.debug("Match with the id (%s) was found for order (%s) ", str(tick_entry.message_id),
                               str(order.order_id))

            reserved = order.reserve_quantity_for_tick(tick_entry._tick)

            if not reserved:  # Error happened
                self._logger.warn("Something went wrong")
                return self._search_for_quantity_in_price_level(tick_entry.next_tick(), quantity_to_trade, order)

            proposed_trades = [Trade.propose(
                self.order_book.message_repository.next_identity(),
                order.order_id,
                trading_party,
                trading_price,
                trading_quantity,
                Timestamp.now()
            )]

            # Search the next tick
            quantity_to_trade, trades = self._search_for_quantity_in_price_level(tick_entry.next_tick(),
                                                                                 quantity_to_trade,
                                                                                 order)

            proposed_trades = proposed_trades + trades

        return quantity_to_trade, proposed_trades


class MatchingEngine(object):
    """Matches ticks and orders to the order book"""

    def __init__(self, matching_strategy):
        """
        Initialise the matching engine

        :param matching_strategy: The strategy to use
        :type matching_strategy: MatchingStrategy
        """
        super(MatchingEngine, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        assert isinstance(matching_strategy, MatchingStrategy), type(matching_strategy)
        self.matching_strategy = matching_strategy

    def match_order(self, order):
        """
        Match an order against the order book

        :param order: The order to match against
        :type order: Order
        :return: The proposed trades and the active ticks
        :rtype: [ProposedTrade], [Tick]
        """
        assert isinstance(order, Order), type(order)
        now = time()
        proposed_trades, active_ticks = self.matching_strategy.match_order(order)
        diff = time() - now
        self._logger.debug("Matching engine completed in %.2f seconds", diff)
        return proposed_trades, active_ticks
