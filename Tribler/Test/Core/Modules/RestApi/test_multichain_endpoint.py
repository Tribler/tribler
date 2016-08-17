import json
from urllib import quote_plus

from twisted.internet.defer import inlineCallbacks


from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.community.multichain.block import MultiChainBlock

from Tribler.community.multichain.community import MultiChainCommunity
from Tribler.dispersy.community import Community
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
        dummy_master_member = DummyMember(self.dispersy, 1, "b" * 20)
        Community.__abstractmethods__ = frozenset()
        self.dispersy.get_communities = lambda: [Community(self.dispersy, dummy_master_member, self.member),
                                                 Community(self.dispersy, dummy_master_member, self.member)]
        return self.do_request('multichain/statistics', expected_code=404)

    @deferred(timeout=10)
    def test_get_statistics(self):
        """
        Testing whether the API returns the correct statistics
        """
        block = MultiChainBlock()
        block.public_key = self.member.public_key
        block.link_public_key = "deadbeef".decode("HEX")
        block.link_sequence_number = 21
        block.up = 42
        block.down = 8
        block.total_up = 1024
        block.total_down = 2048
        block.sequence_number = 3
        block.previous_hash = "babecafe".decode("HEX")
        block.signature = "babebeef".decode("HEX")
        self.mc_community.persistence.add_block(block)

        def verify_response(response):
            response_json = json.loads(response)
            self.assertTrue("statistics" in response_json)
            stats = response_json["statistics"]
            self.assertEqual(stats["self_id"], self.member.public_key.encode("HEX"))
            self.assertEqual(stats["self_total_blocks"], 3)
            self.assertEqual(stats["self_total_up"], 1024)
            self.assertEqual(stats["self_total_down"], 2048)
            self.assertEqual(stats["self_peers_helped"], 1)
            self.assertEqual(stats["self_peers_helped_you"], 1)
            self.assertNotEqual(stats["latest_block_insert_time"], "")
            self.assertEqual(stats["latest_block_id"], block.hash.encode("HEX"))
            self.assertEqual(stats["latest_block_link_public_key"], "deadbeef")
            self.assertEqual(stats["latest_block_link_sequence_number"], 21)
            self.assertEqual(stats["latest_block_up"], 42)
            self.assertEqual(stats["latest_block_down"], 8)

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
            self.assertEqual(stats["self_id"], self.member.public_key.encode("HEX"))
            self.assertEqual(stats["self_total_blocks"], 0)
            self.assertEqual(stats["self_total_up"], 0)
            self.assertEqual(stats["self_total_down"], 0)
            self.assertEqual(stats["self_peers_helped"], 0)
            self.assertEqual(stats["self_peers_helped_you"], 0)
            self.assertEqual(stats["latest_block_insert_time"], "")
            self.assertEqual(stats["latest_block_id"], "")
            self.assertEqual(stats["latest_block_link_public_key"], "")
            self.assertEqual(stats["latest_block_link_sequence_number"], 0)
            self.assertEqual(stats["latest_block_up"], 0)
            self.assertEqual(stats["latest_block_down"], 0)

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
        pub_key = quote_plus(test_block.public_key_requester.encode("HEX"))
        self.should_check_equality = False
        return self.do_request('multichain/blocks/%s?limit=10' % pub_key, expected_code=200)\
            .addCallback(verify_response)
