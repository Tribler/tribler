import unittest

from Tribler.community.market.core.portfolio import Portfolio
from Tribler.community.market.core.tick import TraderId, MessageNumber, MessageId, Price, Quantity, Timeout, Timestamp, \
    Ask, Bid, Trade

class PortfolioTestSuite(unittest.TestCase):
    """Portfolio test cases."""

    def test_portfolio(self):
        # Object creation
        message_number = MessageNumber('message_number')
        timeout = Timeout(1462224447.117)
        timestamp = Timestamp(1462224447.117)
        message_id = MessageId(TraderId('1'), message_number)

        ask = Ask.create(message_id, Price(100), Quantity(30), timeout, timestamp)
        portfolio = Portfolio()

        # Test add tick
        portfolio.add_tick(ask)
        portfolio.add_tick(ask)
        self.assertEquals(ask, portfolio.find_tick(message_id))

        # Test remove tick by id
        portfolio.delete_tick_by_id(message_id)
        self.assertEquals(None, portfolio.find_tick(message_id))


if __name__ == '__main__':
    unittest.main()