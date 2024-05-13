from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Callable, Iterator, List, Set

from pony import orm
from pony.orm import raw_sql
from pony.orm.core import Database, Entity, Query, select
from pony.utils import between

from tribler.core.database.layers.layer import EntityImpl, Layer
from tribler.core.knowledge.payload import StatementOperation

CLOCK_START_VALUE = 0

PUBLIC_KEY_FOR_AUTO_GENERATED_OPERATIONS = b"auto_generated"

SHOW_THRESHOLD = 1  # how many operation needed for showing a knowledge graph statement in the UI
HIDE_THRESHOLD = -2  # how many operation needed for hiding a knowledge graph statement in the UI

if TYPE_CHECKING:
    import dataclasses

    from tribler.core.database.layers.health import TorrentHealth, Tracker


    @dataclasses.dataclass
    class Peer(EntityImpl):
        """
        Database type for a peer.
        """

        id: int
        public_key: bytes
        added_at: datetime.datetime | None
        operations: set[StatementOp]

        def __init__(self, public_key: bytes) -> None: ...  # noqa: D107

        @staticmethod
        def get(public_key: bytes) -> Peer | None: ...  # noqa: D102

        @staticmethod
        def get_for_update(public_key: bytes) -> Peer | None: ...  # noqa: D102


    @dataclasses.dataclass
    class Statement(EntityImpl):
        """
        Database type for a statement.
        """

        id: int
        subject: Resource
        object: Resource
        operations: set[StatementOp]
        added_count: int
        removed_count: int
        local_operation: int | None

        def __init__(self, subject: Resource, object: Resource) -> None: ...  # noqa: D107, A002

        @staticmethod
        def get(subject: Resource, object: Resource) -> Statement | None: ...  # noqa: D102, A002

        @staticmethod
        def get_for_update(subject: Resource, object: Resource) -> Statement | None: ...  # noqa: D102, A002


    class IterResource(type):  # noqa: D101

        def __iter__(cls) -> Iterator[Resource]: ...  # noqa: D105


    @dataclasses.dataclass
    class Resource(EntityImpl, metaclass=IterResource):
        """
        Database type for a resources.
        """

        id: int
        name: str
        type: int
        subject_statements: set[Statement]
        object_statements: set[Statement]
        torrent_healths: set[TorrentHealth]
        trackers: set[Tracker]

        def __init__(self, name: str, type: int) -> None: ...  # noqa: D107, A002

        @staticmethod
        def get(name: str, type: int) -> Resource | None: ...  # noqa: D102, A002

        @staticmethod
        def get_for_update(name: str, type: int) -> Resource | None: ...  # noqa: D102, A002


    @dataclasses.dataclass
    class StatementOp(EntityImpl):
        """
        Database type for a statement operation.
        """

        id: int
        statement: Statement
        peer: Peer
        operation: int
        clock: int
        signature: bytes
        updated_at: datetime.datetime
        auto_generated: bool

        def __init__(self, statement: Statement, peer: Peer, operation: int, clock: int,  # noqa: D107, PLR0913
                     signature: bytes, auto_generated: bool) -> None: ...

        @staticmethod
        def get(statement: Statement, peer: Peer) -> StatementOp | None: ...  # noqa: D102

        @staticmethod
        def get_for_update(statement: Statement, peer: Peer) -> StatementOp | None: ...  # noqa: D102


class Operation(IntEnum):
    """
    Available types of statement operations.
    """

    ADD = 1  # +1 operation
    REMOVE = 2  # -1 operation


class ResourceType(IntEnum):
    """
    Description of available resources within the Knowledge Graph.
    These types are also using as a predicate for the statements.

    Based on https://en.wikipedia.org/wiki/Dublin_Core
    """

    CONTRIBUTOR = 1
    COVERAGE = 2
    CREATOR = 3
    DATE = 4
    DESCRIPTION = 5
    FORMAT = 6
    IDENTIFIER = 7
    LANGUAGE = 8
    PUBLISHER = 9
    RELATION = 10
    RIGHTS = 11
    SOURCE = 12
    SUBJECT = 13
    TITLE = 14
    TYPE = 15

    # this is a section for extra types
    TAG = 101
    TORRENT = 102
    CONTENT_ITEM = 103


@dataclass
class SimpleStatement:
    """
    A statement that reflects some (typed) attribute ``object`` of a given (typed) ``subject``.
    """

    subject_type: int
    subject: str
    predicate: int
    object: str


