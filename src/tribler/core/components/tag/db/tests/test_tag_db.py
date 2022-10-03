import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pony import orm
from pony.orm import commit, db_session

from tribler.core.components.tag.community.tag_payload import TagOperationEnum, TagRelationEnum
from tribler.core.components.tag.db.tag_db import PUBLIC_KEY_FOR_AUTO_GENERATED_TAGS, SHOW_THRESHOLD, TagDatabase
from tribler.core.components.tag.db.tests.test_tag_db_base import Tag, TestTagDBBase
from tribler.core.utilities.pony_utils import get_or_create


# pylint: disable=protected-access
class TestTagDB(TestTagDBBase):
    @patch.object(orm.Database, 'generate_mapping')
    def test_constructor_create_tables_true(self, mocked_generate_mapping: Mock):
        TagDatabase(':memory:')
        mocked_generate_mapping.assert_called_with(create_tables=True)

    @patch.object(orm.Database, 'generate_mapping')
    def test_constructor_create_tables_false(self, mocked_generate_mapping: Mock):
        TagDatabase(':memory:', create_tables=False)
        mocked_generate_mapping.assert_called_with(create_tables=False)

    @db_session
    async def test_get_or_create(self):
        # Test that function get_or_create() works as expected:
        # it gets an entity if the entity is exist and create the entity otherwise
        assert self.db.instance.Peer.select().count() == 0

        # test create
        peer = get_or_create(self.db.instance.Peer, public_key=b'123')
        commit()
        assert peer.public_key == b'123'
        assert self.db.instance.Peer.select().count() == 1

        # test get
        peer = get_or_create(self.db.instance.Peer, public_key=b'123')
        assert peer.public_key == b'123'
        assert self.db.instance.Peer.select().count() == 1

    @db_session
    async def test_update_counter_add(self):
        torrent_tag = self.create_torrent_tag()

        # let's update ADD counter
        torrent_tag.update_counter(TagOperationEnum.ADD, increment=1)
        assert torrent_tag.added_count == 1
        assert torrent_tag.removed_count == 0
        assert not torrent_tag.local_operation

    @db_session
    async def test_update_counter_remove(self):
        torrent_tag = self.create_torrent_tag()

        # let's update REMOVE counter
        torrent_tag.update_counter(TagOperationEnum.REMOVE, increment=1)
        assert torrent_tag.added_count == 0
        assert torrent_tag.removed_count == 1
        assert not torrent_tag.local_operation

    @db_session
    async def test_update_counter_local(self):
        torrent_tag = self.create_torrent_tag()

        # let's update local operation
        torrent_tag.update_counter(TagOperationEnum.REMOVE, increment=1, is_local_peer=True)
        assert torrent_tag.added_count == 0
        assert torrent_tag.removed_count == 1
        assert torrent_tag.local_operation == TagOperationEnum.REMOVE

    @db_session
    async def test_remote_add_tag_operation(self):
        def assert_all_tables_have_the_only_one_entity():
            assert self.db.instance.Peer.select().count() == 1
            assert self.db.instance.Torrent.select().count() == 1
            assert self.db.instance.TorrentTag.select().count() == 1
            assert self.db.instance.Tag.select().count() == 1
            assert self.db.instance.TorrentTagOp.select().count() == 1

        # add the first operation
        self.add_operation(self.db, b'infohash', 'tag', b'peer1')
        assert_all_tables_have_the_only_one_entity()

        # add the same operation
        self.add_operation(self.db, b'infohash', 'tag', b'peer1')
        assert_all_tables_have_the_only_one_entity()

        # add an operation from the past
        self.add_operation(self.db, b'infohash', 'tag', b'peer1', clock=0)
        assert_all_tables_have_the_only_one_entity()

        # add a duplicate operation but from the future
        self.add_operation(self.db, b'infohash', 'tag', b'peer1', clock=1000)
        assert_all_tables_have_the_only_one_entity()

        assert self.db.instance.TorrentTagOp.get().operation == TagOperationEnum.ADD
        assert self.db.instance.TorrentTag.get().added_count == 1
        assert self.db.instance.TorrentTag.get().removed_count == 0

        # add a unique operation from the future
        self.add_operation(self.db, b'infohash', 'tag', b'peer1', operation=TagOperationEnum.REMOVE, clock=1001)
        assert_all_tables_have_the_only_one_entity()
        assert self.db.instance.TorrentTagOp.get().operation == TagOperationEnum.REMOVE
        assert self.db.instance.TorrentTag.get().added_count == 0
        assert self.db.instance.TorrentTag.get().removed_count == 1

    @db_session
    async def test_remote_add_multiple_tag_operations(self):
        self.add_operation(self.db, b'infohash', 'tag', b'peer1')
        self.add_operation(self.db, b'infohash', 'tag', b'peer2')
        self.add_operation(self.db, b'infohash', 'tag', b'peer3')
        self.add_operation(self.db, b'infohash', 'tag', b'peer1', relation=TagRelationEnum.HAS_CONTENT_ITEM)

        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_TAG).added_count == 3
        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_CONTENT_ITEM).added_count == 1

        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_TAG).removed_count == 0
        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_CONTENT_ITEM).removed_count == 0

        self.add_operation(self.db, b'infohash', 'tag', b'peer2', operation=TagOperationEnum.REMOVE)
        self.add_operation(self.db, b'infohash', 'tag', b'peer2', operation=TagOperationEnum.REMOVE,
                           relation=TagRelationEnum.HAS_CONTENT_ITEM)

        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_TAG).added_count == 2
        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_TAG).removed_count == 1

        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_CONTENT_ITEM).added_count == 1
        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_CONTENT_ITEM).removed_count == 1

        self.add_operation(self.db, b'infohash', 'tag', b'peer1', operation=TagOperationEnum.REMOVE)
        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_TAG).added_count == 1
        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_TAG).removed_count == 2

        self.add_operation(self.db, b'infohash', 'tag', b'peer1')
        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_TAG).added_count == 2
        assert self.db.instance.TorrentTag.get(relation=TagRelationEnum.HAS_TAG).removed_count == 1

    @db_session
    async def test_add_auto_generated_tag(self):
        self.db.add_auto_generated_tag(
            infohash=b'infohash',
            tag='tag'
        )

        assert self.db.instance.TorrentTagOp.get().auto_generated
        assert self.db.instance.TorrentTag.get().added_count == SHOW_THRESHOLD
        assert self.db.instance.Peer.get().public_key == PUBLIC_KEY_FOR_AUTO_GENERATED_TAGS

    @db_session
    async def test_multiple_tags(self):
        self.add_operation_set(
            self.db,
            {
                b'infohash1': [
                    Tag(name='tag1', count=2),
                    Tag(name='tag2', count=2),
                    Tag(name='tag3', count=1),
                ],
                b'infohash2': [
                    Tag(name='tag1', count=1),
                    Tag(name='tag2', count=1),
                    Tag(name='tag4', count=1),
                    Tag(name='tag5', count=1),
                    Tag(name='tag6', count=1),
                ]
            }
        )

        def assert_entities_count():
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

    @db_session
    async def test_get_tags_added(self):
        self.add_operation_set(
            self.db,
            {
                b'infohash1': [
                    Tag(name='tag1', count=SHOW_THRESHOLD - 1),
                    Tag(name='tag2', count=SHOW_THRESHOLD),
                    Tag(name='tag3', count=SHOW_THRESHOLD + 1),
                    Tag(name='ContentItem', count=SHOW_THRESHOLD + 1, relation=TagRelationEnum.HAS_CONTENT_ITEM),
                ]
            }
        )

        assert not self.db.get_tags(b'missed infohash')
        assert self.db.get_tags(b'infohash1') == ['tag3', 'tag2']
        assert self.db.get_tags(b'infohash1', relation=TagRelationEnum.HAS_CONTENT_ITEM) == ['ContentItem']

    @db_session
    async def test_get_tags_removed(self):
        self.add_operation_set(
            self.db,
            {
                b'infohash1': [
                    Tag(name='tag1', count=SHOW_THRESHOLD),
                    Tag(name='tag2', count=SHOW_THRESHOLD)
                ]
            }
        )

        self.add_operation(self.db, infohash=b'infohash1', tag='tag2', peer=b'4', operation=TagOperationEnum.REMOVE)

        assert self.db.get_tags(b'infohash1') == ['tag1']

    @db_session
    async def test_show_local_tags(self):
        # Test that locally added tags have a priority to show.
        # That means no matter of other peers opinions, locally added tag should be visible.
        self.add_operation(self.db, b'infohash1', 'tag1', b'peer1', operation=TagOperationEnum.REMOVE)
        self.add_operation(self.db, b'infohash1', 'tag1', b'peer2', operation=TagOperationEnum.REMOVE)
        assert not self.db.get_tags(b'infohash1')

        # test local add
        self.add_operation(self.db, b'infohash1', 'tag1', b'peer3', operation=TagOperationEnum.ADD, is_local_peer=True)
        self.add_operation(self.db, b'infohash1', 'content_item', b'peer3', operation=TagOperationEnum.ADD,
                           relation=TagRelationEnum.HAS_CONTENT_ITEM, is_local_peer=True)
        assert self.db.get_tags(b'infohash1') == ['tag1']
        assert self.db.get_tags(b'infohash1', relation=TagRelationEnum.HAS_CONTENT_ITEM) == ['content_item']

    @db_session
    async def test_hide_local_tags(self):
        # Test that locally removed tags should not be visible to local user.
        # No matter of other peers opinions, locally removed tag should be not visible.
        self.add_operation(self.db, b'infohash1', 'tag1', b'peer1')
        self.add_operation(self.db, b'infohash1', 'tag1', b'peer2')
        assert self.db.get_tags(b'infohash1') == ['tag1']

        # test local remove
        self.add_operation(self.db, b'infohash1', 'tag1', b'peer3', operation=TagOperationEnum.REMOVE,
                           is_local_peer=True)
        assert self.db.get_tags(b'infohash1') == []

    @db_session
    async def test_suggestions(self):
        # Test whether the database returns the right suggestions.
        # Suggestions are tags that have not gathered enough support for display yet.
        self.add_operation(self.db, tag='tag1', peer=b'1')
        self.add_operation(self.db, tag='tag1', peer=b'2')
        self.add_operation(self.db, tag='tag1', peer=b'2', relation=TagRelationEnum.HAS_CONTENT_ITEM)
        assert self.db.get_suggestions(b'infohash') == []  # This tag now has enough support

        self.add_operation(self.db, tag='tag1', peer=b'3', operation=TagOperationEnum.REMOVE)  # score:1
        self.add_operation(self.db, tag='tag1', peer=b'4', operation=TagOperationEnum.REMOVE)  # score:0
        assert self.db.get_suggestions(b'infohash') == ["tag1"]

        self.add_operation(self.db, tag='tag1', peer=b'5', operation=TagOperationEnum.REMOVE)  # score:-1
        self.add_operation(self.db, tag='tag1', peer=b'6', operation=TagOperationEnum.REMOVE)  # score:-2
        assert not self.db.get_suggestions(b'infohash')  # below the threshold

    @db_session
    async def test_get_clock_of_operation(self):
        operation = self.create_operation(tag='tag1')
        assert self.db.get_clock(operation) == 0

        self.add_operation(self.db, infohash=operation.infohash, tag=operation.tag, peer=operation.creator_public_key,
                           clock=1)

        assert self.db.get_clock(operation) == 1

    @db_session
    async def test_get_tags_operations_for_gossip(self):
        time_delta = {'minutes': 1}
        self.add_operation_set(
            self.db,
            {
                b'infohash1': [
                    Tag(name='tag1', count=1),
                    Tag(name='tag2', count=1),
                    Tag(name='tag3', count=2, auto_generated=True)
                ]
            }
        )

        # assert that immediately added torrents are not returned
        assert not self.db.get_tags_operations_for_gossip(time_delta)

        # put back in the past two tag: 'tag1' and 'tag3'
        for tag in ['tag1', 'tag3']:
            query = lambda tto: tto.torrent_tag.tag.name == tag  # pylint: disable=cell-var-from-loop
            tag_operations = self.db.instance.TorrentTagOp.select(query)
            for tag_operation in tag_operations:
                tag_operation.updated_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=2)

        # assert that only one torrent returned (the old and the not auto generated one)
        assert len(self.db.get_tags_operations_for_gossip(time_delta)) == 1

    @db_session
    async def test_get_infohashes_threshold(self):
        # test that `get_infohashes` function returns only infohashes with tags
        # above the threshold
        self.add_operation_set(
            self.db,
            {
                b'infohash1': [
                    Tag(name='tag1', count=SHOW_THRESHOLD),
                ],
                b'infohash2': [
                    Tag(name='tag1', count=SHOW_THRESHOLD - 1)
                ],
                b'infohash3': [
                    Tag(name='tag1', count=SHOW_THRESHOLD, relation=TagRelationEnum.HAS_CONTENT_ITEM),
                ],
            }
        )

        assert self.db.get_infohashes({'tag1'}) == [b'infohash1']

    @db_session
    async def test_get_infohashes(self):
        # test that `get_infohashes` function returns an intersection of result
        # in case of more than one tag passed to the function
        self.add_operation_set(
            self.db,
            {
                b'infohash1': [
                    Tag(name='tag1', count=SHOW_THRESHOLD),
                    Tag(name='tag2', count=SHOW_THRESHOLD),
                    Tag(name='ContentItem', count=SHOW_THRESHOLD, relation=TagRelationEnum.HAS_CONTENT_ITEM)
                ],
                b'infohash2': [
                    Tag(name='tag1', count=SHOW_THRESHOLD),
                    Tag(name='ContentItem', count=SHOW_THRESHOLD, relation=TagRelationEnum.HAS_CONTENT_ITEM)
                ],
                b'infohash3': [
                    Tag(name='tag2', count=SHOW_THRESHOLD)
                ]
            }
        )

        assert self.db.get_infohashes({'missed tag'}) == [b'infohash1', b'infohash2', b'infohash3']
        assert self.db.get_infohashes({'tag1'}) == [b'infohash1', b'infohash2']
        assert self.db.get_infohashes({'tag2'}) == [b'infohash1', b'infohash3']
        assert self.db.get_infohashes({'tag1', 'tag2'}) == [b'infohash1']
        assert self.db.get_infohashes({'ContentItem'}, relation=TagRelationEnum.HAS_CONTENT_ITEM) == [b'infohash1',
                                                                                                      b'infohash2']

    @db_session
    async def test_show_condition(self):
        assert TagDatabase._show_condition(SimpleNamespace(local_operation=TagOperationEnum.ADD))
        assert TagDatabase._show_condition(SimpleNamespace(local_operation=None, score=SHOW_THRESHOLD))
        assert not TagDatabase._show_condition(SimpleNamespace(local_operation=None, score=0))

    @db_session
    async def test_get_random_tag_operations_by_condition_less_than_count(self):
        # Check that `_get_random_tag_operations_by_condition` returns values even in the case that requested amount
        # of operations is unavailable

        self.add_operation_set(
            self.db,
            {
                b'infohash1': [
                    Tag(name='tag1', count=3),  # add 3 TorrentTagOp
                ],
            }
        )

        # request 5 random operations
        random_operations = self.db._get_random_tag_operations_by_condition(
            condition=lambda _: True,
            count=5,
            attempts=100
        )

        assert len(random_operations) == 3

    @db_session
    async def test_get_random_tag_operations_by_condition_greater_than_count(self):
        # Check that `_get_random_tag_operations_by_condition` returns requested amount of entities
        # even if there are more entities in DB than this requested amount.
        self.add_operation_set(
            self.db,
            {
                b'infohash1': [
                    Tag(name='tag1', count=10),  # add 10 TorrentTagOp
                ],
            }
        )

        # request 5 random operations
        random_operations = self.db._get_random_tag_operations_by_condition(
            condition=lambda _: True,
            count=5,
            attempts=100
        )

        assert len(random_operations) == 5

    @db_session
    async def test_get_random_tag_operations_by_condition(self):
        # Check that `_get_random_tag_operations_by_condition` uses a passed condition.

        self.add_operation_set(
            self.db,
            {
                b'infohash1': [
                    Tag(name='tag1', count=10, auto_generated=True),  # add 10 autogenerated tags
                    Tag(name='tag2', count=10, auto_generated=False),  # add 10 normal tags
                ],
            }
        )

        # request 5 normal tags
        random_operations = self.db._get_random_tag_operations_by_condition(
            condition=lambda tto: not tto.auto_generated,
            count=5,
            attempts=100
        )

        # check that only normal tags have been returned
        assert len(random_operations) == 5
        assert all(not o.auto_generated for o in random_operations)

    @db_session
    async def test_get_random_tag_operations_by_condition_no_results(self):
        # test the case when the database is not empty but no operations satisfy
        # the condition. The result should be empty.

        self.add_operation_set(
            self.db,
            {
                b'infohash1': [
                    Tag(name='tag1', count=10, auto_generated=True),  # add 10 autogenerated tags
                ],
            }
        )

        # request 5 normal tags
        random_operations = self.db._get_random_tag_operations_by_condition(
            condition=lambda tto: not tto.auto_generated,
            count=5,
            attempts=100
        )

        # check that only normal tags have been returned
        assert len(random_operations) == 0
