from Tribler.pyipv8.ipv8.attestation.trustchain.block import TrustChainBlock


class MarketBlock(TrustChainBlock):
    """
    This class represents a block in the market community.
    It contains various utility methods to verify validity within the context of the market.
    """

    @staticmethod
    def has_fields(needles, haystack):
        for needle in needles:
            if needle not in haystack:
                return False
        return True

    @staticmethod
    def has_required_types(types, container):
        for key, required_type in types:
            if not isinstance(container[key], required_type):
                return False
        return True

    @staticmethod
    def is_valid_trader_id(trader_id):
        if len(trader_id) != 40:
            return False

        try:
            int(trader_id, 16)
        except ValueError:  # Not a hexadecimal
            return False
        return True

    @staticmethod
    def is_valid_tick(tick):
        """
        Verify whether a dictionary that contains a tick, is valid.
        """
        required_fields = ['trader_id', 'order_number', 'price', 'price_type', 'quantity', 'quantity_type', 'timeout',
                           'timestamp', 'address', 'port']
        if not MarketBlock.has_fields(required_fields, tick):
            return False

        required_types = [('trader_id', str), ('order_number', int), ('price', (int, long)), ('quantity', (int, long)),
                          ('price_type', str), ('quantity_type', str), ('timestamp', float), ('timeout', int),
                          ('address', str), ('port', int)]

        if not MarketBlock.is_valid_trader_id(tick['trader_id']):
            return False
        if not MarketBlock.has_required_types(required_types, tick):
            return False

        return True

    @staticmethod
    def is_valid_tx(tx):
        """
        Verify whether a dictionary that contains a transaction, is valid.
        """
        required_fields = ['trader_id', 'order_number', 'partner_trader_id', 'partner_order_number',
                           'transaction_number', 'price', 'price_type', 'quantity', 'quantity_type',
                           'transferred_price', 'transferred_quantity', 'timestamp', 'payment_complete', 'status']
        if not MarketBlock.has_fields(required_fields, tx):
            return False
        if len(tx) != len(required_fields):
            return False

        required_types = [('trader_id', str), ('order_number', int), ('partner_trader_id', str),
                          ('partner_order_number', int), ('transaction_number', int), ('price', (int, long)),
                          ('price_type', str), ('quantity', (int, long)), ('quantity_type', str),
                          ('transferred_price', (int, long)), ('transferred_quantity', (int, long)),
                          ('timestamp', float), ('payment_complete', bool), ('status', str)]

        if not MarketBlock.is_valid_trader_id(tx['trader_id']) or not \
                MarketBlock.is_valid_trader_id(tx['partner_trader_id']):
            return False
        if not MarketBlock.has_required_types(required_types, tx):
            return False

        return True

    @staticmethod
    def is_valid_payment(payment):
        """
        Verify whether a dictionary that contains a payment, is valid.
        """
        required_fields = ['trader_id', 'transaction_number', 'price', 'price_type', 'quantity', 'quantity_type',
                           'payment_id', 'address_from', 'address_to', 'timestamp', 'success']
        if not MarketBlock.has_fields(required_fields, payment):
            return False
        if len(payment) != len(required_fields):
            return False

        required_types = [('trader_id', str), ('transaction_number', int), ('price', (int, long)),
                          ('price_type', str), ('quantity', (int, long)), ('quantity_type', str), ('payment_id', str),
                          ('address_from', str), ('address_to', str), ('timestamp', float), ('success', bool)]
        if not MarketBlock.has_required_types(required_types, payment):
            return False

        return True

    def is_valid_tick_block(self):
        """
        Verify whether an incoming block with the tick type is valid.
        """
        if self.type != "tick":
            return False
        if not MarketBlock.has_fields(['tick'], self.transaction):
            return False
        if not MarketBlock.is_valid_tick(self.transaction['tick']):
            return False

        return True

    def is_valid_cancel_block(self):
        """
        Verify whether an incoming block with cancel type is valid.
        """
        if self.type != "cancel_order":
            return False

        if not MarketBlock.has_fields(['trader_id', 'order_number'], self.transaction):
            return False

        required_types = [('trader_id', str), ('order_number', int)]
        if not MarketBlock.has_required_types(required_types, self.transaction):
            return False

        return True

    def is_valid_tx_init_done_block(self):
        """
        Verify whether an incoming block with tx_init/tx_done type is valid.
        """
        if self.type != "tx_init" and self.type != "tx_done":
            return False

        if not MarketBlock.has_fields(['ask', 'bid', 'tx'], self.transaction):
            return False

        if not MarketBlock.is_valid_tick(self.transaction['ask']):
            return False
        if not MarketBlock.is_valid_tick(self.transaction['bid']):
            return False
        if not MarketBlock.is_valid_tx(self.transaction['tx']):
            return False

        return True

    def is_valid_tx_payment_block(self):
        """
        Verify whether an incoming block with tx_payment type is valid.
        """
        if self.type != "tx_payment":
            return False

        if not MarketBlock.has_fields(['payment'], self.transaction):
            return False
        if not MarketBlock.is_valid_payment(self.transaction['payment']):
            return False

        return True
