import os

from ipv8.database import database_blob

from pony.orm import db_session

from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.tools import timeout


class TestSearchEndpoint(AbstractApiTest):
    def setUpPreSession(self):
        super(TestSearchEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @timeout(10)
    async def test_search_no_query(self):
        """
        Testing whether the API returns an error 400 if no query is passed when doing a search
        """
        await self.do_request('search', expected_code=400)

    @timeout(10)
    async def test_search_wrong_mdtype(self):
        """
        Testing whether the API returns an error 400 if wrong metadata type is passed in the query
        """
        await self.do_request('search?filter=bla&metadata_type=ddd', expected_code=400)

    @timeout(10)
    async def test_search_remote(self):
        """
        Test that remote search call is sent on a REST API search request
        """
        self.session.gigachannel_community = MockObject()

        sent = []

        def mock_send(*_, **__):
            sent.append(True)

        self.session.gigachannel_community.send_search_request = mock_send
        await self.do_request('search?filter=needle', expected_code=200)
        self.assertTrue(sent)

    @timeout(10)
    async def test_search(self):
        """
        Test a search query that should return a few new type channels
        """
        num_hay = 100
        with db_session:
            _ = self.session.mds.ChannelMetadata(title='test', tags='test', subscribed=True, infohash=os.urandom(20))
            for x in range(0, num_hay):
                self.session.mds.TorrentMetadata(title='hay ' + str(x), infohash=os.urandom(20))
            self.session.mds.TorrentMetadata(title='needle', infohash=database_blob(bytearray(os.urandom(20))))
            self.session.mds.TorrentMetadata(title='needle2', infohash=database_blob(bytearray(os.urandom(20))))

        parsed = await self.do_request('search?filter=needle', expected_code=200)
        self.assertEqual(len(parsed["results"]), 1)

        parsed = await self.do_request('search?filter=hay', expected_code=200)
        self.assertEqual(len(parsed["results"]), 50)

        parsed = await self.do_request('search?filter=test&type=channel', expected_code=200)
        self.assertEqual(len(parsed["results"]), 1)

        parsed = await self.do_request('search?filter=needle&type=torrent', expected_code=200)
        self.assertEqual(parsed["results"][0][u'name'], 'needle')

        parsed = await self.do_request('search?filter=needle&sort_by=name', expected_code=200)
        self.assertEqual(len(parsed["results"]), 1)

        parsed = await self.do_request('search?filter=needle%2A&sort_by=name&sort_desc=1', expected_code=200)
        self.assertEqual(len(parsed["results"]), 2)
        self.assertEqual(parsed["results"][0][u'name'], "needle2")

        # Test getting total count of results
        parsed = await self.do_request('search?filter=needle&include_total=1', expected_code=200)
        self.assertEqual(parsed["total"], 1)

        # Test getting total count of results
        parsed = await self.do_request('search?filter=hay&include_total=1', expected_code=200)
        self.assertEqual(parsed["total"], 100)

        # If uuid is passed in request, then the same uuid is returned in the response
        parsed = await self.do_request('search?uuid=uuid1&filter=needle&sort_by=name', expected_code=200)
        self.assertEqual(len(parsed["results"]), 1)
        self.assertEqual(parsed['uuid'], 'uuid1')

    @timeout(10)
    async def test_completions_no_query(self):
        """
        Testing whether the API returns an error 400 if no query is passed when getting search completion terms
        """
        await self.do_request('search/completions', expected_code=400)

    @timeout(10)
    async def test_completions(self):
        """
        Testing whether the API returns the right terms when getting search completion terms
        """
        json_response =  await self.do_request('search/completions?q=tribler', expected_code=200)
        self.assertEqual(json_response['completions'], [])
