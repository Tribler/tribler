from __future__ import absolute_import

import unittest

from Tribler.community.market.core import DeclinedTradeReason
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import CounterTrade, DeclinedTrade, ProposedTrade, Trade


class TradeTestSuite(unittest.TestCase):
    """Trade test cases."""

    def setUp(self):
        # Object creation
        self.trade = Trade(TraderId(b'0'),
                           OrderId(TraderId(b'0'), OrderNumber(3)),
                           OrderId(TraderId(b'0'), OrderNumber(4)), 1234, Timestamp(1462224447.117))

    def test_to_network(self):
        # Test for to network
        self.assertEquals(NotImplemented, self.trade.to_network())


class ProposedTradeTestSuite(unittest.TestCase):
    """Proposed trade test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(TraderId(b'0'),
                                            OrderId(TraderId(b'0'), OrderNumber(1)),
                                            OrderId(TraderId(b'1'), OrderNumber(2)),
                                            AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')),
                                            Timestamp(1462224447.117))

    def test_to_network(self):
        # Test for to network
        self.assertEquals((TraderId(b'0'), Timestamp(1462224447.117),
                           OrderNumber(1), OrderId(TraderId(b'1'), OrderNumber(2)), self.proposed_trade.proposal_id,
                           AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB'))), self.proposed_trade.to_network())

    def test_from_network(self):
        # Test for from network
        data = ProposedTrade.from_network(type('Data', (object,),
                                               {"trader_id": TraderId(b'0'),
                                                "order_number": OrderNumber(1),
                                                "recipient_order_id": OrderId(TraderId('1'), OrderNumber(2)),
                                                "proposal_id": 1234,
                                                "timestamp": Timestamp(1462224447.117),
                                                "assets": AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB'))}))

        self.assertEquals(TraderId(b'0'), data.trader_id)
        self.assertEquals(OrderId(TraderId(b'0'), OrderNumber(1)), data.order_id)
        self.assertEquals(OrderId(TraderId(b'1'), OrderNumber(2)),
                          data.recipient_order_id)
        self.assertEquals(1234, data.proposal_id)
        self.assertEquals(AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')), data.assets)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


class DeclinedTradeTestSuite(unittest.TestCase):
    """Declined trade test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(TraderId(b'0'),
                                            OrderId(TraderId(b'0'), OrderNumber(1)),
                                            OrderId(TraderId(b'1'), OrderNumber(2)),
                                            AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')),
                                            Timestamp(1462224447.117))
        self.declined_trade = Trade.decline(TraderId(b'0'),
                                            Timestamp(1462224447.117), self.proposed_trade,
                                            DeclinedTradeReason.ORDER_COMPLETED)

    def test_to_network(self):
        # Test for to network
        data = self.declined_trade.to_network()

        self.assertEquals(data[0], TraderId(b"0"))
        self.assertEquals(data[1], Timestamp(1462224447.117))
        self.assertEquals(data[2], OrderNumber(2))
        self.assertEquals(data[3], OrderId(TraderId(b"0"), OrderNumber(1)))
        self.assertEquals(data[4], self.proposed_trade.proposal_id)

    def test_from_network(self):
        # Test for from network
        data = DeclinedTrade.from_network(type('Data', (object,),
                                               {"trader_id": TraderId(b'0'),
                                                "order_number": OrderNumber(1),
                                                "recipient_order_id": OrderId(TraderId(b'1'), OrderNumber(2)),
                                                "proposal_id": 1235,
                                                "timestamp": Timestamp(1462224447.117),
                                                "decline_reason": 0}))

        self.assertEquals(TraderId(b'0'), data.trader_id)
        self.assertEquals(OrderId(TraderId(b'1'), OrderNumber(2)),
                          data.recipient_order_id)
        self.assertEquals(1235, data.proposal_id)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)

    def test_decline_reason(self):
        """
        Test the declined reason
        """
        self.assertEqual(self.declined_trade.decline_reason, DeclinedTradeReason.ORDER_COMPLETED)


class CounterTradeTestSuite(unittest.TestCase):
    """Counter trade test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(TraderId(b'0'),
                                            OrderId(TraderId(b'0'), OrderNumber(1)),
                                            OrderId(TraderId(b'1'), OrderNumber(2)),
                                            AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')),
                                            Timestamp(1462224447.117))
        self.counter_trade = Trade.counter(TraderId(b'0'), AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')),
                                           Timestamp(1462224447.117), self.proposed_trade)

    def test_to_network(self):
        # Test for to network
        self.assertEquals(
            ((TraderId(b'0'), Timestamp(1462224447.117), OrderNumber(2),
              OrderId(TraderId(b'0'), OrderNumber(1)), self.proposed_trade.proposal_id,
              AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')))), self.counter_trade.to_network())

    def test_from_network(self):
        # Test for from network
        data = CounterTrade.from_network(type('Data', (object,),
                                              {"trader_id": TraderId(b'0'),
                                               "timestamp": Timestamp(1462224447.117),
                                               "order_number": OrderNumber(1),
                                               "recipient_order_id": OrderId(TraderId(b'1'), OrderNumber(2)),
                                               "proposal_id": 1236,
                                               "assets": AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')), }))

        self.assertEquals(TraderId(b'0'), data.trader_id)
        self.assertEquals(OrderId(TraderId(b'0'), OrderNumber(1)), data.order_id)
        self.assertEquals(OrderId(TraderId(b'1'), OrderNumber(2)),
                          data.recipient_order_id)
        self.assertEquals(1236, data.proposal_id)
        self.assertEquals(AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')), data.assets)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)
