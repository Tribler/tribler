import os
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from ipv8.keyvault.crypto import default_eccrypto
from pony.orm import db_session

from tribler.core.components.database.db.layers.knowledge_data_access_layer import KnowledgeDataAccessLayer, \
    ResourceType, SHOW_THRESHOLD
from tribler.core.components.database.db.layers.tests.test_knowledge_data_access_layer_base import Resource, \
    TestKnowledgeAccessLayerBase
from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.components.ipv8.adapters_tests import TriblerTestBase
from tribler.core.components.metadata_store.db.orm_bindings.channel_node import NEW
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.metadata_store.remote_query_community.remote_query_community import RemoteQueryCommunity
from tribler.core.components.metadata_store.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler.core.components.metadata_store.remote_query_community.tests.test_remote_query_community import (
    BasicRemoteQueryCommunity,
)
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.unicode import hexlify


class TestRemoteSearchByTags(TriblerTestBase):
    """ In this test set we will use only one node's instance as it is sufficient
    for testing remote search by tags
    """

    def setUp(self):
        super().setUp()
        self.metadata_store = None
        self.tribler_db = None
        self.initialize(BasicRemoteQueryCommunity, 1)

    async def tearDown(self):
        if self.metadata_store:
            self.metadata_store.shutdown()
        if self.tribler_db:
            self.tribler_db.shutdown()

        await super().tearDown()

    def create_node(self, *args, **kwargs):
        self.metadata_store = MetadataStore(
            Path(self.temporary_directory()) / "mds.db",
            Path(self.temporary_directory()),
            default_eccrypto.generate_key("curve25519"),
            disable_sync=True,
        )
        self.tribler_db = TriblerDatabase(str(Path(self.temporary_directory()) / "tags.db"))

        kwargs['metadata_store'] = self.metadata_store
        kwargs['tribler_db'] = self.tribler_db
        kwargs['rqc_settings'] = RemoteQueryCommunitySettings()
        return super().create_node(*args, **kwargs)

    @property
    def rqc(self) -> RemoteQueryCommunity:
        return self.overlay(0)

    @patch.object(RemoteQueryCommunity, 'tribler_db', new=PropertyMock(return_value=None), create=True)
    def test_search_for_tags_no_db(self):
        # test that in case of missed `tribler_db`, function `search_for_tags` returns None
        assert self.rqc.search_for_tags(tags=['tag']) is None

    @patch.object(KnowledgeDataAccessLayer, 'get_subjects_intersection')
    def test_search_for_tags_only_valid_tags(self, mocked_get_subjects_intersection: Mock):
        # test that function `search_for_tags` uses only valid tags
        self.rqc.search_for_tags(tags=['invalid_tag' * 50, 'valid_tag'])
        mocked_get_subjects_intersection.assert_called_with(
            subjects_type=ResourceType.TORRENT,
            objects={'valid_tag'},
            predicate=ResourceType.TAG,
            case_sensitive=False
        )

    @patch.object(MetadataStore, 'get_entries_threaded', new_callable=AsyncMock)
    async def test_process_rpc_query_no_tags(self, mocked_get_entries_threaded: AsyncMock):
        # test that in case of missed tags, the remote search works like normal remote search
        parameters = {'first': 0, 'infohash_set': None, 'last': 100}
        await self.rqc.process_rpc_query(parameters)

        expected_parameters = {'infohash_set': None}
        expected_parameters.update(parameters)
        mocked_get_entries_threaded.assert_called_with(**expected_parameters)

    async def test_process_rpc_query_with_tags(self):
        # This is full test that checked whether search by tags works or not
        #
        # Test assumes that two databases were filled by the following data (TagsDatabase and MDS):
        infohash1 = os.urandom(20)
        infohash2 = os.urandom(20)
        infohash3 = os.urandom(20)

        @db_session
        def fill_tags_database():
            TestKnowledgeAccessLayerBase.add_operation_set(
                self.rqc.tribler_db,
                {
                    hexlify(infohash1): [
                        Resource(predicate=ResourceType.TAG, name='tag1', count=SHOW_THRESHOLD),
                    ],
                    hexlify(infohash2): [
                        Resource(predicate=ResourceType.TAG, name='tag1', count=SHOW_THRESHOLD - 1),
                    ]
                }
            )

        @db_session
        def fill_mds():
            with db_session:
                def _add(infohash):
                    torrent = {"infohash": infohash, "title": 'title', "tags": "", "size": 1, "status": NEW}
                    self.rqc.mds.TorrentMetadata.from_dict(torrent)

                _add(infohash1)
                _add(infohash2)
                _add(infohash3)

        fill_tags_database()
        fill_mds()

        # Then we try to query search for three tags: 'tag1', 'tag2', 'tag3'
        parameters = {'first': 0, 'infohash_set': None, 'last': 100, 'tags': ['tag1']}
        with db_session:
            query_results = [r.to_dict() for r in await self.rqc.process_rpc_query(parameters)]

        # Expected results: only one infohash (b'infohash1') should be returned.
        result_infohash_list = [r['infohash'] for r in query_results]
        assert result_infohash_list == [infohash1]
