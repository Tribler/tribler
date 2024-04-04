from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from ipv8.test.base import TestBase

from tribler.core.database.layers.health import ResourceType
from tribler.core.database.layers.knowledge import KnowledgeDataAccessLayer, Operation
from tribler.core.knowledge.payload import StatementOperation

if TYPE_CHECKING:
    from typing_extensions import Self


class MockResource:
    """
    A mocked Resource that stored is call kwargs.
    """

    def __init__(self, **kwargs) -> None:
        """
        Create a MockResouce and store its kwargs.
        """
        self.get_kwargs = kwargs

    @classmethod
    def get(cls: type[Self], **kwargs) -> type[Self]:
        """
        Fake a search using the given kwargs and return an instance of ourselves.
        """
        return cls(**kwargs)

    @classmethod
    def get_for_update(cls: type[Self], /, **kwargs) -> type[Self] | None:
        """
        Mimic fetching the resource from the database.
        """
        return cls(**kwargs)


class MockEntity(MockResource, SimpleNamespace):
    """
    Allow a db binding to write whatever they want to this class.
    """

    CREATED = []

    def __init__(self, **kwargs) -> None:
        """
        Create a new MockEntity and add it to the CREATED list.
        """
        super().__init__(**kwargs)
        self.CREATED.append(self)


class MockStatement(MockEntity):
    """
    A mocked Statement.
    """

    def update_counter(self, operation: Operation, increment: int = 1, is_local_peer: bool = False) -> None:
        """
        Fake a counter update and store the calling args.
        """
        self.update_counter_arg_op = operation
        self.update_counter_arg_increment = increment
        self.update_counter_arg_local_peer = is_local_peer


class MockStatementOp(MockEntity):
    """
    A mocked StatementOp.
    """

    clock = 0
    operation = Operation.ADD

    def set(self, **kwargs) -> None:
        """
        Fake a set and store the calling args.
        """
        self.set_kwargs = kwargs

    def __hash__(self) -> int:
        """
        We need a hash.
        """
        return 0

    @classmethod
    def select_random(cls: type[Self], count: int) -> list[Self]:
        """
        Fake random selection.
        """
        out = []
        for i in range(count):
            statement_op = MockStatementOp()
            statement_op.id = i
            statement_op.statement = None
            statement_op.peer = None
            statement_op.operation = Operation.ADD.value
            statement_op.clock = 0
            statement_op.signature = b""
            statement_op.updated_at = 0
            statement_op.auto_generated = False
            out.append(statement_op)
        return out


class MockStatementOpMissing(MockStatement):
    """
    A mocked StatementOp that does not exist.
    """

    @classmethod
    def get_for_update(cls: type[Self], /, **kwargs) -> type[Self] | None:
        """
        It did not exist before.
        """
        del kwargs
        return None


class MockDatabase:
    """
    Mock the bindings that others will inherit from.
    """

    Entity = MockEntity
    Resource = MockResource


