from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.block import MarketBlock
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMarketBlock(AbstractServer):
    """
    This class contains tests for a TrustChain block as used in the market.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestMarketBlock, self).setUp(annotate=annotate)

        tick_tx = {
            'trader_id': 'a' * 40,
            'order_number': 4,
            'price': 34,
            'price_type': 'BTC',
            'quantity': 3,
            'quantity_type': 'MB',
            'timeout': 3600,
            'timestamp': 1234.3,
            'address': '127.0.0.1',
            'port': 1337
        }
        self.tick_block = MarketBlock()
        self.tick_block.type = 'tick'
        self.tick_block.transaction = {'tick': tick_tx}

        self.cancel_block = MarketBlock()
        self.cancel_block.type = 'cancel_order'
        self.cancel_block.transaction = {'trader_id': 'a' * 40, 'order_number': 1}

        tx = {
            'trader_id': 'a' * 40,
            'order_number': 3,
            'partner_trader_id': 'b' * 40,
            'partner_order_number': 4,
            'transaction_number': 3,
            'price': 34,
            'price_type': 'BTC',
            'quantity': 3,
            'quantity_type': 'MB',
            'transferred_price': 4,
            'transferred_quantity': 2,
            'timestamp': 1234.3,
            'payment_complete': False,
            'status': 'pending'
        }
        self.tx_block = MarketBlock()
        self.tx_block.type = 'tx_init'
        bid_dict = tick_tx.copy()
        bid_dict['trader_id'] = 'b' * 40
        bid_dict['order_number'] = 2
        self.tx_block.transaction = {
            'ask': tick_tx.copy(),
            'bid': bid_dict,
            'tx': tx
        }

        payment = {
            'trader_id': 'a' * 40,
            'transaction_number': 3,
            'price': 34,
            'price_type': 'BTC',
            'quantity': 3,
            'quantity_type': 'MB',
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
        self.tick_block.transaction['tick'].pop('price')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction['tick']['price'] = 3.44
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction['tick']['price'] = 3
        self.tick_block.transaction['tick']['trader_id'] = 'g' * 40
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
        self.tx_block.transaction['ask']['price'] = 3.44
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['ask']['price'] = 3
        self.tx_block.transaction['bid']['price'] = 3.44
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['bid']['price'] = 3
        self.tx_block.transaction['tx'].pop('trader_id')
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['tx']['trader_id'] = 'a' * 40
        self.tx_block.transaction['tx']['test'] = 3
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['tx'].pop('test')
        self.tx_block.transaction['tx']['price'] = 3.44
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction['tx']['price'] = 3
        self.tx_block.transaction['tx']['trader_id'] = 'a'
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
