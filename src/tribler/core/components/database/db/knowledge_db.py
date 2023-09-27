import datetime
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Iterator, List, Optional, Set

from pony import orm
from pony.orm import raw_sql
from pony.orm.core import Entity, Query, select
from pony.utils import between

from tribler.core.components.knowledge.community.knowledge_payload import StatementOperation
from tribler.core.utilities.pony_utils import TrackedDatabase, get_or_create

CLOCK_START_VALUE = 0

PUBLIC_KEY_FOR_AUTO_GENERATED_OPERATIONS = b'auto_generated'

SHOW_THRESHOLD = 1  # how many operation needed for showing a knowledge graph statement in the UI
HIDE_THRESHOLD = -2  # how many operation needed for hiding a knowledge graph statement in the UI


class Operation(IntEnum):
    """ Available types of statement operations."""
    ADD = 1  # +1 operation
    REMOVE = 2  # -1 operation


class ResourceType(IntEnum):
    """ Description of available resources within the Knowledge Graph.
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
    subject_type: ResourceType
    object: str
    predicate: ResourceType
    subject: str


class KnowledgeDatabase:
    def __init__(self, filename: Optional[str] = None, *, create_tables: bool = True, **generate_mapping_kwargs):
        self.instance = TrackedDatabase()
        self.define_binding(self.instance)
        self.instance.bind('sqlite', filename or ':memory:', create_db=True)
        generate_mapping_kwargs['create_tables'] = create_tables
        self.instance.generate_mapping(**generate_mapping_kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def define_binding(db):
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
            def score(self):
                return self.added_count - self.removed_count

            def update_counter(self, operation: Operation, increment: int = 1, is_local_peer: bool = False):
                """ Update Statement's counter
                Args:
                    operation: Resource operation
                    increment:
                    is_local_peer: The flag indicates whether do we performs operations from a local user or from
                        a remote user. In case of the local user, his operations will be considered as
                        authoritative for his (only) local Tribler instance.

                Returns:
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

        class Misc(db.Entity):  # pylint: disable=unused-variable
            name = orm.PrimaryKey(str)
            value = orm.Optional(str)

    def add_operation(self, operation: StatementOperation, signature: bytes, is_local_peer: bool = False,
                      is_auto_generated: bool = False, counter_increment: int = 1) -> bool:
        """ Add the operation that will be applied to a statement.
        Args:
            operation: the class describes the adding operation
            signature: the signature of the operation
            is_local_peer: local operations processes differently than remote operations. They affects
                `Statement.local_operation` field which is used in `self.get_tags()` function.
            is_auto_generated: the indicator of whether this resource was generated automatically or not
            counter_increment: the counter or "numbers" of adding operations

        Returns: True if the operation has been added/updated, False otherwise.
        """
        self.logger.debug(f'Add operation. {operation.subject} "{operation.predicate}" {operation.object}')
        peer = get_or_create(self.instance.Peer, public_key=operation.creator_public_key)
        subject = get_or_create(self.instance.Resource, name=operation.subject, type=operation.subject_type)
        obj = get_or_create(self.instance.Resource, name=operation.object, type=operation.predicate)
        statement = get_or_create(self.instance.Statement, subject=subject, object=obj)
        op = self.instance.StatementOp.get_for_update(statement=statement, peer=peer)

        if not op:  # then insert
            self.instance.StatementOp(statement=statement, peer=peer, operation=operation.operation,
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
               updated_at=datetime.datetime.utcnow(), auto_generated=is_auto_generated)
        return True

    def add_auto_generated(self, subject_type: ResourceType, subject: str, predicate: ResourceType, obj: str) -> bool:
        """ Add an autogenerated operation.

        The difference between "normal" and "autogenerated" operation is that the  autogenerated operation will be added
        with the flag `is_auto_generated=True` and with the `PUBLIC_KEY_FOR_AUTO_GENERATED_TAGS` public key.

        Args:
            subject_type: a type of adding subject. See: ResourceType enum.
            subject: a string that represents a subject of adding operation.
            predicate: the enum that represents a predicate of adding operation.
            obj: a string that represents an object of adding operation.
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

        return self.add_operation(operation, signature=b'', is_local_peer=False, is_auto_generated=True,
                                  counter_increment=SHOW_THRESHOLD)

    @staticmethod
    def _show_condition(s):
        """This function determines show condition for the statement"""
        return s.local_operation == Operation.ADD.value or not s.local_operation and s.score >= SHOW_THRESHOLD

    def _get_resources(self, resource_type: Optional[ResourceType], name: Optional[str], case_sensitive: bool) -> Query:
        """ Get resources

        Args:
            resource_type: type of resources
            name: name of resources
            case_sensitive: if True, then Resources are selected in a case-sensitive manner. if False, then Resources
                are selected in a case-insensitive manner.
        
        Returns: a Query object for requested resources
        """

        results = self.instance.Resource.select()
        if name:
            results = results.filter(
                (lambda r: r.name == name) if case_sensitive else (lambda r: r.name.lower() == name.lower())
            )
        if resource_type:
            results = results.filter(lambda r: r.type == resource_type.value)
        return results

    def _get_statements(self, source_type: Optional[ResourceType], source_name: Optional[str],
                        statements_getter: Callable[[Entity], Entity],
                        target_condition: Callable[[], bool], condition: Callable[[], bool],
                        case_sensitive: bool, ) -> Iterator[str]:
        """ Get entities that satisfies the given condition.
        """

        for resource in self._get_resources(source_type, source_name, case_sensitive):
            results = orm.select(_ for _ in statements_getter(resource)
                                 .select(condition)
                                 .filter(target_condition)
                                 .order_by(lambda s: orm.desc(s.score)))

            yield from list(results)

    def get_objects(self, subject_type: Optional[ResourceType] = None, subject: Optional[str] = '',
                    predicate: Optional[ResourceType] = None, case_sensitive: bool = True,
                    condition: Callable[[], bool] = None) -> List[str]:
        """ Get objects that satisfy the given subject and predicate.

        To understand the order of parameters, keep in ming the following generic construction:
        (<subject_type>, <subject>, <predicate>, <object>).

        So in the case of retrieving objects this construction becomes
        (<subject_type>, <subject>, <predicate>, ?).

        Args:
            subject_type: a type of the subject.
            subject: a string that represents the subject.
            predicate: the enum that represents a predicate of querying operations.
            case_sensitive: if True, then Resources are selected in a case-sensitive manner. if False, then Resources
                are selected in a case-insensitive manner.

        Returns: a list of the strings representing the objects.
        """
        self.logger.debug(f'Get subjects for {subject} with {predicate}')

        statements = self._get_statements(
            source_type=subject_type,
            source_name=subject,
            statements_getter=lambda r: r.subject_statements,
            target_condition=(lambda s: s.object.type == predicate.value) if predicate else (lambda _: True),
            condition=condition or self._show_condition,
            case_sensitive=case_sensitive,
        )
        return [s.object.name for s in statements]

    def get_subjects(self, subject_type: Optional[ResourceType] = None, predicate: Optional[ResourceType] = None,
                     obj: Optional[str] = '', case_sensitive: bool = True) -> List[str]:
        """ Get subjects that satisfy the given object and predicate.
        To understand the order of parameters, keep in ming the following generic construction:

        (<subject_type>, <subject>, <predicate>, <object>).

        So in the case of retrieving subjects this construction becomes
        (<subject_type>, ?, <predicate>, <object>).

        Args:
            subject_type: a type of the subject.
            obj: a string that represents the object.
            predicate: the enum that represents a predicate of querying operations.
            case_sensitive: if True, then Resources are selected in a case-sensitive manner. if False, then Resources
                are selected in a case-insensitive manner.

        Returns: a list of the strings representing the subjects.
        """
        self.logger.debug(f'Get linked back resources for {obj} with {predicate}')

        statements = self._get_statements(
            source_type=predicate,
            source_name=obj,
            statements_getter=lambda r: r.object_statements,
            target_condition=(lambda s: s.subject.type == subject_type.value) if subject_type else (lambda _: True),
            condition=self._show_condition,
            case_sensitive=case_sensitive,
        )

        return [s.subject.name for s in statements]

    def get_statements(self, subject_type: Optional[ResourceType] = None, subject: Optional[str] = '',
                       case_sensitive: bool = True) -> List[SimpleStatement]:

        statements = self._get_statements(
            source_type=subject_type,
            source_name=subject,
            statements_getter=lambda r: r.subject_statements,
            target_condition=lambda _: True,
            condition=self._show_condition,
            case_sensitive=case_sensitive,
        )

        statements = map(lambda s: SimpleStatement(
            subject_type=s.subject.type,
            subject=s.subject.name,
            predicate=s.object.type,
            object=s.object.name
        ), statements)

        return list(statements)

    def get_suggestions(self, subject_type: Optional[ResourceType] = None, subject: Optional[str] = '',
                        predicate: Optional[ResourceType] = None, case_sensitive: bool = True) -> List[str]:
        """ Get all suggestions for a particular subject.

        Args:
            subject_type: a type of the subject.
            subject: a string that represents the subject.
            predicate: the enum that represents a predicate of querying operations.
            case_sensitive: if True, then Resources are selected in a case-sensitive manner. if False, then Resources
                are selected in a case-insensitive manner.

        Returns: a list of the strings representing the objects.
        """
        self.logger.debug(f"Getting suggestions for {subject} with {predicate}")

        suggestions = self.get_objects(
            subject_type=subject_type,
            subject=subject,
            predicate=predicate,
            case_sensitive=case_sensitive,
            condition=lambda s: not s.local_operation and between(s.score, HIDE_THRESHOLD + 1, SHOW_THRESHOLD - 1)
        )
        return suggestions

    def get_subjects_intersection(self, subjects_type: Optional[ResourceType], objects: Set[str],
                                  predicate: Optional[ResourceType],
                                  case_sensitive: bool = True) -> Set[str]:
        if not objects:
            return set()

        if case_sensitive:
            name_condition = '"obj"."name" = $obj_name'
        else:
            name_condition = 'py_lower("obj"."name") = py_lower($obj_name)'

        query = select(r.name for r in self.instance.Resource)
        for obj_name in objects:
            query = query.filter(raw_sql(f"""
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
            WHERE "obj"."type" = $(predicate.value) AND {name_condition}
        )
    )"""))
        return set(query)

    def get_clock(self, operation: StatementOperation) -> int:
        """ Get the clock (int) of operation.
        """
        peer = self.instance.Peer.get(public_key=operation.creator_public_key)
        subject = self.instance.Resource.get(name=operation.subject, type=operation.subject_type)
        obj = self.instance.Resource.get(name=operation.object, type=operation.predicate)
        if not subject or not obj or not peer:
            return CLOCK_START_VALUE

        statement = self.instance.Statement.get(subject=subject, object=obj)
        if not statement:
            return CLOCK_START_VALUE

        op = self.instance.StatementOp.get(statement=statement, peer=peer)
        return op.clock if op else CLOCK_START_VALUE

    def get_operations_for_gossip(self, count: int = 10) -> Set[Entity]:
        """ Get random operations from the DB that older than time_delta.

        Args:
            count: a limit for a resulting query
        """
        return self._get_random_operations_by_condition(
            condition=lambda so: not so.auto_generated,
            count=count
        )

    def shutdown(self) -> None:
        self.instance.disconnect()

    def _get_random_operations_by_condition(self, condition: Callable[[Entity], bool], count: int = 5,
                                            attempts: int = 100) -> Set[Entity]:
        """ Get `count` random operations that satisfy the given condition.

        This method were introduce as an fast alternative for native Pony `random` method.


        Args:
            condition: the condition by which the entities will be queried.
            count: the amount of entities to return.
            attempts: maximum attempt count for requesting the DB.

        Returns: a set of random operations
        """
        operations = set()
        for _ in range(attempts):
            if len(operations) == count:
                return operations

            random_operations_list = self.instance.StatementOp.select_random(1)
            if random_operations_list:
                operation = random_operations_list[0]
                if condition(operation):
                    operations.add(operation)

        return operations

    def get_misc(self, key: str, default: Optional[str] = None) -> Optional[str]:
        data = self.instance.Misc.get(name=key)
        return data.value if data else default

    def set_misc(self, key: str, value: Any):
        key_value = get_or_create(self.instance.Misc, name=key)
        key_value.value = str(value)