class TestKnowledgeDataAccessLayer(TestBase):
    """
    Tests for the KnowledgeDataAccessLayer.
    """

    def setUp(self) -> None:
        """
        Mock all bindings.
        """
        super().setUp()
        self.kdal = KnowledgeDataAccessLayer(MockDatabase())
        self.kdal.Statement = MockStatement
        self.kdal.Statement.CREATED = []
        self.kdal.StatementOp = MockStatementOpMissing
        self.kdal.StatementOp.CREATED = []

    def get_created(self, entity_type: type[MockEntity]) -> list[MockEntity]:
        """
        Get all instances of a particular mock entity type that have been created.
        """
        return [entity for entity in entity_type.CREATED if isinstance(entity, entity_type)]

    def add_searchable_statement(self, subj: str = "\x01" * 20, obj: str = "test tag") -> None:
        """
        Inject a Statement that can be searched for.
        """
        self.kdal.add_auto_generated_operation(ResourceType.TORRENT, subj, ResourceType.TAG, obj)
        statement, = self.get_created(self.kdal.Statement)
        statement.subject_statements = self.kdal.Statement
        statement.object = SimpleNamespace()
        statement.object.name = statement.get_kwargs["object"].get_kwargs["name"]
        statement.object.type = statement.get_kwargs["object"].get_kwargs["type"]
        statement.subject = SimpleNamespace()
        statement.subject.name = statement.get_kwargs["subject"].get_kwargs["name"]
        statement.subject.type = statement.get_kwargs["subject"].get_kwargs["type"]
        self.kdal.get_statements = lambda **kwargs: [statement]

    def test_add_operation_update(self) -> None:
        """
        Test if operations are correctly updated in the ORM.
        """
        statement_operation = StatementOperation(subject_type=ResourceType.TORRENT, subject=b"\x01" * 20,
                                                 predicate=ResourceType.TAG, object='test tag',
                                                 operation=Operation.ADD, clock=1, creator_public_key=b"\x02" * 64)
        self.kdal.StatementOp = MockStatementOp
        self.kdal.StatementOp.CREATED = []
        value = self.kdal.add_operation(statement_operation, b"\x00" * 32, True)

        statement, = self.get_created(self.kdal.Statement)
        statement_op, = self.get_created(self.kdal.StatementOp)

        self.assertTrue(value)
        self.assertEqual(b"\x01" * 20, statement.get_kwargs["subject"].get_kwargs["name"])
        self.assertEqual(ResourceType.TORRENT, statement.get_kwargs["subject"].get_kwargs["type"])
        self.assertEqual("test tag", statement.get_kwargs["object"].get_kwargs["name"])
        self.assertEqual(ResourceType.TAG, statement.get_kwargs["object"].get_kwargs["type"])
        self.assertEqual(Operation.ADD, statement.update_counter_arg_op)
        self.assertEqual(1, statement.update_counter_arg_increment)
        self.assertTrue(statement.update_counter_arg_local_peer)
        self.assertEqual(Operation.ADD, statement_op.set_kwargs["operation"])
        self.assertEqual(1, statement_op.set_kwargs["clock"])
        self.assertEqual(b"\x00" * 32, statement_op.set_kwargs["signature"])
        self.assertFalse(statement_op.set_kwargs["auto_generated"])

    def test_add_operation_past(self) -> None:
        """
        Test if operations are not added to the ORM if their clock is in the past.
        """
        statement_operation = StatementOperation(subject_type=ResourceType.TORRENT, subject=b"\x01" * 20,
                                                 predicate=ResourceType.TAG, object='test tag',
                                                 operation=Operation.ADD, clock=-1, creator_public_key=b"\x02" * 64)
        self.kdal.StatementOp = MockStatementOp
        self.kdal.StatementOp.CREATED = []
        value = self.kdal.add_operation(statement_operation, b"\x00" * 32, True)

        self.assertFalse(value)

    def test_add_operation_missing(self) -> None:
        """
        Test if operations are correctly added to the ORM is the statement op did not exist before.
        """
        statement_operation = StatementOperation(subject_type=ResourceType.TORRENT, subject=b"\x01" * 20,
                                                 predicate=ResourceType.TAG, object='test tag',
                                                 operation=Operation.ADD, clock=1, creator_public_key=b"\x02" * 64)
        value = self.kdal.add_operation(statement_operation, b"\x00" * 32, True)

        statement, = self.get_created(self.kdal.Statement)

        self.assertTrue(value)
        self.assertEqual(b"\x01" * 20, statement.get_kwargs["subject"].get_kwargs["name"])
        self.assertEqual(ResourceType.TORRENT, statement.get_kwargs["subject"].get_kwargs["type"])
        self.assertEqual("test tag", statement.get_kwargs["object"].get_kwargs["name"])
        self.assertEqual(ResourceType.TAG, statement.get_kwargs["object"].get_kwargs["type"])
        self.assertEqual(Operation.ADD, statement.update_counter_arg_op)
        self.assertEqual(1, statement.update_counter_arg_increment)
        self.assertTrue(statement.update_counter_arg_local_peer)

    def test_add_auto_generated_operation(self) -> None:
        """
        Test if auto generated operations are correctly added to the ORM.
        """
        value = self.kdal.add_auto_generated_operation(ResourceType.TORRENT, "\x01" * 20, ResourceType.TAG, 'test tag')

        statement, = self.get_created(self.kdal.Statement)

        self.assertTrue(value)
        self.assertEqual("\x01" * 20, statement.get_kwargs["subject"].get_kwargs["name"])
        self.assertEqual(ResourceType.TORRENT, statement.get_kwargs["subject"].get_kwargs["type"])
        self.assertEqual("test tag", statement.get_kwargs["object"].get_kwargs["name"])
        self.assertEqual(ResourceType.TAG, statement.get_kwargs["object"].get_kwargs["type"])
        self.assertEqual(Operation.ADD, statement.update_counter_arg_op)
        self.assertEqual(1, statement.update_counter_arg_increment)
        self.assertFalse(statement.update_counter_arg_local_peer)

    def test_get_objects(self) -> None:
        """
        Test if objects are correctly retrieved from the ORM.
        """
        self.add_searchable_statement(obj="test tag")

        value = self.kdal.get_objects()

        self.assertEqual(["test tag"], value)

    def test_get_subjects(self) -> None:
        """
        Test if subjects are correctly retrieved from the ORM.
        """
        self.add_searchable_statement(subj="\x01" * 20)

        value = self.kdal.get_subjects()

        self.assertEqual(["\x01" * 20], value)

    def test_get_suggestions(self) -> None:
        """
        Test if suggestions are correctly retrieved from the ORM.
        """
        self.add_searchable_statement(subj="\x01" * 20, obj="test tag")

        value = self.kdal.get_suggestions(subject="\x01" * 20)

        self.assertEqual(["test tag"], value)

    def test_get_operations_for_gossip(self) -> None:
        """
        Test if.
        """
        self.kdal.StatementOp = MockStatementOp

        selected, = self.kdal.get_operations_for_gossip(1)

        self.assertFalse(selected.auto_generated)
        self.assertEqual(0, selected.clock)
        self.assertEqual(0, selected.id)
        self.assertEqual(Operation.ADD.value, selected.operation)
