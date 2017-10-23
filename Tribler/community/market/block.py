from Tribler.community.trustchain.block import TrustChainBlock, ValidationResult, GENESIS_SEQ, GENESIS_HASH, EMPTY_SIG


class MarketBlock(TrustChainBlock):
    """
    Container for TriblerChain block information
    """

    def __init__(self, data=None):
        super(MarketBlock, self).__init__(data)
        if len(self.transaction) != 1:
            self.transaction = [dict()]

    @property
    def transaction_dict(self):
        return self.transaction[0]

    @transaction_dict.setter
    def transaction_dict(self, value):
        assert isinstance(value, dict), "Must assign dictionary!"
        self.transaction[0] = value

    @classmethod
    def create(cls, transaction, database, public_key, link=None, link_pk=None):
        return super(MarketBlock, cls).create([transaction], database, public_key, link, link_pk)