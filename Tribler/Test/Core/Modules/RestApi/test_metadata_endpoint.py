import json
from binascii import hexlify

import six
from six.moves import xrange

from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.TorrentChecker.torrent_checker import TorrentChecker
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.Utilities.random_utils import random_infohash
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import trial_timeout
from Tribler.Test.util.Tracker.HTTPTracker import HTTPTracker
from Tribler.Test.util.Tracker.UDPTracker import UDPTracker
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


class BaseTestMetadataEndpoint(AbstractApiTest):

    @inlineCallbacks
    def setUp(self):
        yield super(BaseTestMetadataEndpoint, self).setUp()

        # Add a few channels
        with db_session:
            for ind in xrange(10):
                self.session.lm.mds.Metadata._my_key = default_eccrypto.generate_key('low')
                _ = self.session.lm.mds.ChannelMetadata(title='channel%d' % ind, subscribed=(ind % 2 == 0))
                for torrent_ind in xrange(5):
                    _ = self.session.lm.mds.TorrentMetadata(title='torrent%d' % torrent_ind, infohash=random_infohash())

    def setUpPreSession(self):
        super(BaseTestMetadataEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)


class TestChannelsEndpoint(BaseTestMetadataEndpoint):

    def test_get_channels(self):
        """
        Test whether we can query some channels in the database with the REST API
        """
        def on_response(response):
            json_dict = json.loads(response)
            self.assertEqual(len(json_dict['channels']), 10)

        self.should_check_equality = False
        return self.do_request('metadata/channels?sort_by=title', expected_code=200).addCallback(on_response)

    def test_get_channels_invalid_sort(self):
        """
        Test whether we can query some channels in the database with the REST API and an invalid sort parameter
        """
        def on_response(response):
            json_dict = json.loads(response)
            self.assertEqual(len(json_dict['channels']), 10)

        self.should_check_equality = False
        return self.do_request('metadata/channels?sort_by=fdsafsdf', expected_code=200).addCallback(on_response)

    def test_get_subscribed_channels(self):
        """
        Test whether we can successfully query channels we are subscribed to with the REST API
        """
        def on_response(response):
            json_dict = json.loads(response)
            self.assertEqual(len(json_dict['channels']), 5)

        self.should_check_equality = False
        return self.do_request('metadata/channels?subscribed=1', expected_code=200).addCallback(on_response)


class TestSpecificChannelEndpoint(BaseTestMetadataEndpoint):

    def test_subscribe_missing_parameter(self):
        """
        Test whether an error is returned if we try to subscribe to a channel with the REST API and missing parameters
        """
        self.should_check_equality = False
        channel_pk = hexlify(self.session.lm.mds.Metadata._my_key.pub().key_to_bin()[10:])
        return self.do_request('metadata/channels/%s' % channel_pk, expected_code=400, request_type='POST')

    def test_subscribe_no_channel(self):
        """
        Test whether an error is returned if we try to subscribe to a channel with the REST API and a missing channel
        """
        self.should_check_equality = False
        post_params = {'subscribe': '1'}
        return self.do_request('metadata/channels/aa', expected_code=404, request_type='POST', post_data=post_params)

    def test_subscribe(self):
        """
        Test whether we can subscribe to a channel with the REST API
        """
        self.should_check_equality = False
        post_params = {'subscribe': '1'}
        channel_pk = hexlify(self.session.lm.mds.Metadata._my_key.pub().key_to_bin())
        return self.do_request('metadata/channels/%s' % channel_pk, expected_code=200,
                               request_type='POST', post_data=post_params)


class TestSpecificChannelTorrentsEndpoint(BaseTestMetadataEndpoint):

    def test_get_torrents(self):
        """
        Test whether we can query some torrents in the database with the REST API
        """
        def on_response(response):
            json_dict = json.loads(response)
            self.assertEqual(len(json_dict['torrents']), 5)

        self.should_check_equality = False
        channel_pk = hexlify(self.session.lm.mds.Metadata._my_key.pub().key_to_bin())
        return self.do_request('metadata/channels/%s/torrents' % channel_pk, expected_code=200).addCallback(on_response)


class TestPopularChannelsEndpoint(BaseTestMetadataEndpoint):

    def test_get_popular_channels_neg_limit(self):
        """
        Test whether an error is returned if we use a negative value for the limit parameter
        """
        self.should_check_equality = False
        return self.do_request('metadata/channels/popular?limit=-1', expected_code=400)

    def test_get_popular_channels(self):
        """
        Test whether we can retrieve popular channels with the REST API
        """
        def on_response(response):
            json_dict = json.loads(response)
            self.assertEqual(len(json_dict['channels']), 5)

        self.should_check_equality = False
        return self.do_request('metadata/channels/popular?limit=5', expected_code=200).addCallback(on_response)


