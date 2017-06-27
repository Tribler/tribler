from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.transaction import TransactionId, TransactionNumber
from Tribler.community.tradechain.block import TradeChainBlock
from Tribler.community.trustchain.community import TrustChainCommunity
from Tribler.community.tradechain.database import TradeChainDB


class TradeChainCommunity(TrustChainCommunity):
    """
    Community for storing transactions based on TrustChain tamper proof interaction history.
    """
    BLOCK_CLASS = TradeChainBlock
    DB_CLASS = TradeChainDB
    DB_NAME = 'tradechain'

    def __init__(self, *args, **kwargs):
        super(TradeChainCommunity, self).__init__(*args, **kwargs)
        self.market_community = None

    @classmethod
    def get_master_members(cls, dispersy):
        master_key = "3081a7301006072a8648ce3d020106052b810400270381920004016ca22eca84f88c8cd2df03f95bb9f5534081ac" \
                     "83ee306fedb2d36c44e766afecc62732f45e153cf419bd4ab54744a692b5d459cbd12b5cc1a90b58f87a8c3d8d57" \
                     "0c9c0d6094a506f5432b4c8b640d2f2d72fef14f41781924248d9ce91a616741571424b73a430ed2b416bcdb69cd" \
                     "d4766b459ef804c43aa6cbfdc1e1a17411a3d9fd1e2774ee1b744e26cf2dee87"
        return [dispersy.get_member(public_key=master_key.decode("HEX"))]

    def initialize(self, market_community=None):
        super(TradeChainCommunity, self).initialize()
        self.market_community = market_community

    def should_sign(self, message):
        """
        Only sign the block if we have a (completed) transaction in the market community with the specific txid.
        """
        if not self.market_community:  # Don't sign anything if we don't have a market community.
            return False

        trader_id_str, transaction_number_str = message.payload.block.transaction["txid"].split(".")
        txid = TransactionId(TraderId(trader_id_str), TransactionNumber(int(transaction_number_str)))
        transaction = self.market_community.transaction_manager.find_by_id(txid)
        return bool(transaction)
