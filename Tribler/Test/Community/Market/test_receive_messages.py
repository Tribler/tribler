from Tribler.Test.Community.Market.test_community import AbstractTestMarketCommunity
from Tribler.Test.Community.Trustchain.test_trustchain_utilities import TestBlock
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.trustchain.community import HALF_BLOCK
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class MarketCommunityMessagesTestSuite(AbstractTestMarketCommunity):
    """
    Test receiving messages in the Market community
    """

    def get_half_block_message(self, block):
        """
        Create a message from a given block
        """
        candidate = Candidate(self.dispersy.lan_address, False)
        meta = self.market_community.get_meta_message(HALF_BLOCK)
        message = meta.impl(
            distribution=(self.market_community.claim_global_time(),),
            destination=(candidate,),
            payload=(block,)
        )
        return message

    def create_order_status_from_tick(self, tick, traded_quantity):
        """
        Create an order status dictionary from a tick.
        """
        return {
            "trader_id": str(tick.order_id.trader_id),
            "order_number": int(tick.order_id.order_number),
            "price": float(tick.price),
            "price_type": tick.price.wallet_id,
            "quantity": float(tick.quantity),
            "quantity_type": tick.quantity.wallet_id,
            "traded_quantity": traded_quantity,
            "timeout": float(tick.timeout),
            "timestamp": float(tick.timestamp),
            "ip": "127.0.0.1",
            "port": 1234
        }

    def create_tx_done_block(self, ask, bid, transferred_quantity):
        """
        Create a tx_done block, according to an ask and bid.
        """
        tx = {
            "type": "tx_done",
            "ask": self.create_order_status_from_tick(ask, 1),
            "bid": self.create_order_status_from_tick(bid, 1),
            "tx": {
                "trader_id": "abcd",
                "transaction_number": 3,
                "quantity": transferred_quantity,
                "quantity_type": "MC"
            }
        }
        return TestBlock(transaction=tx)

    def create_tick_block(self, tick):
        """
        Create a tick block.
        """
        tx = {
            "type": "tick",
            "tick": tick.to_block_dict()
        }
        tx["tick"]["address"] = "127.0.0.1"
        tx["tick"]["port"] = 1234
        return TestBlock(transaction=tx)

    @blocking_call_on_reactor_thread
    def test_receive_tick(self):
        """
        Test whether the right operations happen when we receive a block with a tick
        """
        ask_block = self.create_tick_block(self.ask)
        self.market_community.received_half_block([self.get_half_block_message(ask_block)])
        self.assertEqual(len(self.market_community.order_book.asks), 1)

        bid_block = self.create_tick_block(self.bid)
        self.market_community.received_half_block([self.get_half_block_message(bid_block)])
        self.assertEqual(len(self.market_community.order_book.bids), 1)

        # If we receive it again, we should not insert it twice
        self.market_community.received_half_block([self.get_half_block_message(ask_block)])
        self.assertEqual(len(self.market_community.order_book.asks), 1)

    @blocking_call_on_reactor_thread
    def test_receive_tx_done_1(self):
        """
        Test whether ticks are created when we receive a block with a tx_done
        """
        block = self.create_tx_done_block(self.ask, self.bid, 1)
        self.market_community.received_half_block([self.get_half_block_message(block)])
        self.assertEqual(len(self.market_community.order_book.asks), 1)
        self.assertEqual(len(self.market_community.order_book.bids), 1)

    @blocking_call_on_reactor_thread
    def test_receive_tx_done_2(self):
        """
        Test whether ticks are removed when we receive a block with a tx_done
        """
        self.market_community.order_book.insert_ask(self.ask)
        self.market_community.order_book.insert_bid(self.bid)

        block = self.create_tx_done_block(self.ask, self.bid, 22)
        self.market_community.received_half_block([self.get_half_block_message(block)])
        self.assertEqual(len(self.market_community.order_book.asks), 1)
        self.assertEqual(len(self.market_community.order_book.bids), 0)
        self.assertEqual(self.market_community.order_book.get_tick(self.ask.order_id).quantity, Quantity(8, 'DUM2'))

    @blocking_call_on_reactor_thread
    def test_receive_done_tick(self):
        """
        Test whether we don't insert a tick from an order that has been completed already
        """
        self.market_community.order_book.insert_bid(self.bid)
        block = self.create_tx_done_block(self.ask, self.bid, 22)
        self.market_community.received_half_block([self.get_half_block_message(block)])
        self.assertEqual(len(self.market_community.order_book.bids), 0)

        bid_block = self.create_tick_block(self.bid)
        self.market_community.received_half_block([self.get_half_block_message(bid_block)])
        self.assertEqual(len(self.market_community.order_book.bids), 0)
