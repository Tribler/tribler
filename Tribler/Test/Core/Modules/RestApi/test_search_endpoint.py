from __future__ import absolute_import

import json
import random

from pony.orm import db_session
from six import unichr
from six.moves import xrange
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.simpledefs import (NTFY_CHANNELCAST, NTFY_TORRENTS, SIGNAL_CHANNEL,
                                     SIGNAL_ON_SEARCH_RESULTS, SIGNAL_TORRENT)
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import trial_timeout
from Tribler.pyipv8.ipv8.database import database_blob


class FakeSearchManager(object):
    """
    This class is used to test whether Tribler starts searching for channels/torrents when a search is performed.
    """

    def __init__(self, notifier):
        self.notifier = notifier

    def search_for_torrents(self, keywords):
        results_dict = {"keywords": keywords, "result_list": []}
        self.notifier.notify(SIGNAL_TORRENT, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)

    def search_for_channels(self, keywords):
        results_dict = {"keywords": keywords, "result_list": []}
        self.notifier.notify(SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)

    def shutdown(self):
        pass


class TestSearchEndpoint(AbstractApiTest):

    def __init__(self, *args, **kwargs):
        super(TestSearchEndpoint, self).__init__(*args, **kwargs)
        self.expected_events_messages = []

    @inlineCallbacks
    def setUp(self):
        yield super(TestSearchEndpoint, self).setUp()
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"
        self.torrent_db_handler = self.session.open_dbhandler(NTFY_TORRENTS)

    def setUpPreSession(self):
        super(TestSearchEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    def insert_channels_in_db(self, num):
        for i in xrange(0, num):
            self.channel_db_handler.on_channel_from_dispersy('rand%d' % i, 42 + i,
                                                             'Test channel %d' % i, 'Test description %d' % i)

    def insert_torrents_in_db(self, num):
        for i in xrange(0, num):
            ih = "".join(unichr(97 + random.randint(0, 15)) for _ in range(0, 20))
            self.torrent_db_handler.addExternalTorrentNoDef(ih.encode('utf-8'), 'hay %d' % i, [('Test.txt', 1337)], [],
                                                            1337)

    @trial_timeout(10)
    @inlineCallbacks
    def test_search_legacy(self):
        """
        Test a search query that should return a few new type channels
        """

        self.insert_channels_in_db(1)
        self.insert_torrents_in_db(100)
        self.torrent_db_handler.addExternalTorrentNoDef(str(unichr(98)) * 20, 'Needle', [('Test.txt', 1337)], [], 1337)
        self.should_check_equality = False

        result = yield self.do_request('search?txt=needle', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["torrents"]), 1)

        result = yield self.do_request('search?txt=hay&first=10&last=20', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["torrents"]), 10)

        """
        torrent_list = [
            [channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso", [['file1.txt', 42]], []],
            [channel_id, 1, 1, ('b' * 40).decode('hex'), 1460000000, "badterm", [['file1.txt', 42]], []]
        ]
        self.insert_torrents_into_channel(torrent_list)
        """

    @trial_timeout(10)
    @inlineCallbacks
    def test_search_chant(self):
        """
        Test a search query that should return a few new type channels
        """

        num_hay = 100
        with db_session:
            my_channel_id = self.session.trustchain_keypair.pub().key_to_bin()
            channel = self.session.lm.mds.ChannelMetadata(public_key=database_blob(my_channel_id), title='test',
                                                          tags='test', subscribed=True)
            for x in xrange(0, num_hay):
                self.session.lm.mds.TorrentMetadata(title='hay ' + str(x), infohash=database_blob(
                    bytearray(random.getrandbits(8) for _ in xrange(20))))
            self.session.lm.mds.TorrentMetadata(title='needle',
                                                infohash=database_blob(
                                                    bytearray(random.getrandbits(8) for _ in xrange(20))))

        self.should_check_equality = False

        result = yield self.do_request('search?txt=needle', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["torrents"]), 1)

        result = yield self.do_request('search?txt=hay', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["torrents"]), num_hay)

        result = yield self.do_request('search?first=10&last=20', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["torrents"]), 10)

        result = yield self.do_request('search?type=channel', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["torrents"]), 1)

        result = yield self.do_request('search?sort_by=-name&type=torrent', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(parsed["torrents"][0][u'name'], 'needle')

        result = yield self.do_request('search?type=channel&subscribed=0', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["torrents"]), 0)

        result = yield self.do_request('search?channel=%s' % str(channel.public_key).encode('hex'), expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["torrents"]), num_hay + 1)

    @trial_timeout(10)
    def test_completions_no_query(self):
        """
        Testing whether the API returns an error 400 if no query is passed when getting search completion terms
        """
        expected_json = {"error": "query parameter missing"}
        return self.do_request('search/completions', expected_code=400, expected_json=expected_json)

    @trial_timeout(10)
    def test_completions(self):
        """
        Testing whether the API returns the right terms when getting search completion terms
        """
        torrent_db_handler = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db_handler.getAutoCompleteTerms = lambda keyword, max_terms: ["%s %d" % (keyword, ind)
                                                                              for ind in xrange(max_terms)]

        expected_json = {"completions": ["tribler %d" % ind for ind in xrange(5)]}

        return self.do_request('search/completions?q=tribler', expected_code=200, expected_json=expected_json)
