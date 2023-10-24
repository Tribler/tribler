import datetime
from unittest.mock import MagicMock, Mock

from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from pony.orm import db_session

from tribler.core.components.database.db.layers.knowledge_data_access_layer import Operation, ResourceType
from tribler.core.components.ipv8.adapters_tests import TriblerMockIPv8, TriblerTestBase
from tribler.core.components.knowledge.community.knowledge_community import KnowledgeCommunity
from tribler.core.components.knowledge.community.knowledge_payload import StatementOperation
from tribler.core.components.database.db.tribler_database import TriblerDatabase

REQUEST_INTERVAL_FOR_RANDOM_OPERATIONS = 0.1  # in seconds


class TestKnowledgeCommunity(TriblerTestBase):
    def setUp(self):
        super().setUp()
        self.initialize(KnowledgeCommunity, 2)

    async def tearDown(self):
        await super().tearDown()

    def create_node(self, *args, **kwargs):
        return TriblerMockIPv8("curve25519", KnowledgeCommunity, db=TriblerDatabase(), key=LibNaCLSK(),
                               request_interval=REQUEST_INTERVAL_FOR_RANDOM_OPERATIONS)

    def create_operation(self, subject='1' * 20, obj=''):
        community = self.overlay(0)
        operation = StatementOperation(subject_type=ResourceType.TORRENT, subject=subject, predicate=ResourceType.TAG,
                                       object=obj, operation=Operation.ADD, clock=0,
                                       creator_public_key=community.key.pub().key_to_bin())
        operation.clock = community.db.knowledge.get_clock(operation) + 1
        return operation

    @db_session
    def fill_db(self):
        # create 10 operations:
        # first 5 of them are correct
        # next 5 of them are incorrect
        # a single operation should be cyrillic
        community = self.overlay(0)
        for i in range(10):
            message = self.create_operation(obj=f'{i}' * 3)
            signature = community.sign(message)
            # 5 of them are signed incorrectly
            if i >= 5:
                signature = b'1' * 64

            community.db.knowledge.add_operation(message, signature)

        # a single entity should be cyrillic
        cyrillic_message = self.create_operation(subject='Контент', obj='Тэг')
        community.db.knowledge.add_operation(cyrillic_message, community.sign(cyrillic_message))

        # put them into the past
        for op in community.db.instance.StatementOp.select():
            op.set(updated_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=2))

    async def test_gossip(self):
        # Test default gossip.
        # Only 6 correct messages should be propagated
        self.fill_db()
        await self.introduce_nodes()
        await self.deliver_messages(timeout=REQUEST_INTERVAL_FOR_RANDOM_OPERATIONS * 2)
        with db_session:
            assert self.overlay(0).db.instance.StatementOp.select().count() == 11
            assert self.overlay(1).db.instance.StatementOp.select().count() == 6

    async def test_on_request_eat_exceptions(self):
        # Tests that except blocks in on_request function works as expected
        # ValueError should be eaten silently
        self.fill_db()
        # let's "break" the function that will be called on on_request()
        self.overlay(0).db.knowledge.get_operations_for_gossip = Mock(return_value=[MagicMock()])
        # occurred exception should be ate by community silently
        await self.introduce_nodes()
        await self.deliver_messages(timeout=REQUEST_INTERVAL_FOR_RANDOM_OPERATIONS * 2)
        self.overlay(0).db.knowledge.get_operations_for_gossip.assert_called()

    async def test_no_peers(self):
        # Test that no error occurs in the community, in case there is no peers
        self.overlay(0).get_peers = Mock(return_value=[])
        self.fill_db()
        await self.introduce_nodes()
        await self.deliver_messages(timeout=REQUEST_INTERVAL_FOR_RANDOM_OPERATIONS * 2)
        self.overlay(0).get_peers.assert_called()
