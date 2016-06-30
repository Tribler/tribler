import json

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class TestTorrentsEndpoint(AbstractApiTest):

    @deferred(timeout=10)
    def test_get_random_torrents(self):
        """
        Testing whether random torrents are returned if random torrents are fetched
        """
        def verify_torrents(results):
            json_results = json.loads(results)
            self.assertEqual(len(json_results['torrents']), 5)

        channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"
        channel_id = channel_db_handler.on_channel_from_dispersy('rand', 42, 'Fancy channel', 'Fancy description')

        torrent_list = []
        for i in xrange(10):
            torrent_list.append([channel_id, 1, 1, (('%s' % i) * 40).decode('hex'), 1460000000,
                                 "ubuntu%d-torrent.iso" % i, [['file%d.txt' % i, 42]], []])
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
