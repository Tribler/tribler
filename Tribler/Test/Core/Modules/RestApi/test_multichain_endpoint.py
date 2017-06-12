import json

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Community.Multichain.test_multichain_utilities import TestBlock
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred
from Tribler.community.multichain.block import MultiChainBlock
from Tribler.community.multichain.community import MultiChainCommunity
from Tribler.dispersy.community import Community
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.util import blocking_call_on_reactor_thread


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
            self.assertEqual(stats["id"], self.member.public_key.encode("HEX"))
            self.assertEqual(stats["total_blocks"], 3)
            self.assertEqual(stats["total_up"], 1024)
            self.assertEqual(stats["total_down"], 2048)
            self.assertEqual(stats["peers_that_pk_helped"], 1)
            self.assertEqual(stats["peers_that_helped_pk"], 1)
            self.assertIn("latest_block", stats)
            self.assertNotEqual(stats["latest_block"]["insert_time"], "")
            self.assertEqual(stats["latest_block"]["hash"], block.hash.encode("HEX"))
            self.assertEqual(stats["latest_block"]["link_public_key"], "deadbeef")
            self.assertEqual(stats["latest_block"]["link_sequence_number"], 21)
            self.assertEqual(stats["latest_block"]["up"], 42)
            self.assertEqual(stats["latest_block"]["down"], 8)

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
            self.assertEqual(stats["id"], self.member.public_key.encode("HEX"))
            self.assertEqual(stats["total_blocks"], 0)
            self.assertEqual(stats["total_up"], 0)
            self.assertEqual(stats["total_down"], 0)
            self.assertEqual(stats["peers_that_pk_helped"], 0)
            self.assertEqual(stats["peers_that_helped_pk"], 0)
            self.assertNotIn("latest_block", stats)

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
        self.should_check_equality = False
        return self.do_request('multichain/blocks/%s?limit=10' % test_block.public_key.encode("HEX"),
                               expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_blocks_bad_limit_too_many(self):
        """
        Testing whether the API takes large values for the limit
        """
        self.should_check_equality = False
        return self.do_request('multichain/blocks/%s?limit=10000000' % TestBlock().public_key.encode("HEX"),
                               expected_code=400)


    @deferred(timeout=10)
    def test_get_blocks_bad_limit_negative(self):
        """
        Testing whether the API takes negative values for the limit
        """
        self.should_check_equality = False
        return self.do_request('multichain/blocks/%s?limit=-10000000' % TestBlock().public_key.encode("HEX"),
                               expected_code=400)

    @deferred(timeout=10)
    def test_get_blocks_bad_limit_nan(self):
        """
        Testing whether the API takes odd values for the limit
        """
        self.should_check_equality = False
        return self.do_request('multichain/blocks/%s?limit=bla' % TestBlock().public_key.encode("HEX"),
                               expected_code=400)

    @deferred(timeout=10)
    def test_get_blocks_bad_limit_nothing(self):
        """
        Testing whether the API takes no values for the limit
        """
        self.should_check_equality = False
        return self.do_request('multichain/blocks/%s?limit=' % TestBlock().public_key.encode("HEX"),
                               expected_code=400)

    @deferred(timeout=10)
    def test_get_blocks_unlimited(self):
        """
        Testing whether the API takes no limit argument
        """
        self.should_check_equality = False
        return self.do_request('multichain/blocks/%s' % TestBlock().public_key.encode("HEX"),
                               expected_code=200)
