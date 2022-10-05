from dataclasses import dataclass
from itertools import count

from ipv8.test.base import TestBase
from pony.orm import commit, db_session

from tribler.core.components.tag.community.tag_payload import TagOperation
from tribler.core.components.tag.db.tag_db import TagDatabase, TagOperationEnum, TagRelationEnum
from tribler.core.utilities.pony_utils import get_or_create


# pylint: disable=protected-access

@dataclass
class Tag:
    name: str
    count: int = 1
    relation: int = TagRelationEnum.HAS_TAG
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
        print('\nTorrent:')
        self.db.instance.Torrent.select().show()
        print('\nTag')
        self.db.instance.Tag.select().show()
        print('\nTorrentTag')
        self.db.instance.TorrentTag.select().show()
        print('\nTorrentTagOp')
        self.db.instance.TorrentTagOp.select().show()

    def create_torrent_tag(self, tag='tag', infohash=b'infohash', relation: TagRelationEnum = TagRelationEnum.HAS_TAG):
        tag = get_or_create(self.db.instance.Tag, name=tag)
        torrent = get_or_create(self.db.instance.Torrent, infohash=infohash)
        torrent_tag = get_or_create(self.db.instance.TorrentTag, tag=tag, torrent=torrent, relation=relation)

        return torrent_tag

    @staticmethod
    def create_operation(infohash=b'infohash', tag='tag', peer=b'', operation=TagOperationEnum.ADD,
                         relation=TagRelationEnum.HAS_TAG, clock=0):
        return TagOperation(infohash=infohash, tag=tag, operation=operation, relation=relation, clock=clock,
                            creator_public_key=peer)

    @staticmethod
    def add_operation(tag_db: TagDatabase, infohash=b'infohash', tag='tag', peer=b'',
                      operation: TagOperationEnum = None, relation: TagRelationEnum = None,
                      is_local_peer=False, clock=None, is_auto_generated=False, counter_increment: int = 1):
        operation = operation or TagOperationEnum.ADD
        relation = relation or TagRelationEnum.HAS_TAG
        operation = TestTagDBBase.create_operation(infohash, tag, peer, operation, relation, clock)
        operation.clock = clock or tag_db.get_clock(operation) + 1
        result = tag_db.add_tag_operation(operation, signature=b'', is_local_peer=is_local_peer,
                                          is_auto_generated=is_auto_generated, counter_increment=counter_increment)
        commit()
        return result

    @staticmethod
    def add_operation_set(tag_db: TagDatabase, dictionary):
        index = count(0)

        def generate_n_peer_names(n):
            for _ in range(n):
                yield f'peer{next(index)}'.encode('utf8')

        for infohash, tags in dictionary.items():
            for tag in tags:
                for peer in generate_n_peer_names(tag.count):
                    TestTagDBBase.add_operation(tag_db, infohash, tag.name, peer, relation=tag.relation,
                                                is_auto_generated=tag.auto_generated)
