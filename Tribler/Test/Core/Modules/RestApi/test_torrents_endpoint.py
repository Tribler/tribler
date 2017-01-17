import json
import time
from twisted.internet.defer import inlineCallbacks
from Tribler.Core.TorrentChecker.torrent_checker import TorrentChecker
from Tribler.Core.Utilities.network_utils import get_random_port

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, NTFY_TORRENTS
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.util.Tracker.HTTPTracker import HTTPTracker
from Tribler.Test.util.Tracker.UDPTracker import UDPTracker
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTorrentsEndpoint(AbstractApiTest):

    @deferred(timeout=10)
    def test_get_random_torrents(self):
        """
        Testing whether random torrents are returned if random torrents are fetched
        """
        def verify_torrents(results):
            json_results = json.loads(results)
            self.assertEqual(len(json_results['torrents']), 2)

        channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"
        channel_id = channel_db_handler.on_channel_from_dispersy('rand', 42, 'Fancy channel', 'Fancy description')

        torrent_list = [
            [channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso", [['file1.txt', 42]], []],
            [channel_id, 2, 2, ('b' * 40).decode('hex'), 1470000000, "ubuntu2-torrent.iso", [['file2.txt', 42]], []],
            [channel_id, 3, 3, ('c' * 40).decode('hex'), 1480000000, "badterm", [['file1.txt', 42]], []],
            [channel_id, 4, 4, ('d' * 40).decode('hex'), 1490000000, "badterm", [['file2.txt', 42]], []],
            [channel_id, 5, 5, ('e' * 40).decode('hex'), 1500000000, "badterm", [['file3.txt', 42]], []],
        ]
        channel_db_handler.on_torrents_from_dispersy(torrent_list)

        self.should_check_equality = False
        return self.do_request('torrents/random?limit=5', expected_code=200).addCallback(verify_torrents)

    @deferred(timeout=10)
    def test_random_torrents_negative(self):
        """
        Testing whether error 400 is returned when a negative limit is passed to the request to fetch random torrents
        """
        expected_json = {"error": "the limit parameter must be a positive number"}
        return self.do_request('torrents/random?limit=-5', expected_code=400, expected_json=expected_json)


class TestTorrentHealthEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestTorrentHealthEndpoint, self).setUp(autoload_discovery=autoload_discovery)

        min_base_port, max_base_port = self.get_bucket_range_port()

        self.udp_port = get_random_port(min_port=min_base_port, max_port=max_base_port)
        self.udp_tracker = UDPTracker(self.udp_port)

        self.http_port = get_random_port(min_port=min_base_port, max_port=max_base_port)
        self.http_tracker = HTTPTracker(self.http_port)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.session.lm.ltmgr = None
        yield self.udp_tracker.stop()
        yield self.http_tracker.stop()
        yield super(TestTorrentHealthEndpoint, self).tearDown(annotate=annotate)

    @deferred(timeout=20)
    @inlineCallbacks
    def test_check_torrent_health(self):
        """
        Test the endpoint to fetch the health of a torrent
        """
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db.addExternalTorrentNoDef('a' * 20, 'ubuntu-torrent.iso', [['file1.txt', 42]],
                                           ('udp://localhost:%s/announce' % self.udp_port,
                                            'http://localhost:%s/announce' % self.http_port), time.time())

        url = 'torrents/%s/health?timeout=10&refresh=1' % ('a' * 20).encode('hex')

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
            json_response = json.loads(response)
            expected_dict = {u"health":
                                 {u"DHT":
                                      {u"leechers": 2, u"seeders": 1, u"infohash": (u'a' * 20).encode('hex')},
                                  u"udp://localhost:%s" % self.udp_port:
                                      {u"leechers": 20, u"seeders": 10, u"infohash": (u'a' * 20).encode('hex')},
                                  u"http://localhost:%s/announce" % self.http_port:
                                      {u"leechers": 30, u"seeders": 20, u"infohash": (u'a' * 20).encode('hex')}}}
            self.assertDictEqual(json_response, expected_dict)

        yield self.do_request(url, expected_code=200, request_type='GET').addCallback(verify_response_no_trackers)

        self.udp_tracker.start()
        self.udp_tracker.tracker_info.add_info_about_infohash('a' * 20, 10, 20)

        self.http_tracker.start()
        self.http_tracker.tracker_info.add_info_about_infohash('a' * 20, 20, 30)

        yield self.do_request(url, expected_code=200, request_type='GET').addCallback(verify_response_with_trackers)
