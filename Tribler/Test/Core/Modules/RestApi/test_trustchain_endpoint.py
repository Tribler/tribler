import json

from twisted.internet.defer import inlineCallbacks

from Tribler.community.triblerchain.community import TriblerChainCommunity
from Tribler.community.trustchain.block import TrustChainBlock
from Tribler.dispersy.community import Community
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.Community.Trustchain.test_trustchain_utilities import TestBlock
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred


class TestTrustchainStatsEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestTrustchainStatsEndpoint, self).setUp(autoload_discovery=autoload_discovery)

        self.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        self.dispersy._database.open()
        master_member = DummyMember(self.dispersy, 1, "a" * 20)
        self.member = self.dispersy.get_new_member(u"curve25519")

        self.tc_community = TriblerChainCommunity(self.dispersy, master_member, self.member)
        self.dispersy.get_communities = lambda: [self.tc_community]
        self.session.get_dispersy_instance = lambda: self.dispersy

    @deferred(timeout=10)
    def test_get_statistics_no_community(self):
        """
        Testing whether the API returns error 404 if no trustchain community is loaded
        """
        dummy_master_member = DummyMember(self.dispersy, 1, "b" * 20)
        Community.__abstractmethods__ = frozenset()
        self.dispersy.get_communities = lambda: [Community(self.dispersy, dummy_master_member, self.member),
                                                 Community(self.dispersy, dummy_master_member, self.member)]
        return self.do_request('trustchain/statistics', expected_code=404)

    @deferred(timeout=10)
    def test_get_statistics(self):
        """
        Testing whether the API returns the correct statistics
        """
        block = TrustChainBlock()
        block.public_key = self.member.public_key
        block.link_public_key = "deadbeef".decode("HEX")
        block.link_sequence_number = 21
        block.transaction = {"up": 42, "down": 8, "total_up": 1024, "total_down": 2048}
        block.sequence_number = 3
        block.previous_hash = "babecafe".decode("HEX")
        block.signature = "babebeef".decode("HEX")
        self.tc_community.persistence.add_block(block)

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
        return self.do_request('trustchain/statistics', expected_code=200).addCallback(verify_response)

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
        return self.do_request('trustchain/statistics', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_blocks_no_community(self):
        """
        Testing whether the API returns error 404 if no trustchain community is loaded when requesting blocks
        """
        self.dispersy.get_communities = lambda: []
        return self.do_request('trustchain/blocks/aaaaa', expected_code=404)

    @deferred(timeout=10)
    def test_get_blocks(self):
        """
        Testing whether the API returns the correct blocks
        """
        def verify_response(response):
            response_json = json.loads(response)
            self.assertEqual(len(response_json["blocks"]), 1)

        test_block = TestBlock()
        self.tc_community.persistence.add_block(test_block)
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s?limit=10' % test_block.public_key.encode("HEX"),
                               expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_blocks_bad_limit_too_many(self):
        """
        Testing whether the API takes large values for the limit
        """
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s?limit=10000000' % TestBlock().public_key.encode("HEX"),
                               expected_code=400)


    @deferred(timeout=10)
    def test_get_blocks_bad_limit_negative(self):
        """
        Testing whether the API takes negative values for the limit
        """
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s?limit=-10000000' % TestBlock().public_key.encode("HEX"),
                               expected_code=400)

    @deferred(timeout=10)
    def test_get_blocks_bad_limit_nan(self):
        """
        Testing whether the API takes odd values for the limit
        """
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s?limit=bla' % TestBlock().public_key.encode("HEX"),
                               expected_code=400)

    @deferred(timeout=10)
    def test_get_blocks_bad_limit_nothing(self):
        """
        Testing whether the API takes no values for the limit
        """
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s?limit=' % TestBlock().public_key.encode("HEX"),
                               expected_code=400)

    @deferred(timeout=10)
    def test_get_blocks_unlimited(self):
        """
        Testing whether the API takes no limit argument
        """
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s' % TestBlock().public_key.encode("HEX"),
                               expected_code=200)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_no_community(self):
        """
        Testing whether the API returns error 404 if no trustchain community is loaded when bootstrapping a new identity
        """
        self.dispersy.get_communities = lambda: []
        return self.do_request('trustchain/bootstrap', expected_code=404)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_all_tokens(self):
        """
        Testing whether the API return all available credit when no argument is supplied
        """
        transaction = {'up': 100, 'down': 0, 'total_up': 100, 'total_down': 0}
        transaction2 = {'up': 100, 'down': 0}

        def verify_response(response):
            response_json = json.loads(response)
            self.assertEqual(response_json['transaction'], transaction2)

        test_block = TestBlock(transaction=transaction, key=self.tc_community.my_member.private_key)
        self.tc_community.persistence.add_block(test_block)

        self.should_check_equality = False
        return self.do_request('trustchain/bootstrap', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_partial_tokens(self):
        """
        Testing whether the API return partial available credit when argument is supplied
        """
        transaction = {'up': 100, 'down': 0, 'total_up': 100, 'total_down': 0}
        transaction2 = {'up': 50, 'down': 0}

        def verify_response(response):
            response_json = json.loads(response)
            self.assertEqual(response_json['transaction'], transaction2)

        test_block = TestBlock(transaction=transaction, key=self.tc_community.my_member.private_key)
        self.tc_community.persistence.add_block(test_block)

        self.should_check_equality = False
        return self.do_request('trustchain/bootstrap?amount=50', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_not_enough_tokens(self):
        """
        Testing whether the API returns error 400 if bandwidth is to low when bootstrapping a new identity
        """
        transaction = {'up': 100, 'down': 0, 'total_up': 100, 'total_down': 0}
        test_block = TestBlock(transaction=transaction, key=self.tc_community.my_member.private_key)
        self.tc_community.persistence.add_block(test_block)

        self.should_check_equality = False
        return self.do_request('trustchain/bootstrap?amount=200', expected_code=400)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_not_enough_tokens_2(self):
        """
        Testing whether the API returns error 400 if bandwidth is to low when bootstrapping a new identity
        """
        transaction = {'up': 0, 'down': 100, 'total_up': 0, 'total_down': 100}
        test_block = TestBlock(transaction=transaction, key=self.tc_community.my_member.private_key)
        self.tc_community.persistence.add_block(test_block)

        self.should_check_equality = False
        return self.do_request('trustchain/bootstrap?amount=10', expected_code=400)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_zero_amount(self):
        """
        Testing whether the API returns error 400 if amount is zero when bootstrapping a new identity
        """
        self.should_check_equality = False
        return self.do_request('trustchain/bootstrap?amount=0', expected_code=400)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_negative_amount(self):
        """
        Testing whether the API returns error 400 if amount is negative when bootstrapping a new identity
        """
        self.should_check_equality = False
        return self.do_request('trustchain/bootstrap?amount=-1', expected_code=400)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_string(self):
        """
        Testing whether the API returns error 400 if amount is string when bootstrapping a new identity
        """
        self.should_check_equality = False
        return self.do_request('trustchain/bootstrap?amount=aaa', expected_code=400)
