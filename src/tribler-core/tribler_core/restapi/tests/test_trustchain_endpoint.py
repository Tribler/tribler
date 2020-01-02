from binascii import unhexlify

from anydex.wallet.tc_wallet import TrustchainWallet

from ipv8.attestation.trustchain.block import TrustChainBlock
from ipv8.attestation.trustchain.community import TrustChainCommunity
from ipv8.messaging.deprecated.encoding import encode
from ipv8.test.mocking.ipv8 import MockIPv8

from tribler_core.restapi.base_api_test import AbstractApiTest
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities.unicode import hexlify


class TestTrustchainStatsEndpoint(AbstractApiTest):

    async def setUp(self):
        await super(TestTrustchainStatsEndpoint, self).setUp()

        self.mock_ipv8 = MockIPv8(u"low",
                                  TrustChainCommunity,
                                  working_directory=self.session.config.get_state_dir())
        self.session.trustchain_community = self.mock_ipv8.overlay
        self.session.wallets['MB'] = TrustchainWallet(self.session.trustchain_community)

    async def tearDown(self):
        await self.mock_ipv8.unload()
        await super(TestTrustchainStatsEndpoint, self).tearDown()

    @timeout(10)
    async def test_get_statistics_no_community(self):
        """
        Testing whether the API returns error 404 if no trustchain community is loaded
        """
        del self.session.wallets['MB']
        await self.do_request('trustchain/statistics', expected_code=404)

    @timeout(10)
    async def test_get_statistics(self):
        """
        Testing whether the API returns the correct statistics
        """
        block = TrustChainBlock()
        block.public_key = self.session.trustchain_community.my_peer.public_key.key_to_bin()
        block.link_public_key = unhexlify(b"deadbeef")
        block.link_sequence_number = 21
        block.type = b'tribler_bandwidth'
        block.transaction = {b"up": 42, b"down": 8, b"total_up": 1024,
                             b"total_down": 2048, b"type": b"tribler_bandwidth"}
        block._transaction = encode(block.transaction)
        block.sequence_number = 3
        block.previous_hash = unhexlify(b"babecafe")
        block.signature = unhexlify(b"babebeef")
        block.hash = block.calculate_hash()
        self.session.trustchain_community.persistence.add_block(block)

        response_dict = await self.do_request('trustchain/statistics', expected_code=200)
        self.assertTrue("statistics" in response_dict)
        stats = response_dict["statistics"]
        self.assertEqual(stats["id"], hexlify(self.session.trustchain_community.
                                              my_peer.public_key.key_to_bin()))
        self.assertEqual(stats["total_blocks"], 3)
        self.assertEqual(stats["total_up"], 1024)
        self.assertEqual(stats["total_down"], 2048)
        self.assertEqual(stats["peers_that_pk_helped"], 1)
        self.assertEqual(stats["peers_that_helped_pk"], 1)

    @timeout(10)
    async def test_get_statistics_no_data(self):
        """
        Testing whether the API returns the correct statistics
        """
        response_dict = await self.do_request('trustchain/statistics', expected_code=200)
        self.assertTrue("statistics" in response_dict)
        stats = response_dict["statistics"]
        self.assertEqual(stats["id"], hexlify(self.session.trustchain_community.my_peer.
                                              public_key.key_to_bin()))
        self.assertEqual(stats["total_blocks"], 0)
        self.assertEqual(stats["total_up"], 0)
        self.assertEqual(stats["total_down"], 0)
        self.assertEqual(stats["peers_that_pk_helped"], 0)
        self.assertEqual(stats["peers_that_helped_pk"], 0)
        self.assertNotIn("latest_block", stats)

    @timeout(10)
    async def test_get_bootstrap_identity_no_community(self):
        """
        Testing whether the API returns error 404 if no trustchain community is loaded when bootstrapping a new identity
        """
        del self.session.wallets['MB']
        await self.do_request('trustchain/bootstrap', expected_code=404)

    @timeout(10)
    async def test_get_bootstrap_identity_all_tokens(self):
        """
        Testing whether the API return all available tokens when no argument is supplied
        """
        transaction = {b'up': 100, b'down': 0, b'total_up': 100, b'total_down': 0}
        transaction2 = {'up': 100, 'down': 0}

        test_block = TrustChainBlock()
        test_block.type = b'tribler_bandwidth'
        test_block.transaction = transaction
        test_block._transaction = encode(transaction)
        test_block.public_key = self.session.trustchain_community.my_peer.public_key.key_to_bin()
        test_block.hash = test_block.calculate_hash()
        self.session.trustchain_community.persistence.add_block(test_block)

        response_dict = await self.do_request('trustchain/bootstrap', expected_code=200)
        self.assertEqual(response_dict['transaction'], transaction2)

    @timeout(10)
    async def test_get_bootstrap_identity_partial_tokens(self):
        """
        Testing whether the API return partial available credit when argument is supplied
        """
        transaction = {b'up': 100, b'down': 0, b'total_up': 100, b'total_down': 0}
        transaction2 = {'up': 50, 'down': 0}

        test_block = TrustChainBlock()
        test_block.type = b'tribler_bandwidth'
        test_block.transaction = transaction
        test_block._transaction = encode(transaction)
        test_block.public_key = self.session.trustchain_community.my_peer.public_key.key_to_bin()
        test_block.hash = test_block.calculate_hash()
        self.session.trustchain_community.persistence.add_block(test_block)

        response_dict = await self.do_request('trustchain/bootstrap?amount=50', expected_code=200)
        self.assertEqual(response_dict['transaction'], transaction2)

    @timeout(10)
    async def test_get_bootstrap_identity_not_enough_tokens(self):
        """
        Testing whether the API returns error 400 if bandwidth is to low when bootstrapping a new identity
        """
        transaction = {b'up': 100, b'down': 0, b'total_up': 100, b'total_down': 0}
        test_block = TrustChainBlock()
        test_block.type = b'tribler_bandwidth'
        test_block.transaction = transaction
        test_block._transaction = encode(transaction)
        test_block.public_key = self.session.trustchain_community.my_peer.public_key.key_to_bin()
        test_block.hash = test_block.calculate_hash()
        self.session.trustchain_community.persistence.add_block(test_block)

        await self.do_request('trustchain/bootstrap?amount=200', expected_code=400)

    @timeout(10)
    async def test_get_bootstrap_identity_not_enough_tokens_2(self):
        """
        Testing whether the API returns error 400 if bandwidth is to low when bootstrapping a new identity
        """
        transaction = {b'up': 0, b'down': 100, b'total_up': 0, b'total_down': 100}
        test_block = TrustChainBlock()
        test_block.type = b'tribler_bandwidth'
        test_block.transaction = transaction
        test_block._transaction = encode(transaction)
        test_block.public_key = self.session.trustchain_community.my_peer.public_key.key_to_bin()
        test_block.hash = test_block.calculate_hash()
        self.session.trustchain_community.persistence.add_block(test_block)

        await self.do_request('trustchain/bootstrap?amount=10', expected_code=400)

    @timeout(10)
    async def test_get_bootstrap_identity_zero_amount(self):
        """
        Testing whether the API returns error 400 if amount is zero when bootstrapping a new identity
        """
        await self.do_request('trustchain/bootstrap?amount=0', expected_code=400)

    @timeout(10)
    async def test_get_bootstrap_identity_negative_amount(self):
        """
        Testing whether the API returns error 400 if amount is negative when bootstrapping a new identity
        """
        await self.do_request('trustchain/bootstrap?amount=-1', expected_code=400)

    @timeout(10)
    async def test_get_bootstrap_identity_string(self):
        """
        Testing whether the API returns error 400 if amount is string when bootstrapping a new identity
        """
        await self.do_request('trustchain/bootstrap?amount=aaa', expected_code=400)
