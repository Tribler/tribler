from Tribler.community.market.core.message_repository import MessageRepository
from orderbook import OrderBook
from pricelevel import PriceLevel
from tick import Tick, Trade, Timestamp, Quantity, Price
from tickentry import TickEntry


class MatchingStrategy(object):
    def __init__(self, order_book, message_repository):
        super(MatchingStrategy, self).__init__()

        assert isinstance(order_book, OrderBook), type(order_book)
        assert isinstance(message_repository, MessageRepository), type(message_repository)

        self.order_book = order_book
        self.message_repository = message_repository

    def match_tick(self, tick):
        return NotImplemented


class PriceTimeStrategy(MatchingStrategy):
    def match_tick(self, tick):
        assert isinstance(tick, Tick), type(tick)

        proposed_trades = []
        active_ticks = []

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

        # Active ticks
        if quantity_to_trade > Quantity(0):
            tick.quantity = quantity_to_trade
            active_ticks.append(tick)

        return proposed_trades, active_ticks

    def _search_for_quantity_in_order_book(self, price_level_price, price_level, quantity_to_trade, tick):
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
                next_price_level_price, next_price_level = self.order_book._bids._price_tree.succ_item(
                    price_level_price)
            else:
                next_price_level_price, next_price_level = self.order_book._asks._price_tree.succ_item(
                    price_level_price)

            quantity_to_trade, trades = self._search_for_quantity_in_order_book(next_price_level_price, next_price_level,
                                                                                quantity_to_trade, tick)
            proposed_trades = proposed_trades + trades

        return quantity_to_trade, proposed_trades

    def _search_for_quantity_in_price_level(self, tick_entry, quantity_to_trade, tick):
        if tick_entry is None:
            return quantity_to_trade, []
        assert isinstance(tick_entry, TickEntry), type(tick_entry)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(tick, Tick), type(tick)

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
    def __init__(self, matching_strategy):
        super(MatchingEngine, self).__init__()

        assert isinstance(matching_strategy, MatchingStrategy), type(matching_strategy)
        self.matching_strategy = matching_strategy

    def match_tick(self, tick):
        assert isinstance(tick, Tick), type(tick)
        return self.matching_strategy.match_tick(tick)
