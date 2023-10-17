from types import SimpleNamespace
from unittest.mock import Mock, patch

from pony.orm import commit, db_session

from tribler.core.components.database.db.layers.knowledge_data_access_layer import KnowledgeDataAccessLayer, \
    Operation, PUBLIC_KEY_FOR_AUTO_GENERATED_OPERATIONS, ResourceType, SHOW_THRESHOLD, SimpleStatement
from tribler.core.components.database.db.layers.tests.test_knowledge_data_access_layer_base import Resource, \
    TestKnowledgeAccessLayerBase
from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.utilities.pony_utils import TrackedDatabase, get_or_create


# pylint: disable=protected-access
class TestKnowledgeAccessLayer(TestKnowledgeAccessLayerBase):
    @patch.object(TrackedDatabase, 'generate_mapping')
    @patch.object(TriblerDatabase, 'fill_default_data', Mock())
    def test_constructor_create_tables_true(self, mocked_generate_mapping: Mock):
        """ Test that constructor of TriblerDatabase calls TrackedDatabase.generate_mapping with create_tables=True"""
        TriblerDatabase()

        mocked_generate_mapping.assert_called_with(create_tables=True)

    @patch.object(TrackedDatabase, 'generate_mapping')
    @patch.object(TriblerDatabase, 'fill_default_data', Mock())
    def test_constructor_create_tables_false(self, mocked_generate_mapping: Mock):
        """ Test that constructor of TriblerDatabase calls TrackedDatabase.generate_mapping with create_tables=False"""
        TriblerDatabase(create_tables=False)

        mocked_generate_mapping.assert_called_with(create_tables=False)

    @db_session
    def test_get_or_create(self):
        # Test that function get_or_create() works as expected:
        # it gets an entity if the entity is exist and create the entity otherwise
        assert self.db.Peer.select().count() == 0

        # test create
        peer = get_or_create(self.db.Peer, public_key=b'123')
        commit()
        assert peer.public_key == b'123'
        assert self.db.Peer.select().count() == 1

        # test get
        peer = get_or_create(self.db.Peer, public_key=b'123')
        assert peer.public_key == b'123'
        assert self.db.Peer.select().count() == 1

    @db_session
    def test_update_counter_add(self):
        statement = self.create_statement()

        # let's update ADD counter
        statement.update_counter(Operation.ADD, increment=1)
        assert statement.added_count == 1
        assert statement.removed_count == 0
        assert not statement.local_operation

    @db_session
    def test_update_counter_remove(self):
        statement = self.create_statement()

        # let's update REMOVE counter
        statement.update_counter(Operation.REMOVE, increment=1)
        assert statement.added_count == 0
        assert statement.removed_count == 1
        assert not statement.local_operation

    @db_session
    def test_update_counter_local(self):
        statement = self.create_statement()

        # let's update local operation
        statement.update_counter(Operation.REMOVE, increment=1, is_local_peer=True)
        assert statement.added_count == 0
        assert statement.removed_count == 1
        assert statement.local_operation == Operation.REMOVE

    @db_session
    def test_remote_add_tag_operation(self):
        def assert_all_tables_have_the_only_one_entity():
            assert self.db.Peer.select().count() == 1
            assert self.db.Resource.select().count() == 2
            assert self.db.Statement.select().count() == 1
            assert self.db.StatementOp.select().count() == 1

        # add the first operation
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash', ResourceType.TAG, 'tag', b'peer1')
        assert_all_tables_have_the_only_one_entity()

        # add the same operation
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash', ResourceType.TAG, 'tag', b'peer1')
        assert_all_tables_have_the_only_one_entity()

        # add an operation from the past
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash', ResourceType.TAG, 'tag', b'peer1', clock=0)
        assert_all_tables_have_the_only_one_entity()

        # add a duplicate operation but from the future
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash', ResourceType.TAG, 'tag', b'peer1', clock=1000)
        assert_all_tables_have_the_only_one_entity()

        assert self.db.StatementOp.get().operation == Operation.ADD
        assert self.db.Statement.get().added_count == 1
        assert self.db.Statement.get().removed_count == 0

        # add a unique operation from the future
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash', ResourceType.TAG, 'tag', b'peer1',
                           operation=Operation.REMOVE, clock=1001)
        assert_all_tables_have_the_only_one_entity()
        assert self.db.StatementOp.get().operation == Operation.REMOVE
        assert self.db.Statement.get().added_count == 0
        assert self.db.Statement.get().removed_count == 1

    @db_session
    def test_resource_type(self):
        # Test that resources with different type are stored in separated db entities.
        def resources():
            """get all resources from self.db.Resource and convert them to the tuples:
            (type, name)
            """
            db_entities = self.db.Resource.select()
            return [(r.type, r.name) for r in db_entities]

        # Add operations for two peers with the 'infohash' and `tag`
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash', ResourceType.TAG, 'tag', b'peer1')
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash', ResourceType.TAG, 'tag', b'peer2')
        # Assert that it is only two resources are presented in the DB
        assert resources() == [(ResourceType.TORRENT, 'infohash'),
                               (ResourceType.TAG, 'tag')]

        # Add the operation with the 'infohash' and `tag` but with intentionally reversed types. Therefore two others
        # Resource entities should be added.
        self.add_operation(self.db, ResourceType.TORRENT, 'tag', ResourceType.TAG, 'infohash', b'peer2')
        # Assert that now there are four resources are presented in the DB
        assert resources() == [(ResourceType.TORRENT, 'infohash'),
                               (ResourceType.TAG, 'tag'),
                               (ResourceType.TORRENT, 'tag'),
                               (ResourceType.TAG, 'infohash')]

    @db_session
    def test_remote_add_multiple_tag_operations(self):
        def _get_statement(t: ResourceType):
            resources = list(self.db.Resource.select(type=t))
            return list(resources[0].object_statements).pop()

        self.add_operation(self.db, subject='infohash', obj='tag', peer=b'peer1')
        self.add_operation(self.db, subject='infohash', obj='tag', peer=b'peer2')

        assert _get_statement(ResourceType.TAG).added_count == 2
        assert _get_statement(ResourceType.TAG).removed_count == 0

        self.add_operation(self.db, subject='infohash', obj='tag', peer=b'peer1', operation=Operation.REMOVE)
        assert _get_statement(ResourceType.TAG).added_count == 1
        assert _get_statement(ResourceType.TAG).removed_count == 1

        self.add_operation(self.db, subject='infohash', obj='tag', peer=b'peer2', operation=Operation.REMOVE)
        assert _get_statement(ResourceType.TAG).added_count == 0
        assert _get_statement(ResourceType.TAG).removed_count == 2

        self.add_operation(self.db, subject='infohash', obj='tag', peer=b'peer1')
        assert _get_statement(ResourceType.TAG).added_count == 1
        assert _get_statement(ResourceType.TAG).removed_count == 1

    @db_session
    def test_add_auto_generated_tag(self):
        self.db.knowledge.add_auto_generated_operation(
            subject_type=ResourceType.TORRENT,
            subject='infohash',
            predicate=ResourceType.TAG,
            obj='tag'
        )

        assert self.db.StatementOp.get().auto_generated
        assert self.db.Statement.get().added_count == SHOW_THRESHOLD
        assert self.db.Peer.get().public_key == PUBLIC_KEY_FOR_AUTO_GENERATED_OPERATIONS

    @db_session
    def test_double_add_auto_generated_tag(self):
        """ Test that adding the same auto-generated tag twice will not create a new Statement entity."""
        kwargs = {
            'subject_type': ResourceType.TORRENT,
            'subject': 'infohash',
            'predicate': ResourceType.TAG,
            'obj': 'tag'
        }
        self.db.knowledge.add_auto_generated_operation(**kwargs)
        self.db.knowledge.add_auto_generated_operation(**kwargs)

        assert len(self.db.Statement.select()) == 1
        assert self.db.Statement.get().added_count == SHOW_THRESHOLD

    @db_session
    def test_multiple_tags(self):
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1', count=2),
                    Resource(name='tag2', count=2),
                    Resource(name='tag3', count=1),
                ],
                'infohash2': [
                    Resource(name='tag1', count=1),
                    Resource(name='tag2', count=1),
                    Resource(name='tag4', count=1),
                    Resource(name='tag5', count=1),
                    Resource(name='tag6', count=1),
                ]
            }
        )

        assert self.db.Statement.select().count() == 8
        assert self.db.Resource.select().count() == 8
        assert self.db.StatementOp.select().count() == 10

        infohash1 = self.db.Resource.get(name='infohash1')
        tag1 = self.db.Resource.get(name='tag1')
        statement = self.db.Statement.get(subject=infohash1, object=tag1)
        assert statement.added_count == 2
        assert statement.removed_count == 0

    @db_session
    def test_get_objects_added(self):
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1', count=SHOW_THRESHOLD - 1, ),
                    Resource(name='tag2', count=SHOW_THRESHOLD),
                    Resource(name='tag3', count=SHOW_THRESHOLD + 1),
                    Resource(predicate=ResourceType.CONTRIBUTOR, name='Contributor', count=SHOW_THRESHOLD + 1),
                ]
            }
        )

        assert not self.db.knowledge.get_objects(subject='missed infohash', predicate=ResourceType.TAG)
        assert self.db.knowledge.get_objects(subject='infohash1', predicate=ResourceType.TAG) == ['tag3', 'tag2']
        assert self.db.knowledge.get_objects(subject='infohash1', predicate=ResourceType.CONTRIBUTOR) == ['Contributor']

    @db_session
    def test_get_objects_removed(self):
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1'),
                    Resource(name='tag2')
                ]
            }
        )

        self.add_operation(self.db, subject='infohash1', predicate=ResourceType.TAG, obj='tag2', peer=b'4',
                           operation=Operation.REMOVE)

        assert self.db.knowledge.get_objects(subject='infohash1', predicate=ResourceType.TAG) == ['tag1']

    @db_session
    def test_get_objects_case_insensitive(self):
        # Test that for case-sensitive queries the result is the exact match.
        # Test that for case-insensitive queries the result is the case-insensitive match.

        torrent = ResourceType.TORRENT
        self.add_operation_set(
            self.db,
            {
                'ubuntu': [
                    Resource(predicate=torrent, name='torrent'),
                ],
                'Ubuntu': [
                    Resource(predicate=torrent, name='Torrent'),
                ],
                'UBUNTU': [
                    Resource(predicate=torrent, name='TORRENT'),
                ]
            }
        )

        all_torrents = ['torrent', 'Torrent', 'TORRENT']
        assert self.db.knowledge.get_objects(subject='ubuntu', predicate=torrent, case_sensitive=False) == all_torrents
        assert self.db.knowledge.get_objects(subject='Ubuntu', predicate=torrent, case_sensitive=False) == all_torrents

        assert self.db.knowledge.get_objects(subject='ubuntu', predicate=torrent, case_sensitive=True) == ['torrent']
        assert self.db.knowledge.get_objects(subject='Ubuntu', predicate=torrent, case_sensitive=True) == ['Torrent']

        all_ubuntu = ['ubuntu', 'Ubuntu', 'UBUNTU']
        assert self.db.knowledge.get_subjects(obj='torrent', predicate=torrent, case_sensitive=False) == all_ubuntu
        assert self.db.knowledge.get_subjects(obj='Torrent', predicate=torrent, case_sensitive=False) == all_ubuntu

        assert self.db.knowledge.get_subjects(obj='torrent', predicate=torrent, case_sensitive=True) == ['ubuntu']
        assert self.db.knowledge.get_subjects(obj='Torrent', predicate=torrent, case_sensitive=True) == ['Ubuntu']

    @db_session
    def test_show_local_resources(self):
        # Test that locally added tags have a priority to show.
        # That means no matter of other peers opinions, locally added tag should be visible.
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash1', ResourceType.TAG, 'tag1', b'peer1',
                           operation=Operation.REMOVE)
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash1', ResourceType.TAG, 'tag1', b'peer2',
                           operation=Operation.REMOVE)
        assert not self.db.knowledge.get_objects(subject='infohash1', predicate=ResourceType.TAG)

        # test local add
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash1', ResourceType.TAG, 'tag1', b'peer3',
                           operation=Operation.ADD,
                           is_local_peer=True)
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash1', ResourceType.CONTRIBUTOR, 'contributor',
                           b'peer3',
                           operation=Operation.ADD, is_local_peer=True)
        assert self.db.knowledge.get_objects(subject='infohash1', predicate=ResourceType.TAG) == ['tag1']
        assert self.db.knowledge.get_objects(subject='infohash1', predicate=ResourceType.CONTRIBUTOR) == ['contributor']

    @db_session
    def test_hide_local_tags(self):
        # Test that locally removed tags should not be visible to local user.
        # No matter of other peers opinions, locally removed tag should be not visible.
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash1', ResourceType.TAG, 'tag1', b'peer1')
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash1', ResourceType.TAG, 'tag1', b'peer2')
        assert self.db.knowledge.get_objects(subject='infohash1', predicate=ResourceType.TAG) == ['tag1']

        # test local remove
        self.add_operation(self.db, ResourceType.TORRENT, 'infohash1', ResourceType.TAG, 'tag1', b'peer3',
                           operation=Operation.REMOVE,
                           is_local_peer=True)
        assert self.db.knowledge.get_objects(subject='infohash1', predicate=ResourceType.TAG) == []

    @db_session
    def test_suggestions(self):
        # Test whether the database returns the right suggestions.
        # Suggestions are tags that have not gathered enough support for display yet.
        self.add_operation(self.db, subject='subject', predicate=ResourceType.TAG, obj='tag1', peer=b'1')
        self.add_operation(self.db, subject='subject', predicate=ResourceType.TAG, obj='tag1', peer=b'2')
        self.add_operation(self.db, subject='subject', predicate=ResourceType.CONTRIBUTOR, obj='contributor',
                           peer=b'2')

        assert self.db.knowledge.get_suggestions(subject='subject',
                                                 predicate=ResourceType.TAG) == []  # This tag now has enough support

        self.add_operation(self.db, subject='subject', predicate=ResourceType.TAG, obj='tag1', peer=b'3',
                           operation=Operation.REMOVE)  # score:1
        self.add_operation(self.db, subject='subject', predicate=ResourceType.TAG, obj='tag1', peer=b'4',
                           operation=Operation.REMOVE)  # score:0
        assert self.db.knowledge.get_suggestions(subject='subject', predicate=ResourceType.TAG) == ["tag1"]

        self.add_operation(self.db, subject='subject', predicate=ResourceType.TAG, obj='tag1', peer=b'5',
                           operation=Operation.REMOVE)  # score:-1
        self.add_operation(self.db, subject='subject', predicate=ResourceType.TAG, obj='tag1', peer=b'6',
                           operation=Operation.REMOVE)  # score:-2
        assert not self.db.knowledge.get_suggestions(subject='infohash',
                                                     predicate=ResourceType.TAG)  # below the threshold

    @db_session
    def test_get_clock_of_operation(self):
        operation = self.create_operation()
        assert self.db.knowledge.get_clock(operation) == 0

        self.add_operation(self.db, subject=operation.subject, predicate=operation.predicate, obj=operation.object,
                           peer=operation.creator_public_key, clock=1)

        assert self.db.knowledge.get_clock(operation) == 1

    @db_session
    def test_get_tags_operations_for_gossip(self):
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1', count=1),
                    Resource(name='tag2', count=1),
                    Resource(name='tag3', count=1),
                    Resource(name='tag4', count=2, auto_generated=True),
                    Resource(name='tag5', count=2, auto_generated=True)
                ]
            }
        )

        operations = self.db.knowledge.get_operations_for_gossip(count=2)
        assert len(operations) == 2
        assert all(not o.auto_generated for o in operations)

    @db_session
    def test_get_subjects_intersection_threshold(self):
        # test that `get_subjects_intersection` function returns only infohashes with tags
        # above the threshold
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(predicate=ResourceType.TAG, name='tag1', count=SHOW_THRESHOLD),
                ],
                'infohash2': [
                    Resource(predicate=ResourceType.TAG, name='tag1', count=SHOW_THRESHOLD - 1)
                ],
                'infohash3': [
                    Resource(predicate=ResourceType.TAG, name='tag1', count=SHOW_THRESHOLD),
                ],
            }
        )

        actual = self.db.knowledge.get_subjects_intersection(
            subjects_type=ResourceType.TORRENT,
            objects={'tag1'},
            predicate=ResourceType.TAG
        )
        assert actual == {'infohash1', 'infohash3'}

    @db_session
    def test_get_subjects_intersection(self):
        # test that `get_infohashes` function returns an intersection of result
        # in case of more than one tag passed to the function
        self.add_operation_set(
            self.db,
            {
                ('zero', ResourceType.TITLE): [
                    # It should not appear in the results due to the differing subject type, although it possesses all
                    # the necessary tags.
                    Resource(name='tag1'),
                    Resource(name='tag2'),
                ],
                'infohash1': [
                    Resource(name='tag1'),
                    Resource(name='tag2'),
                    Resource(predicate=ResourceType.CONTRIBUTOR, name='Contributor')
                ],
                'infohash2': [
                    Resource(name='tag1'),
                    Resource(predicate=ResourceType.CONTRIBUTOR, name='Contributor')
                ],
                'infohash3': [
                    Resource(name='tag2')
                ],
                'infohash4': [
                    Resource(name='TAG1'),
                    Resource(name='TAG2'),
                ],
            }
        )

        # no results
        def _results(objects, predicate=ResourceType.TAG, case_sensitive=True):
            results = self.db.knowledge.get_subjects_intersection(
                subjects_type=ResourceType.TORRENT,
                objects=objects,
                predicate=predicate,
                case_sensitive=case_sensitive
            )
            return results

        assert not _results({'missed tag'})
        assert not _results({'tag1'}, ResourceType.CONTRIBUTOR)

        # results
        assert _results({'tag1'}) == {'infohash1', 'infohash2'}
        assert _results({'tag2'}) == {'infohash1', 'infohash3'}
        assert _results({'tag1', 'tag2'}) == {'infohash1'}
        assert _results({'Contributor'}, predicate=ResourceType.CONTRIBUTOR) == {'infohash1', 'infohash2'}

        # case insensitive
        assert _results({'tag1'}, case_sensitive=False) == {'infohash1', 'infohash2', 'infohash4'}
        assert _results({'tag1', 'tag2'}, case_sensitive=False) == {'infohash1', 'infohash4'}

    @db_session
    def test_show_condition(self):
        assert KnowledgeDataAccessLayer._show_condition(SimpleNamespace(local_operation=Operation.ADD))
        assert KnowledgeDataAccessLayer._show_condition(SimpleNamespace(local_operation=None, score=SHOW_THRESHOLD))
        assert not KnowledgeDataAccessLayer._show_condition(SimpleNamespace(local_operation=None, score=0))

    @db_session
    def test_get_random_operations_by_condition_less_than_count(self):
        # Check that `_get_random_tag_operations_by_condition` returns values even in the case that requested amount
        # of operations is unavailable

        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1', count=3),  # add 3 StatementOp
                ],
            }
        )

        # request 5 random operations
        random_operations = self.db.knowledge._get_random_operations_by_condition(
            condition=lambda _: True,
            count=5,
            attempts=100
        )

        assert len(random_operations) == 3

    @db_session
    def test_get_random_operations_by_condition_greater_than_count(self):
        # Check that `_get_random_tag_operations_by_condition` returns requested amount of entities
        # even if there are more entities in DB than this requested amount.
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(name='tag1', count=10),  # add 10 StatementOp
                ],
            }
        )

        # request 5 random operations
        random_operations = self.db.knowledge._get_random_operations_by_condition(
            condition=lambda _: True,
            count=5,
            attempts=100
        )

        assert len(random_operations) == 5

    @db_session
    def test_get_random_tag_operations_by_condition(self):
        # Check that `_get_random_tag_operations_by_condition` uses a passed condition.

        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    # add 10 autogenerated tags
                    Resource(name='tag1', count=10, auto_generated=True),
                    # add 10 normal tags
                    Resource(name='tag2', count=10, auto_generated=False),
                ],
            }
        )

        # request 5 normal tags
        random_operations = self.db.knowledge._get_random_operations_by_condition(
            condition=lambda so: not so.auto_generated,
            count=5,
            attempts=100
        )

        # check that only normal tags have been returned
        assert len(random_operations) == 5
        assert all(not o.auto_generated for o in random_operations)

    @db_session
    def test_get_random_tag_operations_by_condition_no_results(self):
        # test the case when the database is not empty but no operations satisfy
        # the condition. The result should be empty.

        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    # add 10 autogenerated tags
                    Resource(name='tag1', count=10, auto_generated=True),
                ],
            }
        )

        # request 5 normal tags
        random_operations = self.db.knowledge._get_random_operations_by_condition(
            condition=lambda so: not so.auto_generated,
            count=5,
            attempts=100
        )

        # check that only normal tags have been returned
        assert len(random_operations) == 0

    @db_session
    def test_get_subjects(self):
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(predicate=ResourceType.CONTENT_ITEM, name='ubuntu', auto_generated=True),
                    Resource(predicate=ResourceType.TAG, name='linux', auto_generated=True),
                ],
                'infohash2': [
                    Resource(predicate=ResourceType.CONTENT_ITEM, name='ubuntu', auto_generated=True),
                    Resource(predicate=ResourceType.TAG, name='linux', auto_generated=True),
                ],
                'infohash3': [
                    Resource(predicate=ResourceType.CONTENT_ITEM, name='debian', auto_generated=True),
                    Resource(predicate=ResourceType.TAG, name='linux', auto_generated=True),
                ],
            }
        )

        actual = self.db.knowledge.get_subjects(subject_type=ResourceType.TORRENT, predicate=ResourceType.CONTENT_ITEM,
                                                obj='missed')
        assert actual == []

        actual = self.db.knowledge.get_subjects(subject_type=ResourceType.TORRENT, predicate=ResourceType.CONTENT_ITEM,
                                                obj='ubuntu')
        assert actual == ['infohash1', 'infohash2']

        actual = self.db.knowledge.get_subjects(subject_type=ResourceType.TORRENT, predicate=ResourceType.TAG,
                                                obj='linux')
        assert actual == ['infohash1', 'infohash2', 'infohash3']

    @db_session
    def test_get_statements(self):
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(predicate=ResourceType.CONTENT_ITEM, name='ubuntu', auto_generated=True),
                    Resource(predicate=ResourceType.TYPE, name='linux', auto_generated=True),
                ],
                'infohash2': [
                    Resource(predicate=ResourceType.CONTENT_ITEM, name='debian', auto_generated=True),
                    Resource(predicate=ResourceType.TYPE, name='linux', auto_generated=True),
                ],
                'INFOHASH1': [
                    Resource(predicate=ResourceType.TYPE, name='case_insensitive', auto_generated=True),
                ]
            }
        )

        expected = [
            SimpleStatement(subject_type=ResourceType.TORRENT, subject='infohash1', predicate=ResourceType.CONTENT_ITEM,
                            object='ubuntu'),
            SimpleStatement(subject_type=ResourceType.TORRENT, subject='infohash1', predicate=ResourceType.TYPE,
                            object='linux')
        ]
        assert self.db.knowledge.get_statements(subject='infohash1') == expected

        expected.append(
            SimpleStatement(subject_type=ResourceType.TORRENT, subject='INFOHASH1', predicate=ResourceType.TYPE,
                            object='case_insensitive'))
        assert self.db.knowledge.get_statements(subject='infohash1', case_sensitive=False) == expected

    @db_session
    def test_various_queries(self):
        self.add_operation_set(
            self.db,
            {
                'infohash1': [
                    Resource(predicate=ResourceType.CONTENT_ITEM, name='ubuntu'),
                    Resource(predicate=ResourceType.TYPE, name='linux'),
                ],
                'infohash2': [
                    Resource(predicate=ResourceType.CONTENT_ITEM, name='debian'),
                    Resource(predicate=ResourceType.TYPE, name='linux'),
                ],
                'infohash3': [
                    Resource(predicate=ResourceType.TAG, name='linux'),
                ]
            }
        )

        self.add_operation(self.db, subject_type=ResourceType.TAG, subject='infohash1', predicate=ResourceType.CREATOR,
                           obj='creator', counter_increment=SHOW_THRESHOLD)

        # queries
        def _objects(subject_type=None, subject='', predicate=None):
            return set(self.db.knowledge.get_objects(subject_type=subject_type, subject=subject, predicate=predicate))

        assert _objects(subject='infohash1') == {'ubuntu', 'linux', 'creator'}
        assert _objects(subject_type=ResourceType.TORRENT) == {'ubuntu', 'linux', 'debian'}
        assert _objects(subject_type=ResourceType.TORRENT, subject='infohash1') == {'ubuntu', 'linux'}

        actual = _objects(subject_type=ResourceType.TORRENT, subject='infohash1', predicate=ResourceType.TYPE)
        assert actual == {'linux'}

        def _subjects(subject_type=None, obj='', predicate=None):
            return set(self.db.knowledge.get_subjects(subject_type=subject_type, predicate=predicate, obj=obj))

        assert _subjects(obj='linux') == {'infohash1', 'infohash2', 'infohash3'}
        assert _subjects(predicate=ResourceType.TAG, obj='linux') == {'infohash3'}
        assert _subjects(predicate=ResourceType.CONTENT_ITEM) == {'infohash1', 'infohash2'}
