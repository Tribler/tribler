from __future__ import absolute_import

from six import unichr
from pony.orm import db_session
from six.moves import xrange
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.simpledefs import (NTFY_CHANNELCAST, NTFY_TORRENTS, SIGNAL_CHANNEL,
                                     SIGNAL_ON_SEARCH_RESULTS, SIGNAL_TORRENT)
from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import trial_timeout


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

        self.session.add_observer(self.on_search_results_channels, SIGNAL_CHANNEL, [SIGNAL_ON_SEARCH_RESULTS])
        self.session.add_observer(self.on_search_results_torrents, SIGNAL_TORRENT, [SIGNAL_ON_SEARCH_RESULTS])

        self.results_torrents_called = False
        self.results_channels_called = False

        self.search_results_list = [] # List of incoming torrent/channel results
        self.expected_num_results_list = [] # List of expected number of results for each item in search_results_list

    def setUpPreSession(self):
        super(TestSearchEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    def on_search_results_torrents(self, subject, changetype, objectID, results):
        self.search_results_list.append(results['result_list'])
        self.results_torrents_called = True

    def on_search_results_channels(self, subject, changetype, objectID, results):
        self.search_results_list.append(results['result_list'])
        self.results_channels_called = True

    def insert_channels_in_db(self, num):
        for i in xrange(0, num):
            self.channel_db_handler.on_channel_from_dispersy('rand%d' % i, 42 + i,
                                                             'Test channel %d' % i, 'Test description %d' % i)

    def insert_torrents_in_db(self, num):
        for i in xrange(0, num):
            self.torrent_db_handler.addExternalTorrentNoDef(str(unichr(97 + i)) * 20,
                                                            'Test %d' % i, [('Test.txt', 1337)], [], 1337)

    @trial_timeout(10)
    def test_search_no_parameter(self):
        """
        Testing whether the API returns an error 400 if no search query is passed with the request
        """
        expected_json = {"error": "query parameter missing"}
        return self.do_request('search', expected_code=400, expected_json=expected_json)

    def verify_search_results(self, _):
        self.assertTrue(self.results_channels_called)
        self.assertTrue(self.results_torrents_called)
        self.assertEqual(len(self.search_results_list), len(self.expected_num_results_list))

        for ind in xrange(len(self.search_results_list)):
            self.assertEqual(len(self.search_results_list[ind]), self.expected_num_results_list[ind])

    @trial_timeout(10)
    def test_search_no_matches(self):
        """
        Testing whether the API finds no channels/torrents when searching if they are not in the database
        """
        self.insert_channels_in_db(5)
        self.insert_torrents_in_db(6)
        self.expected_num_results_list = [0, 0]

        expected_json = {"queried": True}
        return self.do_request('search?q=tribler', expected_code=200, expected_json=expected_json)\
            .addCallback(self.verify_search_results)

    @trial_timeout(10)
    def test_search(self):
        """
        Testing whether the API finds channels/torrents when searching if there is some inserted data in the database
        """
        self.insert_channels_in_db(5)
        self.insert_torrents_in_db(6)
        self.expected_num_results_list = [5, 6, 0, 0]

        self.session.config.get_torrent_search_enabled = lambda: True
        self.session.config.get_channel_search_enabled = lambda: True
        self.session.lm.search_manager = FakeSearchManager(self.session.notifier)

        expected_json = {"queried": True}
        return self.do_request('search?q=test', expected_code=200, expected_json=expected_json)\
            .addCallback(self.verify_search_results)

    @trial_timeout(10)
    def test_search_chant(self):
        """
        Test a search query that should return a few new type channels
        """
        def verify_search_results(_):
            self.assertTrue(self.search_results_list)

        with db_session:
            my_channel_id = self.session.trustchain_keypair.pub().key_to_bin()
            self.session.lm.mds.ChannelMetadata(public_key=database_blob(my_channel_id), title='test', tags='test')

        self.should_check_equality = False
        self.expected_num_results_list = []
        return self.do_request('search?q=test', expected_code=200).addCallback(verify_search_results)

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
