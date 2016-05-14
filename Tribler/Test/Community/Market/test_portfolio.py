import unittest

from Tribler.community.market.core.portfolio import Portfolio
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.order_repository import MemoryOrderRepository


class PortfolioTestSuite(unittest.TestCase):
    """Portfolio test cases."""

    def setUp(self):
        # Object creation
        trader_id = TraderId('1')
        message_number = MessageNumber('message_number')
        timeout = Timeout(1462224447.117)
        timestamp = Timestamp(1462224447.117)
        message_id = MessageId(trader_id, message_number)
        order_id = OrderId(trader_id, OrderNumber("order_number"))
        self.ask = Ask(message_id, order_id, Price(100), Quantity(30), timeout, timestamp)
        self.portfolio = Portfolio(MemoryOrderRepository("mid"))


if __name__ == '__main__':
    unittest.main()
