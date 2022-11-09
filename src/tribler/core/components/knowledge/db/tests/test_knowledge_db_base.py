from dataclasses import dataclass
from itertools import count

from ipv8.test.base import TestBase
from pony.orm import commit, db_session

from tribler.core.components.knowledge.community.knowledge_payload import StatementOperation
from tribler.core.components.knowledge.db.knowledge_db import KnowledgeDatabase, Operation, ResourceType, SHOW_THRESHOLD
from tribler.core.utilities.pony_utils import get_or_create


# pylint: disable=protected-access

@dataclass
class Resource:
    name: str
    count: int = SHOW_THRESHOLD
    predicate: int = ResourceType.TAG
    auto_generated: bool = False


class TestTagDBBase(TestBase):
    def setUp(self):
        super().setUp()
        self.db = KnowledgeDatabase()

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

    def create_statement(self, subject='subject', subject_type: ResourceType = ResourceType.TORRENT,
                         predicate: ResourceType = ResourceType.TAG, obj='object'):
        subj = get_or_create(self.db.instance.Resource, name=subject, type=subject_type)
        obj = get_or_create(self.db.instance.Resource, name=obj, type=predicate)
        statement = get_or_create(self.db.instance.Statement, subject=subj, object=obj)

        return statement

    @staticmethod
    def create_operation(subject_type: ResourceType = ResourceType.TORRENT, subject='subject', obj='object', peer=b'',
                         operation=Operation.ADD, predicate=ResourceType.TAG, clock=0):
        return StatementOperation(subject=subject, subject_type=subject_type, predicate=predicate, object=obj,
                                  operation=operation, clock=clock, creator_public_key=peer)

    @staticmethod
    def add_operation(tag_db: KnowledgeDatabase, subject_type: ResourceType = ResourceType.TORRENT,
                      subject: str = 'infohash',
                      predicate: ResourceType = ResourceType.TAG, obj: str = 'tag', peer=b'',
                      operation: Operation = None,
                      is_local_peer=False, clock=None, is_auto_generated=False, counter_increment: int = 1):
        operation = operation or Operation.ADD
        operation = TestTagDBBase.create_operation(subject_type, subject, obj, peer, operation, predicate, clock)
        operation.clock = clock or tag_db.get_clock(operation) + 1
        result = tag_db.add_operation(operation, signature=b'', is_local_peer=is_local_peer,
                                      is_auto_generated=is_auto_generated, counter_increment=counter_increment)
        commit()
        return result

    @staticmethod
    def add_operation_set(tag_db: KnowledgeDatabase, dictionary):
        index = count(0)

        def generate_n_peer_names(n):
            for _ in range(n):
                yield f'peer{next(index)}'.encode('utf8')

        for subject, objects in dictionary.items():
            for obj in objects:
                for peer in generate_n_peer_names(obj.count):
                    # assume that for test purposes all subject by default could be `Predicate.TORRENT`
                    TestTagDBBase.add_operation(tag_db, ResourceType.TORRENT, subject, obj.predicate, obj.name, peer,
                                                is_auto_generated=obj.auto_generated)
