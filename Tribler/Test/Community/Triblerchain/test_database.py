import os

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Community.Trustchain.test_trustchain_utilities import TrustChainTestCase, TestBlock
from Tribler.community.triblerchain.database import TriblerChainDB
from Tribler.community.trustchain.database import DATABASE_DIRECTORY
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestDatabase(TrustChainTestCase):
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
        self.block1 = TestBlock(transaction={'up': 42, 'down': 42})
        self.block2 = TestBlock(transaction={'up': 42, 'down': 42})

    @blocking_call_on_reactor_thread
    def test_get_num_interactors(self):
        """
        Test whether the right number of interactors is returned
        """
        self.block2 = TestBlock(previous=self.block1, transaction={'up': 42, 'down': 42})
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        self.assertEqual((2, 2), self.db.get_num_unique_interactors(self.block1.public_key))
