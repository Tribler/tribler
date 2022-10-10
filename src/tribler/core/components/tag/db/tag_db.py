import datetime
import logging
from enum import IntEnum
from typing import Callable, Iterable, List, Optional, Set

from pony import orm
from pony.orm.core import Entity
from pony.utils import between

from tribler.core.components.tag.community.tag_payload import StatementOperation
from tribler.core.utilities.pony_utils import get_or_create

CLOCK_START_VALUE = 0

PUBLIC_KEY_FOR_AUTO_GENERATED_TAGS = b'auto_generated'

SHOW_THRESHOLD = 1
HIDE_THRESHOLD = -2


class Operation(IntEnum):
    ADD = 1
    REMOVE = 2


class Predicate(IntEnum):
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

    TAG = 101
    TORRENT = 102


class TagDatabase:
    def __init__(self, filename: Optional[str] = None, *, create_tables: bool = True, **generate_mapping_kwargs):
        self.instance = orm.Database()
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
            predicate = orm.Required(int, default=101, index=True)  # default is the 'HAS_TAG' predicate
            object = orm.Required(lambda: Resource)

            operations = orm.Set(lambda: StatementOp)

            added_count = orm.Required(int, default=0)
            removed_count = orm.Required(int, default=0)

            local_operation = orm.Optional(int)  # in case user don't (or do) want to see it locally

            orm.composite_key(subject, predicate, object)

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
            name = orm.Required(str, unique=True)

            subject_statements = orm.Set(lambda: Statement, reverse="subject")
            object_statements = orm.Set(lambda: Statement, reverse="object")

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
        subject = get_or_create(self.instance.Resource, name=operation.subject)
        obj = get_or_create(self.instance.Resource, name=operation.object)
        statement = get_or_create(self.instance.Statement, subject=subject, predicate=operation.predicate, object=obj)
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

    def add_auto_generated(self, subject: str, predicate: Predicate, obj: str):
        operation = StatementOperation(
            subject=subject,
            predicate=predicate,
            object=obj,
            operation=Operation.ADD,
            clock=CLOCK_START_VALUE,
            creator_public_key=PUBLIC_KEY_FOR_AUTO_GENERATED_TAGS,
        )

        self.add_operation(operation, signature=b'', is_local_peer=False, is_auto_generated=True,
                           counter_increment=SHOW_THRESHOLD)

    @staticmethod
    def _show_condition(statement):
        """This function determines show condition for the torrent_tag"""
        return statement.local_operation == Operation.ADD.value or \
               not statement.local_operation and statement.score >= SHOW_THRESHOLD

    def _get_resources(self, resource: str, condition: Callable[[], bool], predicate: Predicate, case_sensitive: bool,
                       is_normal_direction: bool) -> List[str]:
        """ Get resources that satisfy a given condition.
        """
        if case_sensitive:
            resources = list(self.instance.Resource.select(lambda r: r.name == resource))
        else:
            resources = list(self.instance.Resource.select(lambda r: r.name.lower() == resource.lower()))

        if not resources:
            return []
        result = []
        for resource_entity in resources:
            query = (
                (resource_entity.subject_statements if is_normal_direction else resource_entity.object_statements)
                .select(condition)
                .filter(lambda statement: statement.predicate == predicate.value)
            )
            query = query.order_by(lambda statement: orm.desc(statement.score))
            query = orm.select(s.object.name if is_normal_direction else s.subject.name for s in query)
            result.extend(query)
        return result

    def get_objects(self, subject: str, predicate: Predicate, case_sensitive: bool = True) -> List[str]:
        """ Get resources that satisfies given subject and predicate.
        """
        self.logger.debug(f'Get resources for {subject} with {predicate}')

        return self._get_resources(subject, self._show_condition, predicate, case_sensitive, is_normal_direction=True)

    def get_subjects(self, obj: str, predicate: Predicate, case_sensitive: bool = True) -> List[str]:
        """ Get list of subjects that could be linked back to the objects.
        """
        self.logger.debug(f'Get linked back resources for {obj} with {predicate}')

        return self._get_resources(obj, self._show_condition, predicate, case_sensitive, is_normal_direction=False)

    def get_suggestions(self, subject: str, predicate: Predicate, case_sensitive: bool = True) -> List[str]:
        """Get all suggestions for a particular subject.
        """
        self.logger.debug(f"Getting suggestions for {subject} with {predicate}")

        def show_suggestions_condition(statement):
            return not statement.local_operation and \
                   between(statement.score, HIDE_THRESHOLD + 1, SHOW_THRESHOLD - 1)

        return self._get_resources(subject, show_suggestions_condition, predicate, case_sensitive,
                                   is_normal_direction=True)

    def get_subjects_intersection(self, objects: Set[str], predicate: Predicate,
                                  case_sensitive: bool = True) -> Set[str]:
        # FIXME: Ask @kozlovsky how to do it in a proper way
        sets = [set(self.get_subjects(o, predicate, case_sensitive)) for o in objects]
        return set.intersection(*sets)

    def get_clock(self, operation: StatementOperation) -> int:
        """ Get the clock (int) of operation.
        """
        peer = self.instance.Peer.get(public_key=operation.creator_public_key)
        subject = self.instance.Resource.get(name=operation.subject)
        obj = self.instance.Resource.get(name=operation.object)
        if not subject or not obj or not peer:
            return CLOCK_START_VALUE

        statement = self.instance.Statement.get(subject=subject, object=obj, predicate=operation.predicate)
        if not statement:
            return CLOCK_START_VALUE

        op = self.instance.StatementOp.get(statement=statement, peer=peer)
        return op.clock if op else CLOCK_START_VALUE

    def get_operations_for_gossip(self, time_delta, count: int = 10) -> Iterable[Entity]:
        """ Get random operations from the DB that older than time_delta.

        Args:
            time_delta: a dictionary for `datetime.timedelta`
            count: a limit for a resulting query
        """
        updated_at = datetime.datetime.utcnow() - datetime.timedelta(**time_delta)
        return self._get_random_operations_by_condition(
            condition=lambda so: so.updated_at <= updated_at and not so.auto_generated,
            count=count
        )

    def shutdown(self) -> None:
        self.instance.disconnect()

    def _get_random_operations_by_condition(self, condition: Callable[[Entity], bool], count: int = 5,
                                            attempts: int = 100) -> Set[Entity]:
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
