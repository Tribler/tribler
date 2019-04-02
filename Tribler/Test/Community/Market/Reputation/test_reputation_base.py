import os

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.reputation.temporal_pagerank_manager import TemporalPagerankReputationManager
from Tribler.pyipv8.ipv8.attestation.trustchain.block import TrustChainBlock
from Tribler.pyipv8.ipv8.attestation.trustchain.database import TrustChainDB


class TestReputationBase(AbstractServer):
    """
    This class contains various utility methods to add transactions to the TrustChain.
    """

    def setUp(self):
        super(TestReputationBase, self).setUp()

        os.mkdir(os.path.join(self.session_base_dir, 'sqlite'))
        self.market_db = TrustChainDB(self.session_base_dir, 'market')

    def insert_transaction(self, pubkey1, pubkey2, assets_traded):
        transaction = {
            "tx": {
                "assets": assets_traded.to_dictionary(),
                "transferred": assets_traded.to_dictionary()
            },
        }
        block = TrustChainBlock.create(b'tx_done', transaction, self.market_db, pubkey1,
                                       link=None, link_pk=pubkey2)
        link_block = TrustChainBlock.create(b'tx_done', transaction, self.market_db, pubkey2,
                                            link=block, link_pk=pubkey1)

        self.market_db.add_block(block)
        self.market_db.add_block(link_block)

    def compute_reputations(self):
        blocks = self.market_db.get_all_blocks()
        rep_manager = TemporalPagerankReputationManager(blocks)
        rep = rep_manager.compute(own_public_key=b'a')
        self.assertIsInstance(rep, dict)
        return rep
