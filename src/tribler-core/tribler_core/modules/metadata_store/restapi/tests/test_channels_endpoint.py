import base64
import os
import shutil
import sys
from unittest import skipIf
from unittest.mock import Mock

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.orm_bindings.channel_node import NEW
from tribler_core.modules.metadata_store.restapi.tests.test_metadata_endpoint import BaseTestMetadataEndpoint
from tribler_core.restapi.base_api_test import AbstractApiTest
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities.random_utils import random_infohash
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import succeed


class BaseTestMyChannelEndpoint(BaseTestMetadataEndpoint):
    async def setUp(self):
        await super(BaseTestMyChannelEndpoint, self).setUp()
        self.session.gigachannel_manager = MockObject()
        self.session.gigachannel_manager.shutdown = lambda: succeed(None)
        self.session.gigachannel_manager.updated_my_channel = lambda _: succeed(None)

    def setUpPreSession(self):
        super(BaseTestMyChannelEndpoint, self).setUpPreSession()
        self.config.set_chant_manager_enabled(False)

    def create_my_channel(self):
        with db_session:
            chan = self.session.mds.ChannelMetadata.create_channel('test', 'test')
            for ind in range(5):
                _ = self.session.mds.TorrentMetadata(
                    origin_id=chan.id_, title='torrent%d' % ind, status=NEW, infohash=random_infohash()
                )
            for ind in range(5, 9):
                _ = self.session.mds.TorrentMetadata(
                    origin_id=chan.id_, title='torrent%d' % ind, infohash=random_infohash()
                )

            chan2 = self.session.mds.ChannelMetadata.create_channel('test2', 'test2')
            for ind in range(5):
                _ = self.session.mds.TorrentMetadata(
                    origin_id=chan2.id_, title='torrentB%d' % ind, status=NEW, infohash=random_infohash()
                )
            for ind in range(5, 9):
                _ = self.session.mds.TorrentMetadata(
                    origin_id=chan2.id_, title='torrentB%d' % ind, infohash=random_infohash()
                )
            return chan


class TestChannelsEndpoint(BaseTestMetadataEndpoint):
    async def test_get_channels(self):
        """
        Test whether we can query some channels in the database with the REST API
        """
        json_dict = await self.do_request('channels?sort_by=title')
        self.assertEqual(len(json_dict['results']), 10)

    @skipIf(sys.platform == "darwin", "Skipping this test on Mac due to Pony bug")
    async def test_get_channels_sort_by_health(self):
        json_dict = await self.do_request('channels?sort_by=health')
        self.assertEqual(len(json_dict['results']), 10)

    async def test_get_channels_invalid_sort(self):
        """
        Test whether we can query some channels in the database with the REST API and an invalid sort parameter
        """
        json_dict = await self.do_request('channels?sort_by=fdsafsdf')
        self.assertEqual(len(json_dict['results']), 10)

    async def test_get_subscribed_channels(self):
        """
        Test whether we can successfully query channels we are subscribed to with the REST API
        """
        json_dict = await self.do_request('channels?subscribed=1')
        self.assertEqual(len(json_dict['results']), 5)


class TestChannelsCountEndpoint(BaseTestMetadataEndpoint):
    async def test_get_channels_count(self):
        # Test getting total count of results
        json_dict = await self.do_request('channels?subscribed=1&include_total=1')
        self.assertEqual(json_dict['total'], 5)


