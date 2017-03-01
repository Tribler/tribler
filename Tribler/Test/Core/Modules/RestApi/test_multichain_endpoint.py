import base64
import json
from urllib import quote_plus

from twisted.internet.defer import inlineCallbacks

from Tribler.community.multichain.community import MultiChainCommunity
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.Community.Multichain.test_multichain_utilities import TestBlock
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.twisted_thread import deferred


class TestMultichainStatsEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestMultichainStatsEndpoint, self).setUp(autoload_discovery=autoload_discovery)

        self.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        self.dispersy._database.open()
        master_member = DummyMember(self.dispersy, 1, "a" * 20)
        self.member = self.dispersy.get_new_member(u"curve25519")

        self.mc_community = MultiChainCommunity(self.dispersy, master_member, self.member)
        self.dispersy.get_communities = lambda: [self.mc_community]
        self.session.get_dispersy_instance = lambda: self.dispersy

    @deferred(timeout=10)
    def test_get_statistics_no_community(self):
        """
        Testing whether the API returns error 404 if no multichain community is loaded
        """
        self.dispersy.get_communities = lambda: []
        return self.do_request('multichain/statistics', expected_code=404)

    @deferred(timeout=10)
    def test_get_statistics(self):
        """
        Testing whether the API returns the correct statistics
        """
        mock_block = MockObject()
        mock_block.public_key_requester = self.member.public_key
        mock_block.public_key_responder = "deadbeef".decode("HEX")
        mock_block.up = 42
        mock_block.down = 8
        mock_block.total_up_requester = 1024
        mock_block.total_down_requester = 2048
        mock_block.sequence_number_requester = 3
        mock_block.previous_hash_requester = "cafebabe".decode("HEX")
        mock_block.hash_requester = "b19b00b5".decode("HEX")
        mock_block.signature_requester = "deadbabe".decode("HEX")
        mock_block.total_up_responder = 512
        mock_block.total_down_responder = 256
        mock_block.sequence_number_responder = 15
        mock_block.previous_hash_responder = "cafef00d".decode("HEX")
        mock_block.hash_responder = "baadf00d".decode("HEX")
        mock_block.signature_responder = "deadf00d".decode("HEX")
        self.mc_community.persistence.add_block(mock_block)

        def verify_response(response):
            response_json = json.loads(response)
            self.assertTrue("statistics" in response_json)
            stats = response_json["statistics"]
            self.assertEqual(stats["self_id"], base64.encodestring(self.member.public_key).strip())
            self.assertEqual(stats["self_total_blocks"], 3)
            self.assertEqual(stats["self_total_up_mb"], 1024)
            self.assertEqual(stats["self_total_down_mb"], 2048)
            self.assertEqual(stats["self_peers_helped"], 1)
            self.assertEqual(stats["self_peers_helped_you"], 1)
            self.assertNotEqual(stats["latest_block_insert_time"], "")
            self.assertEqual(stats["latest_block_id"], base64.encodestring("b19b00b5".decode("HEX")).strip())
            self.assertEqual(stats["latest_block_requester_id"], base64.encodestring(self.member.public_key).strip())
            self.assertEqual(stats["latest_block_responder_id"], base64.encodestring("deadbeef".decode("HEX")).strip())
            self.assertEqual(stats["latest_block_up_mb"], "42")
            self.assertEqual(stats["latest_block_down_mb"], "8")

        self.should_check_equality = False
        return self.do_request('multichain/statistics', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_statistics_no_data(self):
        """
        Testing whether the API returns the correct statistics
        """

        def verify_response(response):
            response_json = json.loads(response)
            self.assertTrue("statistics" in response_json)
            stats = response_json["statistics"]
            self.assertEqual(stats["self_id"], base64.encodestring(self.member.public_key).strip())
            self.assertEqual(stats["self_total_blocks"], -1)
            self.assertEqual(stats["self_total_up_mb"], 0)
            self.assertEqual(stats["self_total_down_mb"], 0)
            self.assertEqual(stats["self_peers_helped"], 0)
            self.assertEqual(stats["self_peers_helped_you"], 0)
            self.assertEqual(stats["latest_block_insert_time"], "")
            self.assertEqual(stats["latest_block_id"], "")
            self.assertEqual(stats["latest_block_requester_id"], "")
            self.assertEqual(stats["latest_block_responder_id"], "")
            self.assertEqual(stats["latest_block_up_mb"], "")
            self.assertEqual(stats["latest_block_down_mb"], "")

        self.should_check_equality = False
        return self.do_request('multichain/statistics', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_blocks_no_community(self):
        """
        Testing whether the API returns error 404 if no multichain community is loaded when requesting blocks
        """
        self.dispersy.get_communities = lambda: []
        return self.do_request('multichain/blocks/aaaaa', expected_code=404)

    @deferred(timeout=10)
    def test_get_blocks(self):
        """
        Testing whether the API returns the correct blocks
        """
        def verify_response(response):
            response_json = json.loads(response)
            self.assertEqual(len(response_json["blocks"]), 1)

        test_block = TestBlock()
        self.mc_community.persistence.add_block(test_block)
        pub_key = quote_plus(base64.encodestring(test_block.public_key_requester))
        self.should_check_equality = False
        return self.do_request('multichain/blocks/%s?limit=10' % pub_key, expected_code=200)\
            .addCallback(verify_response)
