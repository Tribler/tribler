from nose.tools import raises
from Tribler.Test.Community.AbstractTestCommunity import AbstractTestCommunity
from Tribler.Test.Core.base_test import MockObject
from Tribler.community.search.community import SearchCommunity
from Tribler.community.search.conversion import SearchConversion
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestSearchCommunity(AbstractTestCommunity):

    @blocking_call_on_reactor_thread
    def setUp(self, annotate=True):
        super(TestSearchCommunity, self).setUp(annotate=annotate)
        self.search_community = SearchCommunity(self.dispersy, self.master_member, self.member)

    def test_on_search(self):
        """
        Test whether we are creating a search response when we receive a search request
        """
        def log_incoming_searches(sock_addr, keywords):
            log_incoming_searches.called = True

        log_incoming_searches.called = False

        def create_search_response(id, results, candidate):
            create_search_response.called = True
            self.assertEqual(id, "abc")
            self.assertEqual(results, [])
            self.assertEqual(candidate.sock_addr, "1234")

        create_search_response.called = False

        def search_names(keywords, local=False, keys=None):
            return []

        self.search_community._torrent_db = MockObject()
        self.search_community._torrent_db.searchNames = search_names

        fake_message = MockObject()
        fake_message.candidate = MockObject()
        fake_message.candidate.sock_addr = "1234"
        fake_message.payload = MockObject()
        fake_message.payload.keywords = "test"
        fake_message.payload.identifier = "abc"

        self.search_community._create_search_response = create_search_response
        self.search_community.log_incoming_searches = log_incoming_searches
        self.search_community.on_search([fake_message])

        self.assertTrue(log_incoming_searches.called)
        self.assertTrue(create_search_response.called)

    @raises(DropPacket)
    def test_decode_response_invalid(self):
        """
        Test whether decoding an invalid search response does not crash the program
        """
        self.search_community._initialize_meta_messages()
        search_conversion = SearchConversion(self.search_community)
        search_conversion._decode_search_response(None, 0, "a[]")
