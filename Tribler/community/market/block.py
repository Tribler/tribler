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
    def is_valid_asset_pair(assets_dict, amount_positive=True):
        if 'first' not in assets_dict or 'second' not in assets_dict:
            return False
        if 'amount' not in assets_dict['first'] or 'type' not in assets_dict['first']:
            return False
        if 'amount' not in assets_dict['second'] or 'type' not in assets_dict['second']:
            return False

        if not MarketBlock.has_required_types([('amount', (int, long)), ('type', str)], assets_dict['first']):
            return False
        if not MarketBlock.has_required_types([('amount', (int, long)), ('type', str)], assets_dict['second']):
            return False

        if amount_positive and (assets_dict['first']['amount'] <= 0 or assets_dict['second']['amount'] <= 0):
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
        required_fields = ['trader_id', 'order_number', 'assets', 'timeout', 'timestamp', 'address', 'port', 'traded']
        if not MarketBlock.has_fields(required_fields, tick):
            return False

        required_types = [('trader_id', str), ('order_number', int), ('assets', dict), ('timestamp', float),
                          ('timeout', int), ('address', str), ('port', int)]

        if not MarketBlock.is_valid_trader_id(tick['trader_id']):
            return False
        if not MarketBlock.is_valid_asset_pair(tick['assets']):
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
                           'transaction_number', 'assets', 'transferred', 'timestamp', 'payment_complete', 'status']
        if not MarketBlock.has_fields(required_fields, tx):
            return False
        if len(tx) != len(required_fields):
            return False

        required_types = [('trader_id', str), ('order_number', int), ('partner_trader_id', str),
                          ('partner_order_number', int), ('transaction_number', int), ('assets', dict),
                          ('transferred', dict), ('timestamp', float), ('payment_complete', bool), ('status', str)]

        if not MarketBlock.is_valid_trader_id(tx['trader_id']) or not \
                MarketBlock.is_valid_trader_id(tx['partner_trader_id']):
            return False
        if not MarketBlock.is_valid_asset_pair(tx['assets']):
            return False
        if not MarketBlock.is_valid_asset_pair(tx['transferred'], amount_positive=False):
            return False
        if not MarketBlock.has_required_types(required_types, tx):
            return False

        return True

    @staticmethod
    def is_valid_payment(payment):
        """
        Verify whether a dictionary that contains a payment, is valid.
        """
        required_fields = ['trader_id', 'transaction_number', 'transferred', 'payment_id', 'address_from',
                           'address_to', 'timestamp', 'success']
        if not MarketBlock.has_fields(required_fields, payment):
            return False
        if len(payment) != len(required_fields):
            return False

        required_types = [('trader_id', str), ('transaction_number', int), ('transferred', dict), ('payment_id', str),
                          ('address_from', str), ('address_to', str), ('timestamp', float), ('success', bool)]
        if not MarketBlock.is_valid_trader_id(payment['trader_id']):
            return False
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
