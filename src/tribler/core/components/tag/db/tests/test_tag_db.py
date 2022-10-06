import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pony import orm
from pony.orm import commit, db_session

from tribler.core.components.tag.db.tag_db import PUBLIC_KEY_FOR_AUTO_GENERATED_TAGS, Predicate, SHOW_THRESHOLD, \
    TagDatabase, Operation
from tribler.core.components.tag.db.tests.test_tag_db_base import Resource, TestTagDBBase
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
        statement = self.create_statement()

        # let's update ADD counter
        statement.update_counter(Operation.ADD, increment=1)
        assert statement.added_count == 1
        assert statement.removed_count == 0
        assert not statement.local_operation

    @db_session
    async def test_update_counter_remove(self):
        statement = self.create_statement()

        # let's update REMOVE counter
        statement.update_counter(Operation.REMOVE, increment=1)
        assert statement.added_count == 0
        assert statement.removed_count == 1
        assert not statement.local_operation

    @db_session
    async def test_update_counter_local(self):
        statement = self.create_statement()

        # let's update local operation
        statement.update_counter(Operation.REMOVE, increment=1, is_local_peer=True)
        assert statement.added_count == 0
        assert statement.removed_count == 1
        assert statement.local_operation == Operation.REMOVE

    @db_session
    async def test_remote_add_tag_operation(self):
        def assert_all_tables_have_the_only_one_entity():
            assert self.db.instance.Peer.select().count() == 1
            assert self.db.instance.Resource.select().count() == 2
            assert self.db.instance.Statement.select().count() == 1
            assert self.db.instance.StatementOp.select().count() == 1

        # add the first operation
        self.add_operation(self.db, 'infohash', Predicate.HAS_TAG, 'tag', b'peer1')
        assert_all_tables_have_the_only_one_entity()

        # add the same operation
        self.add_operation(self.db, 'infohash', Predicate.HAS_TAG, 'tag', b'peer1')
        assert_all_tables_have_the_only_one_entity()

        # add an operation from the past
        self.add_operation(self.db, 'infohash', Predicate.HAS_TAG, 'tag', b'peer1', clock=0)
        assert_all_tables_have_the_only_one_entity()

        # add a duplicate operation but from the future
        self.add_operation(self.db, 'infohash', Predicate.HAS_TAG, 'tag', b'peer1', clock=1000)
        assert_all_tables_have_the_only_one_entity()

        assert self.db.instance.StatementOp.get().operation == Operation.ADD
        assert self.db.instance.Statement.get().added_count == 1
        assert self.db.instance.Statement.get().removed_count == 0

        # add a unique operation from the future
        self.add_operation(self.db, 'infohash', Predicate.HAS_TAG, 'tag', b'peer1',
                           operation=Operation.REMOVE, clock=1001)
        assert_all_tables_have_the_only_one_entity()
        assert self.db.instance.StatementOp.get().operation == Operation.REMOVE
        assert self.db.instance.Statement.get().added_count == 0
        assert self.db.instance.Statement.get().removed_count == 1

    @db_session
    async def test_remote_add_multiple_tag_operations(self):
        self.add_operation(self.db, 'infohash', Predicate.HAS_TAG, 'tag', b'peer1')
        self.add_operation(self.db, 'infohash', Predicate.HAS_TAG, 'tag', b'peer2')
        self.add_operation(self.db, 'infohash', Predicate.HAS_TAG, 'tag', b'peer3')
        self.add_operation(self.db, 'title', Predicate.HAS_TORRENT, 'infohash', b'peer1')

        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TAG).added_count == 3
        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TORRENT).added_count == 1
        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TAG).removed_count == 0
        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TORRENT).removed_count == 0

        self.add_operation(self.db, 'infohash', Predicate.HAS_TAG, 'tag', b'peer2',
                           operation=Operation.REMOVE)
        self.add_operation(self.db, 'title', Predicate.HAS_TORRENT, 'infohash', b'peer2',
                           operation=Operation.REMOVE)

        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TAG).added_count == 2
        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TAG).removed_count == 1

        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TORRENT).added_count == 1
        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TORRENT).removed_count == 1

        self.add_operation(self.db, 'infohash', Predicate.HAS_TAG, 'tag', b'peer1',
                           operation=Operation.REMOVE)
        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TAG).added_count == 1
        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TAG).removed_count == 2

        self.add_operation(self.db, 'infohash', Predicate.HAS_TAG, 'tag', b'peer1')
        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TAG).added_count == 2
        assert self.db.instance.Statement.get(predicate=Predicate.HAS_TAG).removed_count == 1

    @db_session
    async def test_add_auto_generated_tag(self):
        self.db.add_auto_generated(
            subject='infohash',
            predicate=Predicate.HAS_TAG,
            obj='tag'
        )

        assert self.db.instance.StatementOp.get().auto_generated
        assert self.db.instance.Statement.get().added_count == SHOW_THRESHOLD
        assert self.db.instance.Peer.get().public_key == PUBLIC_KEY_FOR_AUTO_GENERATED_TAGS

    @db_session
    async def test_multiple_tags(self):
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1', count=2, predicate=Predicate.HAS_TAG),
                    Resource(name='tag2', count=2, predicate=Predicate.HAS_TAG),
                    Resource(name='tag3', count=1, predicate=Predicate.HAS_TAG),
                ],
                'infohash2': [
                    Resource(name='tag1', count=1, predicate=Predicate.HAS_TAG),
                    Resource(name='tag2', count=1, predicate=Predicate.HAS_TAG),
                    Resource(name='tag4', count=1, predicate=Predicate.HAS_TAG),
                    Resource(name='tag5', count=1, predicate=Predicate.HAS_TAG),
                    Resource(name='tag6', count=1, predicate=Predicate.HAS_TAG),
                ]
            }
        )

        def assert_entities_count():
            assert self.db.instance.Statement.select().count() == 8
            assert self.db.instance.Resource.select().count() == 8
            assert self.db.instance.StatementOp.select().count() == 10

        assert_entities_count()

        infohash1 = self.db.instance.Resource.get(name='infohash1')
        tag1 = self.db.instance.Resource.get(name='tag1')
        statement = self.db.instance.Statement.get(subject=infohash1, predicate=Predicate.HAS_TAG, object=tag1)
        assert statement.added_count == 2
        assert statement.removed_count == 0

    @db_session
    async def test_get_objects_added(self):
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1', count=SHOW_THRESHOLD - 1, predicate=Predicate.HAS_TAG),
                    Resource(name='tag2', count=SHOW_THRESHOLD, predicate=Predicate.HAS_TAG),
                    Resource(name='tag3', count=SHOW_THRESHOLD + 1, predicate=Predicate.HAS_TAG),
                    Resource(name='Contributor', count=SHOW_THRESHOLD + 1, predicate=Predicate.HAS_CONTRIBUTOR),
                ]
            }
        )

        assert not self.db.get_objects('missed infohash', predicate=Predicate.HAS_TAG)
        assert self.db.get_objects('infohash1', predicate=Predicate.HAS_TAG) == ['tag3', 'tag2']
        assert self.db.get_objects('infohash1', predicate=Predicate.HAS_CONTRIBUTOR) == ['Contributor']

    @db_session
    async def test_get_objects_removed(self):
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1', count=SHOW_THRESHOLD, predicate=Predicate.HAS_TAG),
                    Resource(name='tag2', count=SHOW_THRESHOLD, predicate=Predicate.HAS_TAG)
                ]
            }
        )

        self.add_operation(self.db, subject='infohash1', predicate=Predicate.HAS_TAG, object='tag2', peer=b'4',
                           operation=Operation.REMOVE)

        assert self.db.get_objects('infohash1', predicate=Predicate.HAS_TAG) == ['tag1']

    @db_session
    async def test_show_local_resources(self):
        # Test that locally added tags have a priority to show.
        # That means no matter of other peers opinions, locally added tag should be visible.
        self.add_operation(self.db, 'infohash1', Predicate.HAS_TAG, 'tag1', b'peer1', operation=Operation.REMOVE)
        self.add_operation(self.db, 'infohash1', Predicate.HAS_TAG, 'tag1', b'peer2', operation=Operation.REMOVE)
        assert not self.db.get_objects('infohash1', Predicate.HAS_TAG)

        # test local add
        self.add_operation(self.db, 'infohash1', Predicate.HAS_TAG, 'tag1', b'peer3', operation=Operation.ADD,
                           is_local_peer=True)
        self.add_operation(self.db, 'infohash1', Predicate.HAS_CONTRIBUTOR, 'contributor', b'peer3',
                           operation=Operation.ADD, is_local_peer=True)
        assert self.db.get_objects('infohash1', predicate=Predicate.HAS_TAG) == ['tag1']
        assert self.db.get_objects('infohash1', predicate=Predicate.HAS_CONTRIBUTOR) == ['contributor']

    @db_session
    async def test_hide_local_tags(self):
        # Test that locally removed tags should not be visible to local user.
        # No matter of other peers opinions, locally removed tag should be not visible.
        self.add_operation(self.db, 'infohash1', Predicate.HAS_TAG, 'tag1', b'peer1')
        self.add_operation(self.db, 'infohash1', Predicate.HAS_TAG, 'tag1', b'peer2')
        assert self.db.get_objects('infohash1', Predicate.HAS_TAG) == ['tag1']

        # test local remove
        self.add_operation(self.db, 'infohash1', Predicate.HAS_TAG, 'tag1', b'peer3', operation=Operation.REMOVE,
                           is_local_peer=True)
        assert self.db.get_objects('infohash1', Predicate.HAS_TAG) == []

    @db_session
    async def test_suggestions(self):
        # Test whether the database returns the right suggestions.
        # Suggestions are tags that have not gathered enough support for display yet.
        self.add_operation(self.db, subject='subject', predicate=Predicate.HAS_TAG, object='tag1', peer=b'1')
        self.add_operation(self.db, subject='subject', predicate=Predicate.HAS_TAG, object='tag1', peer=b'2')
        self.add_operation(self.db, subject='subject', predicate=Predicate.HAS_CONTRIBUTOR, object='contributor',
                           peer=b'2')

        assert self.db.get_suggestions('subject', predicate=Predicate.HAS_TAG) == []  # This tag now has enough support

        self.add_operation(self.db, subject='subject', predicate=Predicate.HAS_TAG, object='tag1', peer=b'3',
                           operation=Operation.REMOVE)  # score:1
        self.add_operation(self.db, subject='subject', predicate=Predicate.HAS_TAG, object='tag1', peer=b'4',
                           operation=Operation.REMOVE)  # score:0
        assert self.db.get_suggestions('subject', predicate=Predicate.HAS_TAG) == ["tag1"]

        self.add_operation(self.db, subject='subject', predicate=Predicate.HAS_TAG, object='tag1', peer=b'5',
                           operation=Operation.REMOVE)  # score:-1
        self.add_operation(self.db, subject='subject', predicate=Predicate.HAS_TAG, object='tag1', peer=b'6',
                           operation=Operation.REMOVE)  # score:-2
        assert not self.db.get_suggestions('infohash', predicate=Predicate.HAS_TAG)  # below the threshold

    @db_session
    async def test_get_clock_of_operation(self):
        operation = self.create_operation()
        assert self.db.get_clock(operation) == 0

        self.add_operation(self.db, subject=operation.subject, predicate=operation.predicate, object=operation.object,
                           peer=operation.creator_public_key, clock=1)

        assert self.db.get_clock(operation) == 1

    @db_session
    async def test_get_tags_operations_for_gossip(self):
        time_delta = {'minutes': 1}
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1', count=1),
                    Resource(name='tag2', count=1),
                    Resource(name='tag3', count=2, auto_generated=True)
                ]
            }
        )

        # assert that immediately added torrents are not returned
        assert not self.db.get_operations_for_gossip(time_delta)

        # put back in the past two tag: 'tag1' and 'tag3'
        for obj in ['tag1', 'tag3']:
            query = lambda so: so.statement.object.name == obj  # pylint: disable=cell-var-from-loop
            operations = self.db.instance.StatementOp.select(query)
            for operation in operations:
                operation.updated_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=2)

        # assert that only one torrent returned (the old and the not auto generated one)
        assert len(self.db.get_operations_for_gossip(time_delta)) == 1

    # @db_session
    # async def test_get_subjects_threshold(self):
    #     # test that `get_subjects` function returns only infohashes with tags
    #     # above the threshold
    #     self.add_operation_set(
    #         self.db,
    #         {
    #             'infohash1': [
    #                 Resource(name='tag1', count=SHOW_THRESHOLD, predicate=Predicate.HAS_TAG),
    #             ],
    #             'infohash2': [
    #                 Resource(name='tag1', count=SHOW_THRESHOLD - 1, predicate=Predicate.HAS_TAG)
    #             ],
    #             'infohash3': [
    #                 Resource(name='tag1', count=SHOW_THRESHOLD, predicate=Predicate.HAS_CONTRIBUTOR),
    #             ],
    #         }
    #     )
    #
    #     assert self.db.get_subjects({'tag1'}) == [b'infohash1']
    #
    # @db_session
    # async def test_get_infohashes(self):
    #     # test that `get_infohashes` function returns an intersection of result
    #     # in case of more than one tag passed to the function
    #     self.add_operation_set(
    #         self.db,
    #         {
    #             b'infohash1': [
    #                 Tag(name='tag1', count=SHOW_THRESHOLD),
    #                 Tag(name='tag2', count=SHOW_THRESHOLD),
    #                 Tag(name='ContentItem', count=SHOW_THRESHOLD, relation=TagPredicateEnum.HAS_CONTENT_ITEM)
    #             ],
    #             b'infohash2': [
    #                 Tag(name='tag1', count=SHOW_THRESHOLD),
    #                 Tag(name='ContentItem', count=SHOW_THRESHOLD, relation=TagPredicateEnum.HAS_CONTENT_ITEM)
    #             ],
    #             b'infohash3': [
    #                 Tag(name='tag2', count=SHOW_THRESHOLD)
    #             ]
    #         }
    #     )
    #
    #     # no results
    #     assert not self.db.get_subjects({'missed tag'})
    #     assert not self.db.get_subjects({'tag1'}, relation=TagPredicateEnum.HAS_CONTENT_ITEM)
    #
    #     # results
    #     assert self.db.get_subjects({'tag1'}) == [b'infohash1', b'infohash2']
    #     assert self.db.get_subjects({'tag2'}) == [b'infohash1', b'infohash3']
    #     assert self.db.get_subjects({'tag1', 'tag2'}) == [b'infohash1']
    #     assert self.db.get_subjects({'ContentItem'}, relation=TagPredicateEnum.HAS_CONTENT_ITEM) == [b'infohash1',
    #                                                                                                   b'infohash2']
    #
    @db_session
    async def test_show_condition(self):
        assert TagDatabase._show_condition(SimpleNamespace(local_operation=Operation.ADD))
        assert TagDatabase._show_condition(SimpleNamespace(local_operation=None, score=SHOW_THRESHOLD))
        assert not TagDatabase._show_condition(SimpleNamespace(local_operation=None, score=0))

    @db_session
    async def test_get_random_operations_by_condition_less_than_count(self):
        # Check that `_get_random_tag_operations_by_condition` returns values even in the case that requested amount
        # of operations is unavailable

        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1', count=3, predicate=Predicate.HAS_TAG),  # add 3 StatementOp
                ],
            }
        )

        # request 5 random operations
        random_operations = self.db._get_random_operations_by_condition(
            condition=lambda _: True,
            count=5,
            attempts=100
        )

        assert len(random_operations) == 3

    @db_session
    async def test_get_random_operations_by_condition_greater_than_count(self):
        # Check that `_get_random_tag_operations_by_condition` returns requested amount of entities
        # even if there are more entities in DB than this requested amount.
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1', count=10, predicate=Predicate.HAS_TAG),  # add 10 StatementOp
                ],
            }
        )

        # request 5 random operations
        random_operations = self.db._get_random_operations_by_condition(
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
                'infohash1': [
                    # add 10 autogenerated tags
                    Resource(name='tag1', count=10, auto_generated=True, predicate=Predicate.HAS_TAG),
                    # add 10 normal tags
                    Resource(name='tag2', count=10, auto_generated=False, predicate=Predicate.HAS_TAG),
                ],
            }
        )

        # request 5 normal tags
        random_operations = self.db._get_random_operations_by_condition(
            condition=lambda so: not so.auto_generated,
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
                'infohash1': [
                    # add 10 autogenerated tags
                    Resource(name='tag1', count=10, auto_generated=True, predicate=Predicate.HAS_TAG),
                ],
            }
        )

        # request 5 normal tags
        random_operations = self.db._get_random_operations_by_condition(
            condition=lambda so: not so.auto_generated,
            count=5,
            attempts=100
        )

        # check that only normal tags have been returned
        assert len(random_operations) == 0
