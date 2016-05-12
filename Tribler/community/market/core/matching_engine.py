from message_repository import MessageRepository
from order import Order
from orderbook import OrderBook
from price import Price
from pricelevel import PriceLevel
from quantity import Quantity
from tick import Tick
from tickentry import TickEntry
from timestamp import Timestamp
from trade import Trade


class MatchingStrategy(object):
    """Matching strategy interface"""

    def __init__(self, order_book, message_repository):
        """
        Initialise the matching strategy

        :param order_book: The order book to search in
        :param message_repository: The message repository to store and retrieve messages
        :type order_book: OrderBook
        :type message_repository: MessageRepository
        """
        super(MatchingStrategy, self).__init__()

        assert isinstance(order_book, OrderBook), type(order_book)
        assert isinstance(message_repository, MessageRepository), type(message_repository)

        self.order_book = order_book
        self.message_repository = message_repository

    def match_order(self, order):
        """
        Match an order against the order book

        :param order: The order to match against
        :type order: Order
        :return: The proposed trades and the active ticks
        :rtype: [ProposedTrade], [Tick]
        """
        return NotImplemented

    def match_tick(self, tick):
        """
        Match a tick against the order book

        :param tick: The tick to match against
        :type tick: Tick
        :return: The proposed trades and the left over quantity
        :rtype: [ProposedTrade], Quantity
        """
        return NotImplemented


class PriceTimeStrategy(MatchingStrategy):
    """Strategy that uses the price time method for picking ticks"""

    def match_order(self, order):
        """
        Match an order against the order book

        :param order: The order to match against
        :type order: Order
        :return: The proposed trades and the active ticks
        :rtype: [ProposedTrade], [Tick]
        """
        assert isinstance(order, Order), type(order)

        active_ticks = []

        proposed_trades, quantity_to_trade = self.match(order)

        # Active ticks
        if quantity_to_trade > Quantity(0):
            if order.is_ask():
                active_tick = self.order_book.create_ask(order.price, quantity_to_trade, order.timeout, order.timestamp)
            else:
                active_tick = self.order_book.create_bid(order.price, quantity_to_trade, order.timeout, order.timestamp)
            active_ticks.append(active_tick)

        for message in active_ticks:
            order.add_message(message)

        for message in proposed_trades:
            order.add_message(message)

        return proposed_trades, active_ticks

    def match_tick(self, tick):
        """
        Match a tick against the order book

        :param tick: The tick to match against
        :type tick: Tick
        :return: The proposed trades and the left over quantity
        :rtype: [ProposedTrade], Quantity
        """
        assert isinstance(tick, Tick), type(tick)

        return self.match(tick)

    def match(self, tick):
        """
        Match a tick against the order book

        :param tick: The tick to match against
        :return: The proposed trades and the left over quantity
        :rtype: [ProposedTrade], Quantity
        """
        assert hasattr(tick, 'message_id')
        assert hasattr(tick, 'price')
        assert hasattr(tick, 'quantity')
        assert hasattr(tick, 'is_ask'), callable(getattr(tick, 'is_ask'))

        proposed_trades = []

        quantity_to_trade = tick.quantity

        # Proposed ask ticks
        if tick.is_ask():
            if tick.price <= self.order_book.bid_price and tick.quantity > Quantity(0):
                best_price_level = self.order_book.bid_price_level
                quantity_to_trade, proposed_trades = self._search_for_quantity_in_order_book(self.order_book.bid_price,
                                                                                             best_price_level,
                                                                                             quantity_to_trade, tick)
        # Proposed bid ticks
        else:
            if tick.price >= self.order_book.ask_price and tick.quantity > Quantity(0):
                best_price_level = self.order_book.ask_price_level
                quantity_to_trade, proposed_trades = self._search_for_quantity_in_order_book(self.order_book.ask_price,
                                                                                             best_price_level,
                                                                                             quantity_to_trade, tick)

        return proposed_trades, quantity_to_trade

    def _search_for_quantity_in_order_book(self, price_level_price, price_level, quantity_to_trade, tick):
        """
        Search through the price levels in the order book
        """
        if price_level is None:
            return quantity_to_trade, []
        assert isinstance(price_level_price, Price), type(price_level_price)
        assert isinstance(price_level, PriceLevel), type(price_level)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(tick, Tick), type(tick)

        if quantity_to_trade <= price_level.depth:
            head_tick = price_level.first_tick
            quantity_to_trade, proposed_trades = self._search_for_quantity_in_price_level(head_tick, quantity_to_trade,
                                                                                          tick)
        else:
            head_tick = price_level.first_tick
            quantity_to_trade, proposed_trades = self._search_for_quantity_in_price_level(head_tick, quantity_to_trade,
                                                                                          tick)

            if tick.is_ask():
                next_price_level_price, next_price_level = self.order_book._bids._price_tree.prev_item(
                    price_level_price)
            else:
                next_price_level_price, next_price_level = self.order_book._asks._price_tree.succ_item(
                    price_level_price)

            quantity_to_trade, trades = self._search_for_quantity_in_order_book(next_price_level_price,
                                                                                next_price_level,
                                                                                quantity_to_trade, tick)
            proposed_trades = proposed_trades + trades

        return quantity_to_trade, proposed_trades

    def _search_for_quantity_in_price_level(self, tick_entry, quantity_to_trade, tick):
        """
        Search through the tick entries in the price levels
        """
        if tick_entry is None:
            return quantity_to_trade, []
        assert isinstance(tick_entry, TickEntry), type(tick_entry)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(tick, Tick), type(tick)

        if not tick_entry.is_valid():
            # self.order_book.remove_tick(tick_entry.message_id)
            return self._search_for_quantity_in_price_level(tick_entry.next_tick(), quantity_to_trade, tick)

        traded_price = tick_entry.price
        counter_party = tick_entry.message_id

        if quantity_to_trade <= tick_entry.quantity:
            traded_quantity = quantity_to_trade
            quantity_to_trade = Quantity(0)

            proposed_trades = [Trade.propose(
                self.message_repository.next_identity(),
                tick.message_id,
                counter_party,
                traded_price,
                traded_quantity,
                Timestamp.now()
            )]
        else:
            traded_quantity = tick_entry.quantity
            quantity_to_trade -= traded_quantity

            proposed_trades = [Trade.propose(
                self.message_repository.next_identity(),
                tick.message_id,
                counter_party,
                traded_price,
                traded_quantity,
                Timestamp.now()
            )]

            quantity_to_trade, trades = self._search_for_quantity_in_price_level(tick_entry.next_tick(),
                                                                                 quantity_to_trade,
                                                                                 tick)

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
        return self.matching_strategy.match_order(order)

    def match_tick(self, tick):
        """
        Match a tick against the order book

        :param tick: The tick to match against
        :type tick: Tick
        :return: The proposed trades and the left over quantity
        :rtype: [ProposedTrade], Quantity
        """
        assert isinstance(tick, Tick), type(tick)
        return self.matching_strategy.match_tick(tick)
