from twisted.internet.defer import inlineCallbacks

from Tribler.community.market.block import MarketBlock
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.tick import Ask
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import Transaction, TransactionId, TransactionNumber
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.test_as_server import AbstractServer


class TestMarketBlock(AbstractServer):
    """
    This class contains tests for a TrustChain block as used in the market.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestMarketBlock, self).setUp(annotate=annotate)

        self.ask = Ask(OrderId(TraderId('0' * 40), OrderNumber(1)),
                       AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), Timeout(30), Timestamp(0.0), True)
        self.bid = Ask(OrderId(TraderId('1' * 40), OrderNumber(1)),
                       AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), Timeout(30), Timestamp(0.0), False)
        self.transaction = Transaction(TransactionId(TraderId('0' * 40), TransactionNumber(1)),
                                       AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')),
                                       OrderId(TraderId('0' * 40), OrderNumber(1)),
                                       OrderId(TraderId('1' * 40), OrderNumber(1)), Timestamp(0.0))

        ask_tx = self.ask.to_block_dict()
        bid_tx = self.bid.to_block_dict()

        self.tick_block = MarketBlock()
        self.tick_block.type = 'tick'
        self.tick_block.transaction = {'tick': ask_tx}

        self.cancel_block = MarketBlock()
        self.cancel_block.type = 'cancel_order'
        self.cancel_block.transaction = {'trader_id': 'a' * 40, 'order_number': 1}

        self.tx_block = MarketBlock()
        self.tx_block.type = 'tx_init'
        self.tx_block.transaction = {
            'ask': ask_tx,
            'bid': bid_tx,
            'tx': self.transaction.to_dictionary()
        }

        payment = {
            'trader_id': 'a' * 40,
            'transaction_number': 3,
            'transferred': {
                'amount': 3,
                'type': 'BTC'
            },
            'payment_id': 'a',
            'address_from': 'a',
            'address_to': 'b',
            'timestamp': 1234.3,
            'success': True
        }
        self.payment_block = MarketBlock()
        self.payment_block.type = 'tx_payment'
        self.payment_block.transaction = {'payment': payment}

    def test_tick_block(self):
        """
        Test whether a tick block can be correctly verified
        """
        self.assertTrue(self.tick_block.is_valid_tick_block())

        self.tick_block.type = 'test'
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.type = 'tick'
        self.tick_block.transaction['test'] = self.tick_block.transaction.pop('tick')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction['tick'] = self.tick_block.transaction.pop('test')
        self.tick_block.transaction['tick'].pop('timeout')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction['tick']['timeout'] = "300"
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction['tick']['timeout'] = 300
        self.tick_block.transaction['tick']['trader_id'] = 'g' * 40
        self.assertFalse(self.tick_block.is_valid_tick_block())

        # Make the asset pair invalid
        assets = self.tick_block.transaction['tick']['assets']
        self.tick_block.transaction['tick']['trader_id'] = 'a' * 40
        assets['test'] = assets.pop('first')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets['first'] = assets.pop('test')
        assets['first']['test'] = assets['first'].pop('amount')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets['first']['amount'] = assets['first']['test']
        assets['second']['test'] = assets['second'].pop('amount')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets['second']['amount'] = assets['second']['test']
        assets['first']['amount'] = 3.4
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets['first']['amount'] = 3
        assets['second']['type'] = 4
        self.assertFalse(self.tick_block.is_valid_tick_block())

    def test_cancel_block(self):
        """
        Test whether a cancel block can be correctly verified
        """
        self.assertTrue(self.cancel_block.is_valid_cancel_block())

        self.cancel_block.type = 'cancel'
        self.assertFalse(self.cancel_block.is_valid_cancel_block())

        self.cancel_block.type = 'cancel_order'
        self.cancel_block.transaction.pop('trader_id')
        self.assertFalse(self.cancel_block.is_valid_cancel_block())

        self.cancel_block.transaction['trader_id'] = 3
        self.assertFalse(self.cancel_block.is_valid_cancel_block())

    def test_tx_init_done_block(self):
        """
        Test whether a tx_init/tx_done block can be correctly verified
        """
        self.assertTrue(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.type = 'test'
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.type = 'tx_init'
        self.tx_block.transaction['test'] = self.tx_block.transaction.pop('ask')
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['ask'] = self.tx_block.transaction.pop('test')
        self.tx_block.transaction['ask']['timeout'] = 3.44
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['ask']['timeout'] = 3
        self.tx_block.transaction['bid']['timeout'] = 3.44
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['bid']['timeout'] = 3
        self.tx_block.transaction['tx'].pop('trader_id')
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['tx']['trader_id'] = 'a' * 40
        self.tx_block.transaction['tx']['test'] = 3
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['tx'].pop('test')
        self.tx_block.transaction['tx']['trader_id'] = 'a'
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['tx']['trader_id'] = 'a' * 40
        self.tx_block.transaction['tx']['assets']['first']['amount'] = 3.4
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['tx']['assets']['first']['amount'] = 3
        self.tx_block.transaction['tx']['transferred']['first']['amount'] = 3.4
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['tx']['transferred']['first']['amount'] = 3
        self.tx_block.transaction['tx']['transaction_number'] = 3.4
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

    def test_tx_payment_block(self):
        """
        Test whether a tx_payment block can be correctly verified
        """
        self.assertTrue(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.type = 'test'
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.type = 'tx_payment'
        self.payment_block.transaction['test'] = self.payment_block.transaction.pop('payment')
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction['payment'] = self.payment_block.transaction.pop('test')
        self.payment_block.transaction['payment'].pop('address_to')
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction['payment']['address_to'] = 'a'
        self.payment_block.transaction['payment']['test'] = 'a'
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction['payment'].pop('test')
        self.payment_block.transaction['payment']['address_to'] = 3
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction['payment']['address_to'] = 'a'
        self.payment_block.transaction['payment']['trader_id'] = 'a' * 39
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

    def test_is_valid_asset_pair(self):
        """
        Test the method to verify whether an asset pair is valid
        """
        self.assertFalse(MarketBlock.is_valid_asset_pair({'a': 'b'}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({'first': {'amount': 3, 'type': 'DUM1'},
                                                          'second': {'amount': 3}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({'first': {'type': 'DUM1'},
                                                          'second': {'amount': 3, 'type': 'DUM2'}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({'first': {'amount': "4", 'type': 'DUM1'},
                                                          'second': {'amount': 3, 'type': 'DUM2'}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({'first': {'amount': 4, 'type': 'DUM1'},
                                                          'second': {'amount': "3", 'type': 'DUM2'}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({'first': {'amount': -4, 'type': 'DUM1'},
                                                          'second': {'amount': 3, 'type': 'DUM2'}}))