class KnowledgeDataAccessLayer(Layer):
    """
    A database layer for knowledge.
    """

    def __init__(self, instance: orm.Database) -> None:
        """
        Create a new knowledge database layer.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.instance = instance
        self.Peer, self.Statement, self.Resource, self.StatementOp = self.define_binding(self.instance)

    @staticmethod
    def define_binding(db: Database) -> tuple[type[Peer], type[Statement], type[Resource], type[StatementOp]]:
        """
        Create the bindings for this layer.
        """
        class Peer(db.Entity):
            id = orm.PrimaryKey(int, auto=True)
            public_key = orm.Required(bytes, unique=True)
            added_at = orm.Optional(datetime.datetime, default=datetime.datetime.utcnow)
            operations = orm.Set(lambda: StatementOp)

        class Statement(db.Entity):
            id = orm.PrimaryKey(int, auto=True)

            subject = orm.Required(lambda: Resource)
            object = orm.Required(lambda: Resource, index=True)

            operations = orm.Set(lambda: StatementOp)

            added_count = orm.Required(int, default=0)
            removed_count = orm.Required(int, default=0)

            local_operation = orm.Optional(int)  # in case user don't (or do) want to see it locally

            orm.composite_key(subject, object)

            @property
            def score(self) -> int:
                return self.added_count - self.removed_count

            def update_counter(self, operation: Operation, increment: int = 1, is_local_peer: bool = False) -> None:
                """
                Update Statement's counter.

                :param operation: Resource operation.
                :param increment:
                :param is_local_peer: The flag indicates whether do we perform operations from a local user.
                """
                if is_local_peer:
                    self.local_operation = operation
                if operation == Operation.ADD:
                    self.added_count += increment
                if operation == Operation.REMOVE:
                    self.removed_count += increment

        class Resource(db.Entity):
            id = orm.PrimaryKey(int, auto=True)
            name = orm.Required(str)
            type = orm.Required(int)  # ResourceType enum

            subject_statements = orm.Set(lambda: Statement, reverse="subject")
            object_statements = orm.Set(lambda: Statement, reverse="object")
            torrent_healths = orm.Set(lambda: db.TorrentHealth, reverse="torrent")
            trackers = orm.Set(lambda: db.Tracker, reverse="torrents")

            orm.composite_key(name, type)

        class StatementOp(db.Entity):
            id = orm.PrimaryKey(int, auto=True)

            statement = orm.Required(lambda: Statement)
            peer = orm.Required(lambda: Peer)

            operation = orm.Required(int)
            clock = orm.Required(int)
            signature = orm.Required(bytes)
            updated_at = orm.Required(datetime.datetime, default=datetime.datetime.utcnow)
            auto_generated = orm.Required(bool, default=False)

            orm.composite_key(statement, peer)

        return Peer, Statement, Resource, StatementOp

    def _get_resources(self, resource_type: ResourceType | None, name: str | None, case_sensitive: bool) -> Query:
        """
        Get resources.

        :param resource_type: type of resources
        :param name: name of resources
        :param case_sensitive: if True, then Resources are selected in a case-sensitive manner.
        :returns: a Query object for requested resources
        """
        results = self.Resource.select()
        if name:
            results = results.filter(
                (lambda r: r.name == name) if case_sensitive else (lambda r: r.name.lower() == name.lower())
            )
        if resource_type:
            results = results.filter(lambda r: r.type == resource_type.value)
        return results

    def get_statements(self, source_type: ResourceType | None, source_name: str | None,  # noqa: PLR0913
                       statements_getter: Callable[[Entity], Entity],
                       target_condition: Callable[[Statement], bool], condition: Callable[[Statement], bool],
                       case_sensitive: bool, ) -> Iterator[Statement]:
        """
        Get entities that satisfies the given condition.
        """
        for resource in self._get_resources(source_type, source_name, case_sensitive):
            results = orm.select(_ for _ in statements_getter(resource)
                                 .select(condition)
                                 .filter(target_condition)
                                 .order_by(lambda s: orm.desc(s.score)))

            yield from list(results)

    def add_operation(self, operation: StatementOperation, signature: bytes, is_local_peer: bool = False,
                      is_auto_generated: bool = False, counter_increment: int = 1) -> bool:
        """
        Add the operation that will be applied to a statement.

        :param operation: the class describes the adding operation
        :param signature: the signature of the operation
        :param is_local_peer: local operations processes differently than remote operations.
        :param is_auto_generated: the indicator of whether this resource was generated automatically or not
        :param counter_increment: the counter or "numbers" of adding operations
        :returns: True if the operation has been added/updated, False otherwise.
        """
        self.logger.debug('Add operation. %s "%s" %s',
                          str(operation.subject), str(operation.predicate), str(operation.object))
        peer = self.get_or_create(self.Peer, public_key=operation.creator_public_key)
        subject = self.get_or_create(self.Resource, name=operation.subject, type=operation.subject_type)
        obj = self.get_or_create(self.Resource, name=operation.object, type=operation.predicate)
        statement = self.get_or_create(self.Statement, subject=subject, object=obj)
        op = self.StatementOp.get_for_update(statement=statement, peer=peer)

        if not op:  # then insert
            self.StatementOp(statement=statement, peer=peer, operation=operation.operation,
                             clock=operation.clock, signature=signature, auto_generated=is_auto_generated)
            statement.update_counter(operation.operation, increment=counter_increment, is_local_peer=is_local_peer)
            return True

        # if it is a message from the past, then return
        if operation.clock <= op.clock:
            return False

        # To prevent endless incrementing of the operation, we apply the following logic:

        # 1. Decrement previous operation
        statement.update_counter(op.operation, increment=-counter_increment, is_local_peer=is_local_peer)
        # 2. Increment new operation
        statement.update_counter(operation.operation, increment=counter_increment, is_local_peer=is_local_peer)

        # 3. Update the operation entity
        op.set(operation=operation.operation, clock=operation.clock, signature=signature,
               updated_at=datetime.datetime.utcnow(), auto_generated=is_auto_generated)  # noqa: DTZ003
        return True

    def add_auto_generated_operation(self, subject_type: ResourceType, subject: str, predicate: ResourceType,
                                     obj: str) -> bool:
        """
        Add an autogenerated operation.

        The difference between "normal" and "autogenerated" operation is that the  autogenerated operation will be added
        with the flag `is_auto_generated=True` and with the `PUBLIC_KEY_FOR_AUTO_GENERATED_TAGS` public key.

        :param subject_type: a type of adding subject. See: ResourceType enum.
        :param subject: a string that represents a subject of adding operation.
        :param predicate: the enum that represents a predicate of adding operation.
        :param obj: a string that represents an object of adding operation.
        """
        operation = StatementOperation(
            subject_type=subject_type,
            subject=subject,
            predicate=predicate,
            object=obj,
            operation=Operation.ADD,
            clock=CLOCK_START_VALUE,
            creator_public_key=PUBLIC_KEY_FOR_AUTO_GENERATED_OPERATIONS,
        )

        return self.add_operation(operation, signature=b"", is_local_peer=False, is_auto_generated=True,
                                  counter_increment=SHOW_THRESHOLD)

    @staticmethod
    def _show_condition(s: Statement) -> bool:
        """
        This function determines show condition for the statement.
        """
        return s.local_operation == Operation.ADD.value or not s.local_operation and s.score >= SHOW_THRESHOLD

    def get_objects(self, subject_type: ResourceType | None = None, subject: str | None = "",
                    predicate: ResourceType | None = None, case_sensitive: bool = True,
                    condition: Callable[[Statement], bool] | None = None) -> List[str]:
        """
        Get objects that satisfy the given subject and predicate.

        To understand the order of parameters, keep in ming the following generic construction:
        (<subject_type>, <subject>, <predicate>, <object>).

        So in the case of retrieving objects this construction becomes
        (<subject_type>, <subject>, <predicate>, ?).

        :param subject_type: a type of the subject.
        :param subject: a string that represents the subject.
        :param predicate: the enum that represents a predicate of querying operations.
        :param case_sensitive: if True, then Resources are selected in a case-sensitive manner.
        :returns: a list of the strings representing the objects.
        """
        self.logger.debug("Get subjects for %s with %s", str(subject), str(predicate))

        statements = self.get_statements(
            source_type=subject_type,
            source_name=subject,
            statements_getter=lambda r: r.subject_statements,
            target_condition=(lambda s: s.object.type == predicate.value) if predicate else (lambda _: True),
            condition=condition or self._show_condition,
            case_sensitive=case_sensitive,
        )
        return [s.object.name for s in statements]

    def get_subjects(self, subject_type: ResourceType | None = None, predicate: ResourceType | None = None,
                     obj: str | None = "", case_sensitive: bool = True) -> List[str]:
        """
        Get subjects that satisfy the given object and predicate.

        To understand the order of parameters, keep in mind the following generic construction:

        (<subject_type>, <subject>, <predicate>, <object>).

        So in the case of retrieving subjects this construction becomes
        (<subject_type>, ?, <predicate>, <object>).

        :param subject_type: a type of the subject.
        :param obj: a string that represents the object.
        :param predicate: the enum that represents a predicate of querying operations.
        :param case_sensitive: if True, then Resources are selected in a case-sensitive manner.
        :returns: a list of the strings representing the subjects.
        """
        self.logger.debug("Get linked back resources for %s with %s", str(obj), str(predicate))

        statements = self.get_statements(
            source_type=predicate,
            source_name=obj,
            statements_getter=lambda r: r.object_statements,
            target_condition=(lambda s: s.subject.type == subject_type.value) if subject_type else (lambda _: True),
            condition=self._show_condition,
            case_sensitive=case_sensitive,
        )

        return [s.subject.name for s in statements]

    def get_simple_statements(self, subject_type: ResourceType | None = None, subject: str | None = "",
                              case_sensitive: bool = True) -> list[SimpleStatement]:
        """
        Get simple statements for the given subject search.
        """
        statements = self.get_statements(
            source_type=subject_type,
            source_name=subject,
            statements_getter=lambda r: r.subject_statements,
            target_condition=lambda _: True,
            condition=self._show_condition,
            case_sensitive=case_sensitive,
        )

        return [SimpleStatement(subject_type=s.subject.type, subject=s.subject.name, predicate=s.object.type,
                                object=s.object.name)
                for s in statements]

    def get_suggestions(self, subject_type: ResourceType | None = None, subject: str | None = "",
                        predicate: ResourceType | None = None, case_sensitive: bool = True) -> List[str]:
        """
        Get all suggestions for a particular subject.

        :param subject_type: a type of the subject.
        :param subject: a string that represents the subject.
        :param predicate: the enum that represents a predicate of querying operations.
        :param case_sensitive: if True, then Resources are selected in a case-sensitive manner.
        :returns: a list of the strings representing the objects.
        """
        self.logger.debug("Getting suggestions for %s with %s", str(subject), str(predicate))

        return self.get_objects(
            subject_type=subject_type,
            subject=subject,
            predicate=predicate,
            case_sensitive=case_sensitive,
            condition=lambda s: not s.local_operation and between(s.score, HIDE_THRESHOLD + 1, SHOW_THRESHOLD - 1)
        )

    def get_subjects_intersection(self, objects: Set[str],
                                  predicate: ResourceType | None,
                                  subjects_type: ResourceType = ResourceType.TORRENT,
                                  case_sensitive: bool = True) -> Set[str]:
        """
        Get all subjects that have a certain predicate.
        """
        if not objects:
            return set()

        if case_sensitive:
            name_condition = '"obj"."name" = $obj_name'
        else:
            name_condition = 'py_lower("obj"."name") = py_lower($obj_name)'
        query = select(r.name for r in self.Resource if r.type == subjects_type.value)
        for obj_name in objects:
            query = query.filter(raw_sql("""
    r.id IN (
        SELECT "s"."subject"
        FROM "Statement" "s"
        WHERE (
            "s"."local_operation" = $(Operation.ADD.value)
        OR
            ("s"."local_operation" = 0 OR "s"."local_operation" IS NULL)
            AND ("s"."added_count" - "s"."removed_count") >= $SHOW_THRESHOLD
        ) AND "s"."object" IN (
            SELECT "obj"."id" FROM "Resource" "obj"
            WHERE "obj"."type" = $(predicate.value) AND $name_condition
        )
    )"""), globals={"obj_name": obj_name, "name_condition": name_condition, "SHOW_THRESHOLD": SHOW_THRESHOLD})
        return set(query)

    def get_clock(self, operation: StatementOperation) -> int:
        """
        Get the clock (int) of operation.
        """
        peer = self.Peer.get(public_key=operation.creator_public_key)
        subject = self.Resource.get(name=operation.subject, type=operation.subject_type)
        obj = self.Resource.get(name=operation.object, type=operation.predicate)
        if not subject or not obj or not peer:
            return CLOCK_START_VALUE

        statement = self.Statement.get(subject=subject, object=obj)
        if not statement:
            return CLOCK_START_VALUE

        op = self.StatementOp.get(statement=statement, peer=peer)
        return op.clock if op else CLOCK_START_VALUE

    def get_operations_for_gossip(self, count: int = 10) -> set[Entity]:
        """
        Get random operations from the DB.

        :param count: a limit for a resulting query
        """
        return self._get_random_operations_by_condition(
            condition=lambda so: not so.auto_generated,
            count=count
        )

    def _get_random_operations_by_condition(self, condition: Callable[[Entity], bool], count: int = 5,
                                            attempts: int = 100) -> set[Entity]:
        """
        Get `count` random operations that satisfy the given condition.

        This method were introduce as an fast alternative for native Pony `random` method.

        :param condition: the condition by which the entities will be queried.
        :param count: the amount of entities to return.
        :param attempts: maximum attempt count for requesting the DB.
        :returns: a set of random operations
        """
        operations: set[Entity] = set()
        for _ in range(attempts):
            if len(operations) == count:
                return operations

            random_operations_list = self.StatementOp.select_random(1)
            if random_operations_list:
                operation = random_operations_list[0]
                if condition(operation):
                    operations.add(operation)

        return operations
