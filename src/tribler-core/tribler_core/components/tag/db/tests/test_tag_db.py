from pony.orm import commit, db_session

from ipv8.test.base import TestBase
from tribler_core.components.tag.db.tag_db import Operation, TagDatabase


# pylint: disable=protected-access


class TestTagDB(TestBase):
    def setUp(self):
        super().setUp()
        self.db = TagDatabase()
        self.timer = 0

    async def tearDown(self):
        await super().tearDown()

    def add(self, infohash=b'', tag='', peer=b'', time_increment=1, operation=Operation.ADD, is_local_peer=False):
        self.timer += time_increment
        self.db.add_tag_operation(infohash=infohash, tag=tag, operation=operation, time_of_operation=self.timer,
                                  creator_public_key=peer, signature=b'', is_local_peer=is_local_peer)
        commit()

    @db_session
    async def test_get_or_create(self):
        # test create
        assert self.db.instance.Peer.select().count() == 0
        self.db._get_or_create(self.db.instance.Peer, public_key=b'123', create_kwargs={'last_time': 42})
        commit()

        # test get
        assert self.db.instance.Peer.select().count() == 1
        peer = self.db._get_or_create(self.db.instance.Peer, public_key=b'123', create_kwargs={'last_time': 24})
        assert peer.public_key == b'123'
        assert peer.last_time == 42

    @db_session
    async def test_update_counter(self):
        instance = self.db.instance

        # create torrent tag
        tag = self.db._get_or_create(instance.Tag, name="tribler")
        torrent = self.db._get_or_create(instance.Torrent, infohash=b'123')
        torrent_tag = self.db._get_or_create(instance.TorrentTag, tag=tag, torrent=torrent)
        commit()

        assert torrent_tag.added_count == 0
        assert torrent_tag.removed_count == 0
        assert not torrent_tag.local_operation

        # test remote peer
        torrent_tag.update_counter(Operation.ADD, increment=1)
        assert torrent_tag.added_count == 1
        assert torrent_tag.removed_count == 0
        assert not torrent_tag.local_operation

        torrent_tag.update_counter(Operation.REMOVE, increment=1)
        assert torrent_tag.added_count == 1
        assert torrent_tag.removed_count == 1
        assert not torrent_tag.local_operation

        # test local peer
        torrent_tag.update_counter(Operation.REMOVE, increment=1, is_local_peer=True)
        assert torrent_tag.added_count == 1
        assert torrent_tag.removed_count == 2
        assert torrent_tag.local_operation == Operation.REMOVE

    @db_session
    async def test_remote_add_tag_operation(self):
        def assert_all_tables_have_the_only_one_entity():
            assert self.db.instance.Peer.select().count() == 1
            assert self.db.instance.Torrent.select().count() == 1
            assert self.db.instance.TorrentTag.select().count() == 1
            assert self.db.instance.Tag.select().count() == 1
            assert self.db.instance.TorrentTagOp.select().count() == 1

        # add the first operation
        self.add(b'infohash', 'tag', b'peer1')
        assert_all_tables_have_the_only_one_entity()

        # add the same operation
        self.add(b'infohash', 'tag', b'peer1')
        assert_all_tables_have_the_only_one_entity()

        # add an operation from the past
        self.add(b'infohash', 'tag', b'peer1', time_increment=-1)
        assert_all_tables_have_the_only_one_entity()

        # add a duplicate operation from the future
        self.add(b'infohash', 'tag', b'peer1', time_increment=10)
        assert_all_tables_have_the_only_one_entity()

        assert self.db.instance.TorrentTagOp.get().operation == Operation.ADD
        assert self.db.instance.TorrentTag.get().added_count == 1
        assert self.db.instance.TorrentTag.get().removed_count == 0

        # add a unique operation from the future
        self.add(b'infohash', 'tag', b'peer1', operation=Operation.REMOVE, time_increment=10)
        assert_all_tables_have_the_only_one_entity()
        assert self.db.instance.TorrentTagOp.get().operation == Operation.REMOVE
        assert self.db.instance.TorrentTag.get().added_count == 0
        assert self.db.instance.TorrentTag.get().removed_count == 1

    @db_session
    async def test_remote_add_multiple_tag_operations(self):
        self.add(b'infohash', 'tag', b'peer1')
        self.add(b'infohash', 'tag', b'peer2')
        self.add(b'infohash', 'tag', b'peer3')

        assert self.db.instance.TorrentTag.get().added_count == 3
        assert self.db.instance.TorrentTag.get().removed_count == 0

        self.add(b'infohash', 'tag', b'peer2', operation=Operation.REMOVE)
        assert self.db.instance.TorrentTag.get().added_count == 2
        assert self.db.instance.TorrentTag.get().removed_count == 1

        self.add(b'infohash', 'tag', b'peer1', operation=Operation.REMOVE)
        assert self.db.instance.TorrentTag.get().added_count == 1
        assert self.db.instance.TorrentTag.get().removed_count == 2

        self.add(b'infohash', 'tag', b'peer1')
        assert self.db.instance.TorrentTag.get().added_count == 2
        assert self.db.instance.TorrentTag.get().removed_count == 1

    @db_session
    async def test_local_add_tag_operation(self):
        # remote
        self.add(b'infohash', 'tag', b'peer1')
        assert self.db.instance.TorrentTag.get().added_count == 1
        assert self.db.instance.TorrentTag.get().removed_count == 0
        assert not self.db.instance.TorrentTag.get().local_operation

        # local
        self.add(b'infohash', 'tag', b'peer2', is_local_peer=True)
        assert self.db.instance.TorrentTag.get().added_count == 2
        assert self.db.instance.TorrentTag.get().removed_count == 0
        assert self.db.instance.TorrentTag.get().local_operation == Operation.ADD

        self.add(b'infohash', 'tag', b'peer2', operation=Operation.REMOVE, is_local_peer=True)
        assert self.db.instance.TorrentTag.get().local_operation == Operation.REMOVE
        assert self.db.instance.TorrentTag.get().added_count == 1
        assert self.db.instance.TorrentTag.get().removed_count == 1

    @db_session
    async def test_multiple_tags(self):
        # peer1
        self.add(b'infohash1', 'tag1', b'peer1')
        self.add(b'infohash1', 'tag2', b'peer1')
        self.add(b'infohash1', 'tag3', b'peer1')

        self.add(b'infohash2', 'tag4', b'peer1')
        self.add(b'infohash2', 'tag5', b'peer1')
        self.add(b'infohash2', 'tag6', b'peer1')

        # peer2
        self.add(b'infohash1', 'tag1', b'peer2')
        self.add(b'infohash1', 'tag2', b'peer2')

        # peer3
        self.add(b'infohash2', 'tag1', b'peer3')
        self.add(b'infohash2', 'tag2', b'peer3')

        def assert_entities_count():
            assert self.db.instance.Peer.select().count() == 3
            assert self.db.instance.Torrent.select().count() == 2
            assert self.db.instance.TorrentTag.select().count() == 8
            assert self.db.instance.Tag.select().count() == 6
            assert self.db.instance.TorrentTagOp.select().count() == 10

        assert_entities_count()

        torrent1 = self.db.instance.Torrent.get(infohash=b'infohash1')
        tag1 = self.db.instance.Tag.get(name='tag1')
        torrent_tag = self.db.instance.TorrentTag.get(torrent=torrent1, tag=tag1)
        assert torrent_tag.added_count == 2
        assert torrent_tag.removed_count == 0

        self.add(b'infohash1', 'tag1', b'peer2', operation=Operation.REMOVE)
        self.add(b'infohash1', 'tag2', b'peer2', operation=Operation.REMOVE)
        assert_entities_count()
        assert torrent_tag.added_count == 1
        assert torrent_tag.removed_count == 1

    @db_session
    async def test_get_tags(self):
        # peer1
        self.add(b'infohash1', 'tag1', b'peer1')
        self.add(b'infohash1', 'tag2', b'peer1')
        self.add(b'infohash1', 'tag3', b'peer1')

        self.add(b'infohash2', 'tag4', b'peer1')
        self.add(b'infohash2', 'tag5', b'peer1')
        self.add(b'infohash2', 'tag6', b'peer1')

        # peer2
        self.add(b'infohash1', 'tag1', b'peer2')
        self.add(b'infohash1', 'tag2', b'peer2')

        # peer3
        self.add(b'infohash2', 'tag1', b'peer3')
        self.add(b'infohash2', 'tag2', b'peer3')

        assert self.db.get_tags(b'infohash1') == ['tag1', 'tag2']
        assert self.db.get_tags(b'infohash2') == []
        assert self.db.get_tags(b'infohash3') == []

    @db_session
    async def test_get_tags_local(self):
        self.add(b'infohash1', 'tag1', b'peer1')
        self.add(b'infohash1', 'tag1', b'peer2')
        assert self.db.get_tags(b'infohash1') == ['tag1']

        # test local remove
        self.add(b'infohash1', 'tag1', b'peer3', operation=Operation.REMOVE, is_local_peer=True)
        assert self.db.get_tags(b'infohash1') == []

        # test local add
        self.add(b'infohash2', 'tag2', b'peer3', operation=Operation.ADD, is_local_peer=True)
        assert self.db.get_tags(b'infohash2') == ['tag2']

    @db_session
    async def test_get_last_time_of_operation(self):
        assert not self.db.get_last_time_of_operation(b'infohash', 'tag', b'peer_public_key')

        self.add(b'infohash', 'tag', b'peer_public_key')
        assert self.db.get_last_time_of_operation(b'infohash', 'tag', b'peer_public_key') == 1