class TestSpecificChannelEndpoint(BaseTestMetadataEndpoint):
    async def setUp(self):
        await super(TestSpecificChannelEndpoint, self).setUp()
        self.session.ltmgr = Mock()
        self.session.ltmgr.shutdown = lambda: succeed(True)
        self.session.ltmgr.shutdown_downloads = lambda: succeed(True)
        self.session.ltmgr.checkpoint_downloads = lambda: succeed(True)

    @timeout(10)
    async def test_create_channel(self):
        """
        Test creating a channel in your channel with REST API POST request
        """
        await self.do_request('channels/mychannel/0/channels', request_type='POST', expected_code=200)
        with db_session:
            my_channel = self.session.mds.ChannelMetadata.get(title="New channel")
            self.assertTrue(my_channel)
            self.assertEqual(my_channel.title, 'New channel')

    async def test_get_contents_count(self):
        # Test getting total count of results
        with db_session:
            chan = self.session.mds.ChannelMetadata.select().first()
            json_dict = await self.do_request('channels/%s/123?include_total=1' % hexlify(chan.public_key))
        self.assertEqual(json_dict['total'], 5)

    @timeout(10)
    async def test_get_channel_contents(self):
        """
        Test whether we can query torrents from a channel
        """
        with db_session:
            chan = self.session.mds.ChannelMetadata.select().first()
        json_dict = await self.do_request('channels/%s/123' % hexlify(chan.public_key), expected_code=200)
        self.assertEqual(len(json_dict['results']), 5)
        self.assertIn('status', json_dict['results'][0])

    @timeout(10)
    async def test_get_channel_contents_by_type(self):
        # Test filtering channel contents by a list of data types
        with db_session:
            chan = self.session.mds.ChannelMetadata.select(
                lambda g: g.public_key == database_blob(self.ext_key.pub().key_to_bin()[10:])
            ).first()
            self.session.mds.CollectionNode(title='some_folder', origin_id=chan.id_, sign_with=self.ext_key)

            json_dict = await self.do_request(
                'channels/%s/123?metadata_type=220&metadata_type=300' % hexlify(chan.public_key), expected_code=200
            )
        self.assertEqual(len(json_dict['results']), 6)
        self.assertIn('status', json_dict['results'][0])


class TestSpecificChannelCommitEndpoint(BaseTestMyChannelEndpoint):
    @timeout(10)
    async def test_commit_no_channel(self):
        """
        Test whether we get an error if we try to commit a channel without it being created
        """
        await self.do_request('channels/mychannel/123/commit', expected_code=404, request_type='POST')

    @timeout(10)
    async def test_commit_single_channel(self):
        """
        Test whether we can successfully commit changes to a single personal channel with the REST API
        """
        chan = self.create_my_channel()
        await self.do_request('channels/mychannel/%i/commit' % chan.id_, request_type='POST')

    @timeout(10)
    async def test_commit_all_channels(self):
        """
        Test whether we can successfully commit changes to all personal channels with the REST API
        """
        self.create_my_channel()
        await self.do_request('channels/mychannel/0/commit', request_type='POST')

    @timeout(10)
    async def test_get_commit_state(self):
        """
        Test getting dirty status of a channel through its commit endpoint
        """
        self.create_my_channel()
        await self.do_request('channels/mychannel/0/commit', expected_json={'dirty': True})


class TestSpecificChannelCopyEndpoint(BaseTestMyChannelEndpoint):
    @timeout(10)
    async def test_copy_torrents_to_collection(self):
        """
        Test if we can copy torrents from an external channel(s) to a personal channel/collection
        """
        channel = self.session.mds.ChannelMetadata.create_channel('my chan')
        ext_key = default_eccrypto.generate_key(u"curve25519")
        with db_session:
            external_metadata1 = self.session.mds.TorrentMetadata(
                sign_with=ext_key, id_=111, title="bla1", infohash=random_infohash()
            )
            external_metadata2_ffa = self.session.mds.TorrentMetadata(
                public_key=b"", id_=222, title="bla2-ffa", infohash=random_infohash()
            )

        request_data = [external_metadata1.to_simple_dict(), external_metadata2_ffa.to_simple_dict()]
        await self.do_request(
            'collections/%s/%i/copy' % (hexlify(channel.public_key), channel.id_),
            post_data=request_data,
            request_type='POST',
        )
        with db_session:
            self.assertEqual(len(channel.contents), 2)

        await self.do_request(
            'collections/%s/%i/copy' % (hexlify(b"0" * 64), 777),
            post_data=request_data,
            request_type='POST',
            expected_code=404,
        )

        await self.do_request(
            'collections/%s/%i/copy' % (hexlify(channel.public_key), channel.id_),
            post_data='',
            request_type='POST',
            expected_code=400,
        )

        request_data = [{'public_key': hexlify(b"1" * 64), 'id': 12333}]
        await self.do_request(
            'collections/%s/%i/copy' % (hexlify(channel.public_key), channel.id_),
            post_data=request_data,
            request_type='POST',
            expected_code=400,
        )


class TestSpecificChannelChannelsEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(TestSpecificChannelChannelsEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @timeout(10)
    async def test_create_subchannel_and_collection(self):
        """
        Test if we can create subchannels/collections in a personal channel
        """
        await self.do_request('channels/mychannel/0/channels', request_type='POST', expected_code=200)
        with db_session:
            channel = self.session.mds.ChannelMetadata.get()
            self.assertTrue(channel)
        await self.do_request('channels/mychannel/%i/collections' % channel.id_, request_type='POST', expected_code=200)
        with db_session:
            coll = self.session.mds.CollectionNode.get(lambda g: g.origin_id == channel.id_)
            self.assertTrue(coll)


class TestSpecificChannelTorrentsEndpoint(BaseTestMyChannelEndpoint):
    async def setUp(self):
        await super(TestSpecificChannelTorrentsEndpoint, self).setUp()
        self.session.ltmgr = Mock()
        self.session.ltmgr.shutdown = lambda: succeed(True)
        self.session.ltmgr.shutdown_downloads = lambda: succeed(True)
        self.session.ltmgr.checkpoint_downloads = lambda: succeed(True)

    @timeout(10)
    async def test_add_torrents_no_channel(self):
        """
        Test whether an error is returned when we try to add a torrent to your unexisting channel
        """
        with db_session:
            channel = self.create_my_channel()
            channel.delete()
            await self.do_request(
                'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
                request_type='PUT',
                expected_code=404,
            )

    @timeout(10)
    async def test_add_torrents_no_dir(self):
        """
        Test whether an error is returned when pointing to a file instead of a directory when adding torrents
        """
        channel = self.create_my_channel()
        post_params = {'torrents_dir': 'nonexisting'}
        await self.do_request(
            'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
            request_type='PUT',
            post_data=post_params,
            expected_code=400,
        )

    @timeout(10)
    async def test_add_torrents_recursive_no_dir(self):
        """
        Test whether an error is returned when recursively adding torrents without a specified directory
        """
        channel = self.create_my_channel()
        post_params = {'recursive': True}
        await self.do_request(
            'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
            request_type='PUT',
            post_data=post_params,
            expected_code=400,
        )

    @timeout(10)
    async def test_add_torrents_from_dir(self):
        """
        Test whether adding torrents from a directory to your channels works
        """
        channel = self.create_my_channel()
        post_params = {'torrents_dir': self.session_base_dir, 'recursive': True}
        await self.do_request(
            'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
            request_type='PUT',
            post_data=post_params,
        )

    @timeout(10)
    async def test_add_torrent_missing_torrent(self):
        """
        Test whether an error is returned when adding a torrent to your channel but with a missing torrent parameter
        """
        channel = self.create_my_channel()
        post_params = {}
        await self.do_request(
            'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
            request_type='PUT',
            post_data=post_params,
            expected_code=400,
        )

    @timeout(10)
    async def test_add_invalid_torrent(self):
        """
        Test whether an error is returned when adding an invalid torrent file to your channel
        """
        channel = self.create_my_channel()
        post_params = {'torrent': 'bla'}
        await self.do_request(
            'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
            request_type='PUT',
            post_data=post_params,
            expected_code=500,
        )

    @timeout(10)
    async def test_add_torrent_duplicate(self):
        """
        Test whether adding a duplicate torrent to you channel results in an error
        """
        with db_session:
            channel = self.create_my_channel()
            my_channel = self.session.mds.ChannelMetadata.get_my_channels().first()
            tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
            my_channel.add_torrent_to_channel(tdef, {'description': 'blabla'})

            with open(TORRENT_UBUNTU_FILE, "rb") as torrent_file:
                base64_content = base64.b64encode(torrent_file.read()).decode('utf-8')

                post_params = {'torrent': base64_content}
                await self.do_request(
                    'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
                    request_type='PUT',
                    post_data=post_params,
                    expected_code=500,
                )

    @timeout(10)
    async def test_add_torrent(self):
        """
        Test adding a torrent to your channel
        """
        channel = self.create_my_channel()

        with open(TORRENT_UBUNTU_FILE, "rb") as torrent_file:
            base64_content = base64.b64encode(torrent_file.read())

            post_params = {'torrent': base64_content.decode('utf-8')}
            await self.do_request(
                'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
                request_type='PUT',
                post_data=post_params,
            )

    @timeout(10)
    async def test_add_torrent_invalid_uri(self):
        """
        Test whether adding a torrent to your channel with an invalid URI results in an error
        """
        channel = self.create_my_channel()

        post_params = {'uri': 'thisisinvalid'}
        await self.do_request(
            'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
            request_type='PUT',
            post_data=post_params,
            expected_code=400,
        )

    @timeout(10)
    async def test_add_torrent_from_url(self):
        """
        Test whether we can add a torrent to your channel from an URL
        """
        channel = self.create_my_channel()

        # Setup file server to serve torrent file
        files_path = self.session_base_dir / 'http_torrent_files'
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_UBUNTU_FILE, files_path / 'ubuntu.torrent')
        file_server_port = self.get_port()
        await self.setUpFileServer(file_server_port, files_path)

        post_params = {'uri': 'http://localhost:%d/ubuntu.torrent' % file_server_port}
        await self.do_request(
            'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
            request_type='PUT',
            post_data=post_params,
        )

    @timeout(10)
    async def test_add_torrent_from_magnet(self):
        """
        Test whether we can add a torrent to your channel from a magnet link
        """
        channel = self.create_my_channel()

        def fake_get_metainfo(_, **__):
            meta_info = TorrentDef.load(TORRENT_UBUNTU_FILE).get_metainfo()
            return succeed(meta_info)

        self.session.ltmgr.get_metainfo = fake_get_metainfo

        post_params = {'uri': 'magnet:?fake'}
        await self.do_request(
            'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
            request_type='PUT',
            post_data=post_params,
        )

    @timeout(10)
    async def test_add_torrent_from_magnet_error(self):
        """
        Test whether an error while adding magnets to your channel results in a proper 500 error
        """
        channel = self.create_my_channel()

        def fake_get_metainfo(*_, **__):
            return succeed(None)

        self.session.ltmgr.get_metainfo = fake_get_metainfo

        post_params = {'uri': 'magnet:?fake'}
        await self.do_request(
            'channels/%s/%s/torrents' % (hexlify(channel.public_key), channel.id_),
            request_type='PUT',
            post_data=post_params,
            expected_code=500,
        )

    async def test_get_torrents(self):
        """
        Test whether we can query some torrents in the database with the REST API
        """
        with db_session:
            chan = self.session.mds.ChannelMetadata.select().first()
        json_dict = await self.do_request('channels/%s/123' % hexlify(chan.public_key))
        self.assertEqual(len(json_dict['results']), 5)

    async def test_get_torrents_ffa_channel(self):
        """
        Test whether we can query channel contents for unsigned (legacy/FFA) channels
        """
        with db_session:
            channel = self.session.mds.ChannelMetadata(title='ffa', infohash=random_infohash(), public_key=b"", id_=123)
            self.session.mds.TorrentMetadata(
                public_key=b"", id_=333333, origin_id=channel.id_, title='torrent', infohash=random_infohash()
            )

        def on_response(json_dict):
            self.assertEqual(len(json_dict['results']), 1)

        # We test for both forms of querying null-key channels
        on_response(await self.do_request('channels//123'))
        on_response(await self.do_request('channels/00/123'))
