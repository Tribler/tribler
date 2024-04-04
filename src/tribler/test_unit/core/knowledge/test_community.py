from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from random import sample
from typing import TYPE_CHECKING
from unittest.mock import Mock

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.test.base import TestBase
from pony.orm import db_session

from tribler.core.database.layers.knowledge import Operation, ResourceType
from tribler.core.knowledge.community import (
    KnowledgeCommunity,
    KnowledgeCommunitySettings,
    is_valid_resource,
    validate_operation,
    validate_resource,
    validate_resource_type,
)
from tribler.core.knowledge.payload import StatementOperation, StatementOperationMessage

if TYPE_CHECKING:
    from ipv8.community import CommunitySettings
    from ipv8.test.mocking.ipv8 import MockIPv8


@dataclasses.dataclass
class Peer:
    """
    A mocked Peer class.
    """

    public_key: bytes
    added_at: datetime = dataclasses.field(default=datetime.now(tz=timezone.utc))
    operations: set[StatementOp] = dataclasses.field(default_factory=set)


@dataclasses.dataclass
class Resource:
    """
    A mocked Resource class.
    """

    name: str
    type: int

    subject_statements: set[Statement] = dataclasses.field(default_factory=set)
    object_statements: set[Statement] = dataclasses.field(default_factory=set)
    torrent_healths: set = dataclasses.field(default_factory=set)
    trackers: set = dataclasses.field(default_factory=set)


@dataclasses.dataclass
class Statement:
    """
    A mocked Statement class.
    """

    subject: Resource
    object: Resource
    operations: set[StatementOp]
    added_count: int = 0
    removed_count: int = 0
    local_operation: int = 0


@dataclasses.dataclass
class StatementOp:
    """
    A mocked StatementOp class.
    """

    statement: Statement
    peer: Peer
    operation: int
    clock: int
    signature: bytes
    updated_at: datetime = dataclasses.field(default=datetime.now(tz=timezone.utc))
    auto_generated: bool = False


class TestKnowledgeCommunity(TestBase[KnowledgeCommunity]):
    """
    Tests for the KnowledgeCommunity.
    """

    def setUp(self) -> None:
        """
        Create two nodes.
        """
        super().setUp()
        self.initialize(KnowledgeCommunity, 2,
                        KnowledgeCommunitySettings(request_interval=0.1))
        self.operations = []
        self.signatures = []
        self.statement_ops = []

    def create_node(self, settings: CommunitySettings | None = None, create_dht: bool = False,
                    enable_statistics: bool = False) -> MockIPv8:
        """
        Create a mocked database and new key for each node.
        """
        settings.db = Mock()
        settings.key = default_eccrypto.generate_key("curve25519")
        out = super().create_node(settings, create_dht, enable_statistics)
        out.overlay.cancel_all_pending_tasks()
        return out

    def create_operation(self, subject: str = "1" * 20, obj: str = "",
                         sign_correctly: bool = True) -> StatementOperation:
        """
        Create an operation with the given subject and object.
        """
        operation = StatementOperation(subject_type=ResourceType.TORRENT, subject=subject, predicate=ResourceType.TAG,
                                       object=obj, operation=Operation.ADD, clock=len(self.operations) + 1,
                                       creator_public_key=self.overlay(0).key.pub().key_to_bin())
        self.operations.append((operation, self.overlay(0).sign(operation) if sign_correctly else b'1' * 64))
        self.statement_ops.append(StatementOp(
            statement=Statement(
                Resource(self.operations[-1][0].subject, self.operations[-1][0].subject_type),
                Resource(self.operations[-1][0].object, self.operations[-1][0].predicate),
                set()
            ),
            peer=Peer(self.overlay(0).key.pub().key_to_bin()),
            operation=self.operations[-1][0].operation,
            clock=self.operations[-1][0].clock,
            signature=self.operations[-1][1]
        ))
        return operation

    @db_session
    def fill_db(self) -> None:
        """
        Create 5 correct, of which one has unicode characters, and 5 incorrect operations.
        """
        for i in range(9):
            self.create_operation(obj=f'{i}' * 3, sign_correctly=i < 4)
        self.create_operation(subject='Контент', obj='Тэг', sign_correctly=True)
        self.overlay(0).db.knowledge.get_operations_for_gossip = lambda count: sample(self.statement_ops, count)

    async def test_gossip(self) -> None:
        """
        Test if the 5 correct messages are gossiped.
        """
        self.fill_db()

        with self.assertReceivedBy(1, [StatementOperationMessage] * 10) as received:
            self.overlay(1).request_operations()
            await self.deliver_messages()

        received_objects = {message.operation.object for message in received}
        self.assertEqual(10, len(received_objects))
        self.assertEqual(5, len(self.overlay(1).db.knowledge.add_operation.call_args_list))

    async def test_on_request_eat_exceptions(self) -> None:
        """
        Test faulty statement ops have their ValueError caught.
        """
        self.fill_db()
        self.statement_ops[0].statement.subject.name = ""  # Fails validate_resource(operation.subject)

        with self.assertReceivedBy(1, [StatementOperationMessage] * 9) as received:
            self.overlay(1).request_operations()
            await self.deliver_messages()

        received_objects = {message.operation.object for message in received}
        self.assertEqual(9, len(received_objects))
        self.assertEqual(4, len(self.overlay(1).db.knowledge.add_operation.call_args_list))

    async def test_no_peers(self) -> None:
        """
        Test if no error occurs in the community, in case there are no peers.
        """
        self.overlay(1).network.remove_peer(self.peer(0))
        self.fill_db()

        with self.assertReceivedBy(0, []), self.assertReceivedBy(1, []):
            self.overlay(1).request_operations()
            await self.deliver_messages()

    def test_valid_tag(self) -> None:
        """
        Test if a normal tag is valid.
        """
        tag = "Tar "

        validate_resource(tag)  # no exception

        self.assertTrue(is_valid_resource(tag))

    def test_invalid_tag_nothing(self) -> None:
        """
        Test if nothing is not a valid tag.
        """
        tag = ""

        self.assertFalse(is_valid_resource(tag))

        with self.assertRaises(ValueError):
            validate_resource(tag)

    def test_invalid_tag_short(self) -> None:
        """
        Test if a short tag is not valid.
        """
        tag = "t"

        self.assertFalse(is_valid_resource(tag))

        with self.assertRaises(ValueError):
            validate_resource(tag)

    def test_invalid_tag_long(self) -> None:
        """
        Test if a long tag is not valid.
        """
        tag = "t" * 51

        self.assertFalse(is_valid_resource(tag))

        with self.assertRaises(ValueError):
            validate_resource(tag)

    def test_correct_operation(self) -> None:
        """
        Test if a correct operation is valid.
        """
        for operation in Operation:
            validate_operation(operation)  # no exception
            validate_operation(operation.value)  # no exception

    def test_incorrect_operation(self) -> None:
        """
        Test if an incorrect operation raises a ValueError.
        """
        max_operation = max(Operation)

        with self.assertRaises(ValueError):
            validate_operation(max_operation.value + 1)

    def test_correct_relation(self) -> None:
        """
        Test if a correct relation is valid.
        """
        for relation in ResourceType:
            validate_resource_type(relation)  # no exception
            validate_resource_type(relation.value)  # no exception

    def test_incorrect_relation(self) -> None:
        """
        Test if an incorrect relation raises a ValueError.
        """
        max_relation = max(ResourceType)
        with self.assertRaises(ValueError):
            validate_operation(max_relation.value + 1)
