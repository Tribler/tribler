from json import dumps
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.test.base import TestBase

from pony.orm import db_session

from tribler.core.components.metadata_store.db.orm_bindings.channel_node import NEW
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.metadata_store.remote_query_community.remote_query_community import RemoteQueryCommunity
from tribler.core.components.metadata_store.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler.core.components.metadata_store.remote_query_community.tests.test_remote_query_community import (
    BasicRemoteQueryCommunity,
)
from tribler.core.components.tag.db.tag_db import SHOW_THRESHOLD, TagDatabase
from tribler.core.components.tag.db.tests.test_tag_db import Tag, TestTagDB
from tribler.core.utilities.path_util import Path


class TestRemoteSearchByTags(TestBase):
    """ In this test set we will use only one node's instance as it is sufficient
    for testing remote search by tags
    """

    def setUp(self):
        super().setUp()
        self.metadata_store = None
        self.tags_db = None
        self.initialize(BasicRemoteQueryCommunity, 1)

    async def tearDown(self):
        if self.metadata_store:
            self.metadata_store.shutdown()
        if self.tags_db:
            self.tags_db.shutdown()

        await super().tearDown()

    def create_node(self, *args, **kwargs):
        self.metadata_store = MetadataStore(
            Path(self.temporary_directory()) / "mds.db",
            Path(self.temporary_directory()),
            default_eccrypto.generate_key("curve25519"),
            disable_sync=True,
        )
        self.tags_db = TagDatabase(str(Path(self.temporary_directory()) / "tags.db"))

        kwargs['metadata_store'] = self.metadata_store
        kwargs['tags_db'] = self.tags_db
        kwargs['rqc_settings'] = RemoteQueryCommunitySettings()
        return super().create_node(*args, **kwargs)

    @property
    def rqc(self) -> RemoteQueryCommunity:
        return self.overlay(0)

    @patch.object(RemoteQueryCommunity, 'tags_db', new=PropertyMock(return_value=None), create=True)
    async def test_search_for_tags_no_db(self):
        # test that in case of missed `tags_db`, function `search_for_tags` returns None
        assert self.rqc.search_for_tags(tags=['tag']) is None

    @patch.object(TagDatabase, 'get_infohashes')
    async def test_search_for_tags_only_valid_tags(self, mocked_get_infohashes: Mock):
        # test that function `search_for_tags` uses only valid tags
        self.rqc.search_for_tags(tags=['in', 'valid_tag'])
        mocked_get_infohashes.assert_called_with({'valid_tag'})

    @patch.object(MetadataStore, 'get_entries_threaded', new_callable=AsyncMock)
    async def test_process_rpc_query_no_tags(self, mocked_get_entries_threaded: AsyncMock):
        # test that in case of missed tags, the remote search works like normal remote search
        parameters = {'first': 0, 'infohash_set': None, 'last': 100}
        json = dumps(parameters).encode('utf-8')

        await self.rqc.process_rpc_query(json)

        expected_parameters = {'infohash_set': None}
        expected_parameters.update(parameters)
        mocked_get_entries_threaded.assert_called_with(**expected_parameters)

    async def test_process_rpc_query_with_tags(self):
        # This is full test that checked whether search by tags works or not
        #
        # Test assumes that two databases were filled by the following data (TagsDatabase and MDS):
        @db_session
        def fill_tags_database():
            TestTagDB.add_operation_set(
                self.rqc.tags_db,
                {
                    b'infohash1': [
                        Tag(name='tag1', count=SHOW_THRESHOLD),
                    ],
                    b'infohash2': [
                        Tag(name='tag1', count=SHOW_THRESHOLD - 1),
                    ]
                })

        @db_session
        def fill_mds():
            with db_session:
                def _add(infohash):
                    torrent = {"infohash": infohash, "title": 'title', "tags": "", "size": 1, "status": NEW}
                    self.rqc.mds.TorrentMetadata.from_dict(torrent)

                _add(b'infohash1')
                _add(b'infohash2')
                _add(b'infohash3')

        fill_tags_database()
        fill_mds()

        # Then we try to query search for three tags: 'tag1', 'tag2', 'tag3'
        parameters = {'first': 0, 'infohash_set': None, 'last': 100, 'tags': ['tag1']}
        json = dumps(parameters).encode('utf-8')

        with db_session:
            query_results = [r.to_dict() for r in await self.rqc.process_rpc_query(json)]

        # Expected results: only one infohash (b'infohash1') should be returned.
        result_infohash_list = [r['infohash'] for r in query_results]
        assert result_infohash_list == [b'infohash1']
