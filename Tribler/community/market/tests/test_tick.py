from .context import Tribler
from Tribler.community.market.core.tick import TraderId, MessageNumber, MessageId, Price
import unittest


class TickTestSuite(unittest.TestCase):
    """Tick test cases."""

    def test_trader_id(self):
        trader_id = TraderId('trader_id')
        trader_id2 = TraderId('trader_id')
        trader_id3 = TraderId('trader_id_2')
        self.assertEqual('trader_id', str(trader_id))
        self.assertTrue(trader_id == trader_id2)
        self.assertTrue(trader_id == trader_id)
        self.assertTrue(trader_id != trader_id3)
        self.assertFalse(trader_id == 6)
        self.assertEqual(trader_id.__hash__(), trader_id2.__hash__())
        self.assertNotEqual(trader_id.__hash__(), trader_id3.__hash__())

if __name__ == '__main__':
    unittest.main()