class TestRandomTorrentsEndpoint(BaseTestMetadataEndpoint):

    def test_get_random_torrents_neg_limit(self):
        """
        Test if an error is returned if we query some random torrents with the REST API and a negative limit
        """
        self.should_check_equality = False
        return self.do_request('metadata/torrents/random?limit=-5', expected_code=400)

    def test_get_random_torrents(self):
        """
        Test whether we can retrieve some random torrents with the REST API
        """
        def on_response(response):
            json_dict = json.loads(response)
            self.assertEqual(len(json_dict['torrents']), 5)

        self.should_check_equality = False
        return self.do_request('metadata/torrents/random?limit=5', expected_code=200).addCallback(on_response)


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
        Test the endpoint to fetch the health of a torrent
        """
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db.addExternalTorrentNoDef('a' * 20, 'ubuntu-torrent.iso', [['file1.txt', 42]],
                                           ('udp://localhost:%s/announce' % self.udp_port,
                                            'http://localhost:%s/announce' % self.http_port), time.time())

        url = 'metadata/torrents/%s/health?timeout=10&refresh=1' % hexlify(b'a' * 20)

        self.should_check_equality = False
        yield self.do_request(url, expected_code=400, request_type='GET')  # No torrent checker

        def call_cb(infohash, callback, **_):
            callback({"seeders": 1, "leechers": 2})

        # Initialize the torrent checker
        self.session.lm.torrent_checker = TorrentChecker(self.session)
        self.session.lm.torrent_checker.initialize()
        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = call_cb

        yield self.do_request('torrents/%s/health' % ('f' * 40), expected_code=404, request_type='GET')

        def verify_response_no_trackers(response):
            json_response = json.loads(response)
            self.assertTrue('DHT' in json_response['health'])

        def verify_response_with_trackers(response):
            hex_as = hexlify(b'a' * 20)
            json_response = json.loads(response)
            expected_dict = {u"health":
                             {u"DHT":
                                  {u"leechers": 2, u"seeders": 1, u"infohash": hex_as},
                              u"udp://localhost:%s" % self.udp_port:
                                  {u"leechers": 20, u"seeders": 10, u"infohash": hex_as},
                              u"http://localhost:%s/announce" % self.http_port:
                                  {u"leechers": 30, u"seeders": 20, u"infohash": hex_as}}}
            self.assertDictEqual(json_response, expected_dict)

        yield self.do_request(url, expected_code=200, request_type='GET').addCallback(verify_response_no_trackers)

        self.udp_tracker.start()
        self.udp_tracker.tracker_info.add_info_about_infohash('a' * 20, 10, 20)

        self.http_tracker.start()
        self.http_tracker.tracker_info.add_info_about_infohash('a' * 20, 20, 30)

        yield self.do_request(url, expected_code=200, request_type='GET').addCallback(verify_response_with_trackers)

    @trial_timeout(20)
    @inlineCallbacks
    def test_check_torrent_health_chant(self):
        """
        Test the endpoint to fetch the health of a chant-managed, infohash-only torrent
        """
        infohash = 'a' * 20
        tracker_url = 'udp://localhost:%s/announce' % self.udp_port

        meta_info = {"info": {"name": "my_torrent", "piece length": 42,
                              "root hash": infohash, "files": [],
                              "url-list": tracker_url}}
        tdef = TorrentDef.load_from_dict(meta_info)

        with db_session:
            self.session.lm.mds.TorrentMetadata(infohash=tdef.infohash,
                                                title='ubuntu-torrent.iso',
                                                size=42,
                                                tracker_info=tracker_url,
                                                health=torrent_state)
        url = 'metadata/torrents/%s/health?timeout=10&refresh=1' % hexlify(infohash)
        self.should_check_equality = False

        # Initialize the torrent checker
        self.session.lm.torrent_checker = TorrentChecker(self.session)
        self.session.lm.torrent_checker.initialize()

        def verify_response_no_trackers(response):
            json_response = json.loads(response)
            expected_dict = {
                u"health": {
                    u"udp://localhost:%d" % self.udp_tracker.port: {
                        u"leechers": 11,
                        u"seeders": 12,
                        u"infohash": six.text_type(hexlify(infohash))
                    }
                }
            }
            self.assertDictEqual(json_response, expected_dict)

        # Left for compatibility with other tests in this object
        self.udp_tracker.start()
        self.http_tracker.start()
        yield self.do_request(url, expected_code=200, request_type='GET').addCallback(verify_response_no_trackers)
