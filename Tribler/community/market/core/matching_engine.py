from order import Order
from price_level import PriceLevel
from orderbook import OrderBook
from tick import Tick, Trade, Timestamp, Quantity, Price


class MatchingStrategy(object):
    def __init__(self, order_book):
        super(MatchingStrategy, self).__init__()

        assert isinstance(order_book, OrderBook), type(order_book)

        self.order_book = order_book

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
                quantity_to_trade, proposed_trades = self.search_for_quantity_in_order_book(self.order_book.bid_price,
                                                                                            best_price_level,
                                                                                            quantity_to_trade, tick)
        # Proposed bid ticks
        else:
            if tick.price >= self.order_book.ask_price and tick.quantity > Quantity(0):
                best_price_level = self.order_book.ask_price_level
                quantity_to_trade, proposed_trades = self.search_for_quantity_in_order_book(self.order_book.ask_price,
                                                                                            best_price_level,
                                                                                            quantity_to_trade, tick)

        # Active ticks
        if quantity_to_trade > Quantity(0):
            tick.quantity = quantity_to_trade
            active_ticks.append(tick)

        return proposed_trades, active_ticks

    def search_for_quantity_in_order_book(self, price_level_price, price_level, quantity_to_trade, tick):
        if price_level is None:
            return quantity_to_trade, []
        assert isinstance(price_level_price, Price), type(price_level_price)
        assert isinstance(price_level, PriceLevel), type(price_level)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(tick, Tick), type(tick)

        if quantity_to_trade <= price_level.depth:
            head_order = price_level.first_order
            quantity_to_trade, proposed_trades = self.search_for_quantity_in_price_level(head_order, quantity_to_trade,
                                                                                         tick)
        else:
            head_order = price_level.first_order
            quantity_to_trade, proposed_trades = self.search_for_quantity_in_price_level(head_order, quantity_to_trade,
                                                                                         tick)

            if tick.is_ask():
                next_price_level_price, next_price_level = self.order_book._bids._price_tree.succ_item(
                    price_level_price)
            else:
                next_price_level_price, next_price_level = self.order_book._asks._price_tree.succ_item(
                    price_level_price)

            quantity_to_trade, trades = self.search_for_quantity_in_order_book(next_price_level_price, next_price_level,
                                                                               quantity_to_trade, tick)
            proposed_trades = proposed_trades + trades

        return quantity_to_trade, proposed_trades

    def search_for_quantity_in_price_level(self, order, quantity_to_trade, tick):
        if order is None:
            return quantity_to_trade, []
        assert isinstance(order, Order), type(order)
        assert isinstance(quantity_to_trade, Quantity), type(quantity_to_trade)
        assert isinstance(tick, Tick), type(tick)

        traded_price = order.price
        counter_party = order.message_id

        if quantity_to_trade <= order.quantity:
            traded_quantity = quantity_to_trade
            quantity_to_trade = Quantity(0)

            proposed_trades = [Trade.propose(
                self.order_book.generate_message_id(),
                tick.message_id,
                counter_party,
                traded_price,
                traded_quantity,
                Timestamp.now()
            )]
        else:
            traded_quantity = order.quantity
            quantity_to_trade -= traded_quantity

            proposed_trades = [Trade.propose(
                self.order_book.generate_message_id(),
                tick.message_id,
                counter_party,
                traded_price,
                traded_quantity,
                Timestamp.now()
            )]

            quantity_to_trade, trades = self.search_for_quantity_in_price_level(order.next_order(), quantity_to_trade,
                                                                                tick)

            proposed_trades = proposed_trades + trades

        return quantity_to_trade, proposed_trades


class MatchingEngine(object):
    def __init__(self, order_book, matching_strategy):
        super(MatchingEngine, self).__init__()

        assert isinstance(order_book, OrderBook), type(order_book)

        self.order_book = order_book
        self.matching_strategy = matching_strategy

    def match_tick(self, tick):
        assert isinstance(tick, Tick), type(tick)

        return self.matching_strategy.match_tick(tick)
