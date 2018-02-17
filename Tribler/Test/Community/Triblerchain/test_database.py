import os

from twisted.internet.defer import inlineCallbacks

from Tribler.community.triblerchain.database import TriblerChainDB
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.pyipv8.ipv8.attestation.trustchain.block import TrustChainBlock
from Tribler.pyipv8.ipv8.attestation.trustchain.database import DATABASE_DIRECTORY
from Tribler.Test.test_as_server import AbstractServer


class TestDatabase(AbstractServer):
    """
    Tests the Database for TriblerChain database.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestDatabase, self).setUp(annotate=annotate)
        path = os.path.join(self.getStateDir(), DATABASE_DIRECTORY)
        if not os.path.exists(path):
            os.makedirs(path)
        self.db = TriblerChainDB(self.getStateDir(), u'triblerchain')
        self.block1 = TrustChainBlock()
        self.block1.transaction = {'up': 42, 'down': 42}
        self.block1.public_key = 'a'
        self.block2 = TrustChainBlock()
        self.block2.transaction = {'up': 42, 'down': 42}
        self.block2.public_key = 'b'

    @blocking_call_on_reactor_thread
    def test_get_num_interactors(self):
        """
        Test whether the right number of interactors is returned
        """
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        self.assertEqual((1, 1), self.db.get_num_unique_interactors(self.block1.public_key))
