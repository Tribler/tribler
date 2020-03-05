from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

from tribler_core.modules.metadata_store.orm_bindings.channel_node import COMMITTED, TODELETE, UPDATED
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.restapi.base_api_test import AbstractApiTest
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.tests.tools.tools import timeout
from tribler_core.tests.tools.tracker.http_tracker import HTTPTracker
from tribler_core.tests.tools.tracker.udp_tracker import UDPTracker
from tribler_core.utilities.random_utils import random_infohash
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import has_bep33_support, succeed


class BaseTestMetadataEndpoint(AbstractApiTest):
    async def setUp(self):
        await super(BaseTestMetadataEndpoint, self).setUp()
        self.infohashes = []

        torrents_per_channel = 5
        # Add a few channels
        with db_session:
            for ind in range(10):
                self.ext_key = default_eccrypto.generate_key('curve25519')
                channel = self.session.mds.ChannelMetadata(
                    title='channel%d' % ind,
                    subscribed=(ind % 2 == 0),
                    num_entries=torrents_per_channel,
                    infohash=random_infohash(),
                    id_=123,
                    sign_with=self.ext_key,
                )
                for torrent_ind in range(torrents_per_channel):
                    rand_infohash = random_infohash()
                    self.infohashes.append(rand_infohash)
                    self.session.mds.TorrentMetadata(
                        origin_id=channel.id_,
                        title='torrent%d' % torrent_ind,
                        infohash=rand_infohash,
                        sign_with=self.ext_key,
                    )

    def setUpPreSession(self):
        super(BaseTestMetadataEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)


class TestMetadataEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(AbstractApiTest, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @timeout(10)
    async def test_update_multiple_metadata_entries(self):
        """
        Test updating attributes of several metadata entities at once with a PATCH request to REST API
        """
        # Test handling the wrong/empty JSON gracefully
        await self.do_request('metadata', expected_code=400, request_type='PATCH', post_data='')

        # Test trying update a non-existing entry
        await self.do_request(
            'metadata',
            post_data=[{'public_key': hexlify(b'1' * 64), 'id': 111}],
            expected_code=404,
            request_type='PATCH',
        )
        with db_session:
            md1 = self.session.mds.TorrentMetadata(title='old1', infohash=random_infohash())
            md2 = self.session.mds.ChannelMetadata(title='old2', infohash=random_infohash(), subscribed=False)

        NEW_NAME1 = "updated1"
        NEW_NAME2 = "updated2"
        patch_data = [
            {'public_key': hexlify(md1.public_key), 'id': md1.id_, 'title': NEW_NAME1},
            {'public_key': hexlify(md2.public_key), 'id': md2.id_, 'title': NEW_NAME2, 'subscribed': 1},
        ]
        await self.do_request('metadata', post_data=patch_data, expected_code=200, request_type='PATCH')
        with db_session:
            entry1 = self.session.mds.ChannelNode.get(rowid=md1.rowid)
            self.assertEqual(NEW_NAME1, entry1.title)
            self.assertEqual(UPDATED, entry1.status)

            entry2 = self.session.mds.ChannelNode.get(rowid=md2.rowid)
            self.assertEqual(NEW_NAME2, entry2.title)
            self.assertEqual(UPDATED, entry2.status)
            self.assertTrue(entry2.subscribed)

    @timeout(10)
    async def test_delete_multiple_metadata_entries(self):
        """
        Test deleting multiple entries with JSON REST API
        """
        with db_session:
            md1 = self.session.mds.TorrentMetadata(title='old1', infohash=random_infohash())
            md2 = self.session.mds.TorrentMetadata(title='old2', infohash=random_infohash())

        patch_data = [
            {'public_key': hexlify(md1.public_key), 'id': md1.id_},
            {'public_key': hexlify(md2.public_key), 'id': md2.id_},
        ]
        await self.do_request('metadata', post_data=patch_data, expected_code=200, request_type='DELETE')
        with db_session:
            self.assertFalse(self.session.mds.ChannelNode.select().count())


class TestSpecificMetadataEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(AbstractApiTest, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    async def test_update_entry_missing_json(self):
        """
        Test whether an error is returned if we try to change entry with the REST API and missing JSON data
        """
        channel_pk = hexlify(self.session.mds.ChannelNode._my_key.pub().key_to_bin()[10:])
        await self.do_request('metadata/%s/123' % channel_pk, expected_code=400, request_type='PATCH', post_data='')

    async def test_update_entry_not_found(self):
        """
        Test whether an error is returned if we try to change some metadata entry that is not there
        """
        patch_params = {'subscribed': '1'}
        await self.do_request('metadata/aa/123', expected_code=404, request_type='PATCH', post_data=patch_params)

    @timeout(10)
    async def test_update_entry_status_and_name(self):
        """
        Test whether an error is returned if try to modify both the status and name of a torrent
        """
        with db_session:
            chan = self.session.mds.ChannelMetadata.create_channel(title="bla")
        patch_params = {'status': TODELETE, 'title': 'test'}
        await self.do_request(
            'metadata/%s/%i' % (hexlify(chan.public_key), chan.id_),
            request_type='PATCH',
            post_data=patch_params,
            expected_code=400,
        )

    @timeout(10)
    async def test_update_entry(self):
        """
        Test updating a metadata entry with REST API
        """
        new_title = 'bla2'
        new_tags = "Compressed"

        with db_session:
            chan = self.session.mds.ChannelMetadata.create_channel(title="bla")
            chan.status = COMMITTED

        patch_params = {'title': new_title, 'tags': new_tags}

        result = await self.do_request(
            'metadata/%s/%i' % (hexlify(chan.public_key), chan.id_),
            request_type='PATCH',
            post_data=patch_params,
            expected_code=200,
        )
        self.assertEqual(new_title, result['name'])
        self.assertEqual(new_tags, result['category'])
        with db_session:
            chan = self.session.mds.ChannelMetadata.get_my_channels().first()
        self.assertEqual(chan.status, UPDATED)
        self.assertEqual(chan.tags, new_tags)
        self.assertEqual(chan.title, new_title)

    @timeout(10)
    async def test_get_entry(self):
        """
        Test getting an entry with REST API GET request
        """
        with db_session:
            chan = self.session.mds.TorrentMetadata(
                title="bla", infohash=random_infohash(), tracker_info="http://sometracker.local/announce"
            )
            chan.status = COMMITTED
        await self.do_request(
            'metadata/%s/%i' % (hexlify(chan.public_key), chan.id_),
            expected_json=chan.to_simple_dict(include_trackers=True),
        )

    @timeout(10)
    async def test_get_entry_not_found(self):
        """
        Test trying to get a non-existing entry with the REST API GET request
        """
        await self.do_request('metadata/%s/%i' % (hexlify(b"0" * 64), 123), expected_code=404)


class TestTorrentHealthEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(TestTorrentHealthEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    async def setUp(self):
        await super(TestTorrentHealthEndpoint, self).setUp()

        self.udp_port = self.get_port()
        self.udp_tracker = UDPTracker(self.udp_port)

        self.http_port = self.get_port()
        self.http_tracker = HTTPTracker(self.http_port)

    async def tearDown(self):
        self.session.ltmgr = None
        if self.udp_tracker:
            await self.udp_tracker.stop()
        if self.http_tracker:
            await self.http_tracker.stop()
        await super(TestTorrentHealthEndpoint, self).tearDown()

    @timeout(20)
    async def test_check_torrent_health(self):
        """
        Test the endpoint to fetch the health of a chant-managed, infohash-only torrent
        """
        infohash = b'a' * 20
        tracker_url = 'udp://localhost:%s/announce' % self.udp_port
        self.udp_tracker.tracker_info.add_info_about_infohash(infohash, 12, 11, 1)

        with db_session:
            tracker_state = self.session.mds.TrackerState(url=tracker_url)
            torrent_state = self.session.mds.TorrentState(trackers=tracker_state, infohash=infohash)
            self.session.mds.TorrentMetadata(
                infohash=infohash, title='ubuntu-torrent.iso', size=42, tracker_info=tracker_url, health=torrent_state
            )
        url = 'metadata/torrents/%s/health?timeout=10&refresh=1' % hexlify(infohash)

        # Initialize the torrent checker
        self.session.torrent_checker = TorrentChecker(self.session)
        await self.session.torrent_checker.initialize()

        # Add mock DHT response - we both need to account for the case when BEP33 is used and the old lookup method
        self.session.ltmgr = MockObject()
        self.session.ltmgr.get_metainfo = lambda _, **__: succeed(None)
        self.session.ltmgr.dht_health_manager = MockObject()
        dht_health_dict = {"infohash": hexlify(infohash), "seeders": 1, "leechers": 2}
        self.session.ltmgr.dht_health_manager.get_health = lambda *_, **__: succeed({"DHT": [dht_health_dict]})

        # Left for compatibility with other tests in this object
        await self.udp_tracker.start()
        await self.http_tracker.start()
        json_response = await self.do_request(url)
        self.assertIn("health", json_response)
        self.assertIn("udp://localhost:%s" % self.udp_port, json_response['health'])
        if has_bep33_support():
            self.assertIn("DHT", json_response['health'])

        json_response = await self.do_request(url + '&nowait=1')
        self.assertDictEqual(json_response, {u'checking': u'1'})
