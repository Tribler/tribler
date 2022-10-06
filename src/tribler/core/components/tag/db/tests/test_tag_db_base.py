from dataclasses import dataclass
from itertools import count

from ipv8.test.base import TestBase
from pony.orm import commit, db_session

from tribler.core.components.tag.community.tag_payload import StatementOperation
from tribler.core.components.tag.db.tag_db import Operation, Predicate, SHOW_THRESHOLD, TagDatabase
from tribler.core.utilities.pony_utils import get_or_create


# pylint: disable=protected-access

@dataclass
class Resource:
    name: str
    count: int = SHOW_THRESHOLD
    predicate: int = Predicate.HAS_TAG
    auto_generated: bool = False


class TestTagDBBase(TestBase):
    def setUp(self):
        super().setUp()
        self.db = TagDatabase()

    async def tearDown(self):
        if self._outcome.errors:
            self.dump_db()

        await super().tearDown()

    @db_session
    def dump_db(self):
        print('\nPeer:')
        self.db.instance.Peer.select().show()
        print('\nResource:')
        self.db.instance.Resource.select().show()
        print('\nStatement')
        self.db.instance.Statement.select().show()
        print('\nStatementOp')
        self.db.instance.StatementOp.select().show()

    def create_statement(self, subject='subject', predicate: Predicate = Predicate.HAS_TAG,
                         object='object'):
        subj = get_or_create(self.db.instance.Resource, name=subject)
        obj = get_or_create(self.db.instance.Resource, name=object)
        statement = get_or_create(self.db.instance.Statement, subject=subj, predicate=predicate, object=obj)

        return statement

    @staticmethod
    def create_operation(subject='subject', object='object', peer=b'', operation=Operation.ADD,
                         predicate=Predicate.HAS_TAG, clock=0):
        return StatementOperation(subject=subject, predicate=predicate, object=object, operation=operation, clock=clock,
                                  creator_public_key=peer)

    @staticmethod
    def add_operation(tag_db: TagDatabase, subject: str, predicate: Predicate, object: str,
                      peer=b'', operation: Operation = None, is_local_peer=False, clock=None,
                      is_auto_generated=False, counter_increment: int = 1):
        operation = operation or Operation.ADD
        operation = TestTagDBBase.create_operation(subject, object, peer, operation, predicate, clock)
        operation.clock = clock or tag_db.get_clock(operation) + 1
        result = tag_db.add_operation(operation, signature=b'', is_local_peer=is_local_peer,
                                      is_auto_generated=is_auto_generated, counter_increment=counter_increment)
        commit()
        return result

    @staticmethod
    def add_operation_set(tag_db: TagDatabase, dictionary):
        index = count(0)

        def generate_n_peer_names(n):
            for _ in range(n):
                yield f'peer{next(index)}'.encode('utf8')

        for subject, objects in dictionary.items():
            for obj in objects:
                for peer in generate_n_peer_names(obj.count):
                    TestTagDBBase.add_operation(tag_db, subject, obj.predicate, obj.name, peer,
                                                is_auto_generated=obj.auto_generated)
