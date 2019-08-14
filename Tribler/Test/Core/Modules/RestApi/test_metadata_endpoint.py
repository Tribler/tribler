from __future__ import absolute_import

from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

from six.moves import xrange

from twisted.internet.defer import inlineCallbacks, succeed

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import COMMITTED, TODELETE, UPDATED
from Tribler.Core.TorrentChecker.torrent_checker import TorrentChecker
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.Utilities.random_utils import random_infohash
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Core.Utilities.utilities import has_bep33_support
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.tools import trial_timeout
from Tribler.Test.util.Tracker.HTTPTracker import HTTPTracker
from Tribler.Test.util.Tracker.UDPTracker import UDPTracker


class BaseTestMetadataEndpoint(AbstractApiTest):
    @inlineCallbacks
    def setUp(self):
        yield super(BaseTestMetadataEndpoint, self).setUp()
        self.infohashes = []

        torrents_per_channel = 5
        # Add a few channels
        with db_session:
            for ind in xrange(10):
                key = default_eccrypto.generate_key('curve25519')
                channel = self.session.lm.mds.ChannelMetadata(
                    title='channel%d' % ind,
                    subscribed=(ind % 2 == 0),
                    num_entries=torrents_per_channel,
                    infohash=random_infohash(),
                    id_=123,
                    sign_with=key,
                )
                for torrent_ind in xrange(torrents_per_channel):
                    rand_infohash = random_infohash()
                    self.infohashes.append(rand_infohash)
                    self.session.lm.mds.TorrentMetadata(
                        origin_id=channel.id_, title='torrent%d' % torrent_ind, infohash=rand_infohash, sign_with=key
                    )

    def setUpPreSession(self):
        super(BaseTestMetadataEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)


class TestMetadataEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(AbstractApiTest, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @inlineCallbacks
    @trial_timeout(10)
    def test_update_multiple_metadata_entries(self):
        """
        Test updating attributes of several metadata entities at once with a PATCH request to REST API
        """
        # Test handling the wrong/empty JSON gracefully
        yield self.do_request('metadata', expected_code=400, request_type='PATCH')

        # Test trying update a non-existing entry
        yield self.do_request(
            'metadata',
            raw_data=json.twisted_dumps([{'public_key': hexlify(b'1' * 64), 'id': 111}]),
            expected_code=404,
            request_type='PATCH',
        )
        with db_session:
            md1 = self.session.lm.mds.TorrentMetadata(title='old1', infohash=random_infohash())
            md2 = self.session.lm.mds.ChannelMetadata(title='old2', infohash=random_infohash(), subscribed=False)

        NEW_NAME1 = "updated1"
        NEW_NAME2 = "updated2"
        patch_data = [
            {'public_key': hexlify(md1.public_key), 'id': md1.id_, 'title': NEW_NAME1},
            {'public_key': hexlify(md2.public_key), 'id': md2.id_, 'title': NEW_NAME2, 'subscribed': 1},
        ]
        yield self.do_request(
            'metadata', raw_data=json.twisted_dumps(patch_data), expected_code=200, request_type='PATCH'
        )
        with db_session:
            entry1 = self.session.lm.mds.ChannelNode.get(rowid=md1.rowid)
            self.assertEqual(NEW_NAME1, entry1.title)
            self.assertEqual(UPDATED, entry1.status)

            entry2 = self.session.lm.mds.ChannelNode.get(rowid=md2.rowid)
            self.assertEqual(NEW_NAME2, entry2.title)
            self.assertEqual(UPDATED, entry2.status)
            self.assertTrue(entry2.subscribed)

    @inlineCallbacks
    @trial_timeout(10)
    def test_delete_multiple_metadata_entries(self):
        """
        Test deleting multiple entries with JSON REST API
        """
        with db_session:
            md1 = self.session.lm.mds.TorrentMetadata(title='old1', infohash=random_infohash())
            md2 = self.session.lm.mds.TorrentMetadata(title='old2', infohash=random_infohash())

        patch_data = [
            {'public_key': hexlify(md1.public_key), 'id': md1.id_},
            {'public_key': hexlify(md2.public_key), 'id': md2.id_},
        ]
        yield self.do_request(
            'metadata', raw_data=json.twisted_dumps(patch_data), expected_code=200, request_type='DELETE'
        )
        with db_session:
            self.assertFalse(self.session.lm.mds.ChannelNode.select().count())


class TestSpecificMetadataEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(AbstractApiTest, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    def test_update_entry_missing_json(self):
        """
        Test whether an error is returned if we try to change entry with the REST API and missing JSON data
        """
        channel_pk = hexlify(self.session.lm.mds.ChannelNode._my_key.pub().key_to_bin()[10:])
        return self.do_request('metadata/%s/123' % channel_pk, expected_code=400, request_type='PATCH')

    def test_update_entry_not_found(self):
        """
        Test whether an error is returned if we try to change some metadata entry that is not there
        """
        patch_params = {'subscribed': '1'}
        return self.do_request(
            'metadata/aa/123', expected_code=404, request_type='PATCH', raw_data=json.dumps(patch_params)
        )

    @trial_timeout(10)
    def test_update_entry_status_and_name(self):
        """
        Test whether an error is returned if try to modify both the status and name of a torrent
        """
        with db_session:
            chan = self.session.lm.mds.ChannelMetadata.create_channel(title="bla")
        patch_params = {'status': TODELETE, 'title': 'test'}
        return self.do_request(
            'metadata/%s/%i' % (hexlify(chan.public_key), chan.id_),
            request_type='PATCH',
            raw_data=json.dumps(patch_params),
            expected_code=400,
        )

    @trial_timeout(10)
    def test_update_entry(self):
        """
        Test updating a metadata entry with REST API
        """
        new_title = 'bla2'
        new_tags = "Compressed"

        with db_session:
            chan = self.session.lm.mds.ChannelMetadata.create_channel(title="bla")
            chan.status = COMMITTED

        patch_params = {'title': new_title, 'tags': new_tags}

        @db_session
        def on_response(r):
            result = json.loads(r)
            self.assertEqual(new_title, result['name'])
            self.assertEqual(new_tags, result['category'])
            chan = self.session.lm.mds.ChannelMetadata.get_my_channel()
            self.assertEqual(chan.status, UPDATED)
            self.assertEqual(chan.tags, new_tags)
            self.assertEqual(chan.title, new_title)

        return self.do_request(
            'metadata/%s/%i' % (hexlify(chan.public_key), chan.id_),
            request_type='PATCH',
            raw_data=json.dumps(patch_params),
            expected_code=200,
        ).addCallback(on_response)

    @trial_timeout(10)
    def test_get_entry(self):
        """
        Test getting an entry with REST API GET request
        """
        with db_session:
            chan = self.session.lm.mds.TorrentMetadata(
                title="bla", infohash=random_infohash(), tracker_info="http://sometracker.local/announce"
            )
            chan.status = COMMITTED
        return self.do_request(
            'metadata/%s/%i' % (hexlify(chan.public_key), chan.id_),
            expected_json=chan.to_simple_dict(include_trackers=True),
        )

    @trial_timeout(10)
    def test_get_entry_not_found(self):
        """
        Test trying to get a non-existing entry with the REST API GET request
        """
        return self.do_request('metadata/%s/%i' % (b"0" * 64, 123), expected_code=404)


class TestRandomTorrentsEndpoint(BaseTestMetadataEndpoint):
    def test_get_random_torrents_neg_limit(self):
        """
        Test if an error is returned if we query some random torrents with the REST API and a negative limit
        """
        return self.do_request('metadata/torrents/random?limit=-5', expected_code=400)

    def test_get_random_torrents(self):
        """
        Test whether we can retrieve some random torrents with the REST API
        """

        def on_response(response):
            json_dict = json.twisted_loads(response)
            self.assertEqual(len(json_dict['torrents']), 5)

        return self.do_request('metadata/torrents/random?limit=5').addCallback(on_response)


class TestTorrentHealthEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(TestTorrentHealthEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @inlineCallbacks
    def setUp(self):
        yield super(TestTorrentHealthEndpoint, self).setUp()

        min_base_port, max_base_port = self.get_bucket_range_port()

        self.udp_port = get_random_port(min_port=min_base_port, max_port=max_base_port)
        self.udp_tracker = UDPTracker(self.udp_port)

        self.http_port = get_random_port(min_port=min_base_port, max_port=max_base_port)
        self.http_tracker = HTTPTracker(self.http_port)

    @inlineCallbacks
    def tearDown(self):
        self.session.lm.ltmgr = None
        if self.udp_tracker:
            yield self.udp_tracker.stop()
        if self.http_tracker:
            yield self.http_tracker.stop()
        yield super(TestTorrentHealthEndpoint, self).tearDown()

    @trial_timeout(20)
    @inlineCallbacks
    def test_check_torrent_health(self):
        """
        Test the endpoint to fetch the health of a chant-managed, infohash-only torrent
        """
        infohash = b'a' * 20
        tracker_url = 'udp://localhost:%s/announce' % self.udp_port
        self.udp_tracker.tracker_info.add_info_about_infohash(infohash, 12, 11, 1)

        with db_session:
            tracker_state = self.session.lm.mds.TrackerState(url=tracker_url)
            torrent_state = self.session.lm.mds.TorrentState(trackers=tracker_state, infohash=infohash)
            self.session.lm.mds.TorrentMetadata(
                infohash=infohash, title='ubuntu-torrent.iso', size=42, tracker_info=tracker_url, health=torrent_state
            )
        url = 'metadata/torrents/%s/health?timeout=10&refresh=1' % hexlify(infohash)

        # Initialize the torrent checker
        self.session.lm.torrent_checker = TorrentChecker(self.session)
        self.session.lm.torrent_checker.initialize()

        def verify_response_no_trackers(response):
            json_response = json.twisted_loads(response)
            self.assertIn("health", json_response)
            self.assertIn("udp://localhost:%s" % self.udp_port, json_response['health'])
            if has_bep33_support():
                self.assertIn("DHT", json_response['health'])

        # Add mock DHT response - we both need to account for the case when BEP33 is used and the old lookup method
        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = lambda _, **__: succeed(None)
        self.session.lm.ltmgr.dht_health_manager = MockObject()
        dht_health_dict = {"infohash": hexlify(infohash), "seeders": 1, "leechers": 2}
        self.session.lm.ltmgr.dht_health_manager.get_health = lambda *_, **__: succeed({"DHT": [dht_health_dict]})

        # Left for compatibility with other tests in this object
        self.udp_tracker.start()
        self.http_tracker.start()
        yield self.do_request(url).addCallback(verify_response_no_trackers)

        def verify_response_nowait(response):
            json_response = json.twisted_loads(response)
            self.assertDictEqual(json_response, {u'checking': u'1'})

        yield self.do_request(url + '&nowait=1').addCallback(verify_response_nowait)
