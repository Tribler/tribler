import os

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.database import MarketDB
from Tribler.community.market.reputation.temporal_pagerank_manager import TemporalPagerankReputationManager
from Tribler.community.market.tradechain.block import TradeChainBlock


class TestReputationBase(AbstractServer):
    """
    This class contains various utility methods to add transactions to the TradeChain.
    """

    def setUp(self, annotate=True):
        super(TestReputationBase, self).setUp(annotate=annotate)

        os.mkdir(os.path.join(self.session_base_dir, 'sqlite'))
        self.market_db = MarketDB(self.session_base_dir, 'market')

    def insert_transaction(self, pubkey1, pubkey2, quantity, price):
        transaction = {
            "tx": {
                "quantity_type": quantity.wallet_id,
                "quantity": float(quantity),
                "price_type": price.wallet_id,
                "price": float(price)
            },
            "type": "tx_done"
        }
        block = TradeChainBlock.create(transaction, self.market_db, pubkey1, link=None, link_pk=pubkey2)
        link_block = TradeChainBlock.create(transaction, self.market_db, pubkey2, link=block, link_pk=pubkey1)

        self.market_db.add_block(block)
        self.market_db.add_block(link_block)

    def compute_reputations(self):
        blocks = self.market_db.get_all_blocks()
        rep_manager = TemporalPagerankReputationManager(blocks)
        rep = rep_manager.compute(own_public_key='a')
        self.assertIsInstance(rep, dict)
        return rep
