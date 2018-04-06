import json

from twisted.internet.defer import inlineCallbacks

from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.pyipv8.ipv8.attestation.trustchain.block import TrustChainBlock
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred


class TestTrustchainStatsEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestTrustchainStatsEndpoint, self).setUp(autoload_discovery=autoload_discovery)
        self.session.lm.trustchain_community._use_main_thread = False

    def setUpPreSession(self):
        super(TestTrustchainStatsEndpoint, self).setUpPreSession()
        self.config.set_ipv8_enabled(True)
        self.config.set_trustchain_enabled(True)

    @deferred(timeout=10)
    def test_get_statistics_no_community(self):
        """
        Testing whether the API returns error 404 if no trustchain community is loaded
        """
        del self.session.lm.wallets['MB']
        return self.do_request('trustchain/statistics', expected_code=404)

    @deferred(timeout=10)
    def test_get_statistics(self):
        """
        Testing whether the API returns the correct statistics
        """
        block = TrustChainBlock()
        block.public_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
        block.link_public_key = "deadbeef".decode("HEX")
        block.link_sequence_number = 21
        block.type = 'tribler_bandwidth'
        block.transaction = {"up": 42, "down": 8, "total_up": 1024, "total_down": 2048, "type": "tribler_bandwidth"}
        block.sequence_number = 3
        block.previous_hash = "babecafe".decode("HEX")
        block.signature = "babebeef".decode("HEX")
        self.session.lm.trustchain_community.persistence.add_block(block)

        def verify_response(response):
            response_json = json.loads(response)
            self.assertTrue("statistics" in response_json)
            stats = response_json["statistics"]
            self.assertEqual(stats["id"], self.session.lm.trustchain_community.my_peer.
                             public_key.key_to_bin().encode("HEX"))
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
            self.assertEqual(stats["id"], self.session.lm.trustchain_community.my_peer.
                             public_key.key_to_bin().encode("HEX"))
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
        self.session.lm.trustchain_community = None
        return self.do_request('trustchain/blocks/aaaaa', expected_code=404)

    @deferred(timeout=10)
    def test_get_blocks(self):
        """
        Testing whether the API returns the correct blocks
        """
        def verify_response(response):
            response_json = json.loads(response)
            self.assertEqual(len(response_json["blocks"]), 1)

        test_block = TrustChainBlock()
        self.session.lm.trustchain_community.persistence.add_block(test_block)
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s?limit=10' % test_block.public_key.encode("HEX"),
                               expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_blocks_bad_limit_too_many(self):
        """
        Testing whether the API takes large values for the limit
        """
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s?limit=10000000' % TrustChainBlock().public_key.encode("HEX"),
                               expected_code=400)


    @deferred(timeout=10)
    def test_get_blocks_bad_limit_negative(self):
        """
        Testing whether the API takes negative values for the limit
        """
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s?limit=-10000000' % TrustChainBlock().public_key.encode("HEX"),
                               expected_code=400)

    @deferred(timeout=10)
    def test_get_blocks_bad_limit_nan(self):
        """
        Testing whether the API takes odd values for the limit
        """
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s?limit=bla' % TrustChainBlock().public_key.encode("HEX"),
                               expected_code=400)

    @deferred(timeout=10)
    def test_get_blocks_bad_limit_nothing(self):
        """
        Testing whether the API takes no values for the limit
        """
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s?limit=' % TrustChainBlock().public_key.encode("HEX"),
                               expected_code=400)

    @deferred(timeout=10)
    def test_get_blocks_unlimited(self):
        """
        Testing whether the API takes no limit argument
        """
        self.should_check_equality = False
        return self.do_request('trustchain/blocks/%s' % TrustChainBlock().public_key.encode("HEX"),
                               expected_code=200)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_no_community(self):
        """
        Testing whether the API returns error 404 if no trustchain community is loaded when bootstrapping a new identity
        """
        del self.session.lm.wallets['MB']
        return self.do_request('trustchain/bootstrap', expected_code=404)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_all_tokens(self):
        """
        Testing whether the API return all available tokens when no argument is supplied
        """
        transaction = {'up': 100, 'down': 0, 'total_up': 100, 'total_down': 0}
        transaction2 = {'up': 100, 'down': 0}

        def verify_response(response):
            response_json = json.loads(response)
            self.assertEqual(response_json['transaction'], transaction2)

        test_block = TrustChainBlock()
        test_block.type = 'tribler_bandwidth'
        test_block.transaction = transaction
        test_block.public_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
        self.session.lm.trustchain_community.persistence.add_block(test_block)

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

        test_block = TrustChainBlock()
        test_block.type = 'tribler_bandwidth'
        test_block.transaction = transaction
        test_block.public_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
        self.session.lm.trustchain_community.persistence.add_block(test_block)

        self.should_check_equality = False
        return self.do_request('trustchain/bootstrap?amount=50', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_not_enough_tokens(self):
        """
        Testing whether the API returns error 400 if bandwidth is to low when bootstrapping a new identity
        """
        transaction = {'up': 100, 'down': 0, 'total_up': 100, 'total_down': 0}
        test_block = TrustChainBlock()
        test_block.type = 'tribler_bandwidth'
        test_block.transaction = transaction
        test_block.public_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
        self.session.lm.trustchain_community.persistence.add_block(test_block)

        self.should_check_equality = False
        return self.do_request('trustchain/bootstrap?amount=200', expected_code=400)

    @deferred(timeout=10)
    def test_get_bootstrap_identity_not_enough_tokens_2(self):
        """
        Testing whether the API returns error 400 if bandwidth is to low when bootstrapping a new identity
        """
        transaction = {'up': 0, 'down': 100, 'total_up': 0, 'total_down': 100}
        test_block = TrustChainBlock()
        test_block.type = 'tribler_bandwidth'
        test_block.transaction = transaction
        test_block.public_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
        self.session.lm.trustchain_community.persistence.add_block(test_block)

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
