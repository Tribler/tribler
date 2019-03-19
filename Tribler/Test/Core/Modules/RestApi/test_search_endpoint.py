from __future__ import absolute_import

import json
import random

from pony.orm import db_session

from six.moves import xrange

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import trial_timeout
from Tribler.pyipv8.ipv8.database import database_blob


class TestSearchEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestSearchEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @trial_timeout(10)
    def test_search_no_query(self):
        """
        Testing whether the API returns an error 400 if no query is passed when doing a search
        """
        self.should_check_equality = False
        return self.do_request('search', expected_code=400)

    @trial_timeout(10)
    def test_search_wrong_mdtype(self):
        """
        Testing whether the API returns an error 400 if wrong metadata type is passed in the query
        """
        self.should_check_equality = False
        return self.do_request('search?filter=bla&metadata_type=ddd', expected_code=400)

    @trial_timeout(10)
    @inlineCallbacks
    def test_search(self):
        """
        Test a search query that should return a few new type channels
        """
        num_hay = 100
        with db_session:
            _ = self.session.lm.mds.ChannelMetadata(title='test', tags='test', subscribed=True,
                                                    infohash=str(random.getrandbits(160)))
            for x in xrange(0, num_hay):
                self.session.lm.mds.TorrentMetadata(title='hay ' + str(x), infohash=str(random.getrandbits(160)))
            self.session.lm.mds.TorrentMetadata(title='needle',
                                                infohash=database_blob(
                                                    bytearray(random.getrandbits(8) for _ in xrange(20))))

        self.should_check_equality = False

        result = yield self.do_request('search?filter=needle', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["results"]), 1)

        result = yield self.do_request('search?filter=hay', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["results"]), 50)

        result = yield self.do_request('search?filter=test&type=channel', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["results"]), 1)

        result = yield self.do_request('search?filter=needle&type=torrent', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(parsed["results"][0][u'name'], 'needle')

        result = yield self.do_request('search?filter=needle&sort_by=name', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["results"]), 1)

        # If uuid is passed in request, then the same uuid is returned in the response
        result = yield self.do_request('search?uuid=uuid1&filter=needle&sort_by=name', expected_code=200)
        parsed = json.loads(result)
        self.assertEqual(len(parsed["results"]), 1)
        self.assertEqual(parsed['uuid'], 'uuid1')

    @trial_timeout(10)
    def test_completions_no_query(self):
        """
        Testing whether the API returns an error 400 if no query is passed when getting search completion terms
        """
        self.should_check_equality = False
        return self.do_request('search/completions', expected_code=400)

    @trial_timeout(10)
    def test_completions(self):
        """
        Testing whether the API returns the right terms when getting search completion terms
        """

        def on_response(response):
            json_response = json.loads(response)
            self.assertEqual(json_response['completions'], [])

        self.should_check_equality = False
        return self.do_request('search/completions?q=tribler', expected_code=200).addCallback(on_response)
