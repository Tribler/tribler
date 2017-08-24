import os

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.database import MarketDB
from Tribler.community.market.tradechain.block import TradeChainBlock


class TestReputationBase(AbstractServer):
    """
    This class contains various utility methods to add transactions to the TradeChain.
    """

    def setUp(self, annotate=True):
        super(TestReputationBase, self).setUp(annotate=annotate)

        os.mkdir(os.path.join(self.session_base_dir, 'sqlite'))
        self.market_db = MarketDB(self.session_base_dir, 'market')

    def insert_transaction(self, pubkey1, pubkey2, asset1_type, asset1_amount, asset2_type, asset2_amount):
        latest_block = self.market_db.get_latest(pubkey1)

        block = TradeChainBlock()
        block.public_key = pubkey1
        if latest_block:
            block.sequence_number = latest_block.sequence_number + 1

        block.link_public_key = pubkey2

        transaction = {"asset1_type": asset1_type, "asset1_amount": asset1_amount,
                       "asset2_type": asset2_type, "asset2_amount": asset2_amount}
        block.transaction = transaction

        self.market_db.add_block(block)
