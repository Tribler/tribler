from __future__ import absolute_import

import random
from binascii import unhexlify

from ipv8.attestation.trustchain.block import TrustChainBlock
from ipv8.attestation.trustchain.community import TrustChainCommunity
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.messaging.deprecated.encoding import encode
from ipv8.test.attestation.trustchain.test_block import MockDatabase, TestBlock
from ipv8.test.mocking.ipv8 import MockIPv8

from six.moves import xrange

from twisted.internet.defer import inlineCallbacks

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.trustview_endpoint import TrustGraph
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Core.exceptions import TrustGraphException
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import BaseTestCase


class TestTrustGraph(BaseTestCase):

    def setUp(self):
        self.root_key = default_eccrypto.generate_key(u"very-low")
        self.trust_graph = TrustGraph(hexlify(self.root_key.pub().key_to_bin()), max_peers=20, max_transactions=200)

    def test_initialize(self):
        """
        Tests the initialization of the Trust graph. At least root node should be in the graph.
        """
        self.assertGreaterEqual(len(self.trust_graph.peers), 1)

    def test_get_node_and_reset(self):
        """
        Tests get node with and without adding to the graph.
        Also tests the reset of the graph.
        """
        test_node1_key = hexlify(default_eccrypto.generate_key(u"very-low").pub().key_to_bin())
        test_node1 = self.trust_graph.get_node(test_node1_key)
        self.assertIsNotNone(test_node1)

        # check that node is added by default if not available in the graph
        self.assertGreaterEqual(len(self.trust_graph.peers), 2)

        # Get node without adding to the graph
        test_node2_key = hexlify(default_eccrypto.generate_key(u"very-low").pub().key_to_bin())
        test_node2 = self.trust_graph.get_node(test_node2_key, add_if_not_exist=False)
        self.assertIsNone(test_node2)

        # After resetting the graph, there should only be one root node
        self.trust_graph.reset(self.root_key)
        self.assertEqual(len(self.trust_graph.peers), 1)

    def test_maximum_nodes_in_graph(self):
        """
        Tests the maximum nodes that can be present in the graph.
        """
        # Added the MAX_PEERS nodes in the graph (including the root node)
        for _ in xrange(self.trust_graph.max_peers-1):
            test_node_key = hexlify(default_eccrypto.generate_key(u"very-low").pub().key_to_bin())
            test_node = self.trust_graph.get_node(test_node_key)
            self.assertIsNotNone(test_node)

        self.assertEqual(len(self.trust_graph.peers), self.trust_graph.max_peers)

        # If we try to add more than MAX_PEERS, we expect to get an exception
        try:
            test_node_key = hexlify(default_eccrypto.generate_key(u"very-low").pub().key_to_bin())
            self.trust_graph.get_node(test_node_key)
        except TrustGraphException as tge:
            exception_msg = getattr(tge, 'message', repr(tge))
            self.assertTrue('Max node peers reached in graph' in exception_msg)
        else:
            self.fail("Expected to fail but did not.")

    def test_add_blocks(self):
        """
        Tests the maximum blocks/transactions that be be present in the graph.
        :return:
        """
        db = MockDatabase()
        block = TestBlock()

        for _ in xrange(self.trust_graph.max_transactions):
            tx = {b"total_up": random.randint(1, 100), b"total_down": random.randint(1, 100),
                  b"up": random.randint(1, 100), b"down": random.randint(1, 100)}
            new_block = TrustChainBlock.create(b'tribler_bandwidth', tx, db, block.public_key)
            db.add_block(new_block)
            self.trust_graph.add_block(new_block)

        self.assertEqual(len(self.trust_graph.transactions), self.trust_graph.max_transactions)

        # Already max transactions are added to the graph, adding more should raise an exception
        try:
            tx = {b"total_up": random.randint(1, 100), b"total_down": random.randint(1, 100),
                  b"up": random.randint(1, 100), b"down": random.randint(1, 100)}
            new_block = TrustChainBlock.create(b'tribler_bandwidth', tx, db, block.public_key)
            db.add_block(new_block)
            self.trust_graph.add_block(new_block)
        except TrustGraphException as tge:
            exception_msg = getattr(tge, 'message', repr(tge))
            self.assertTrue('Max transactions reached in the graph' in exception_msg)
        else:
            self.fail("Expected to fail but did not.")


class TestTrustViewEndpoint(AbstractApiTest):
    @inlineCallbacks
    def setUp(self):
        yield super(TestTrustViewEndpoint, self).setUp()

        self.mock_ipv8 = MockIPv8(u"low", TrustChainCommunity, working_directory=self.session.config.get_state_dir())
        self.session.lm.trustchain_community = self.mock_ipv8.overlay

        self.session.lm.bootstrap = MockObject()
        self.session.lm.bootstrap.download = MockObject()

        bootstrap_download_state = MockObject()
        bootstrap_download_state.get_total_transferred = lambda _: random.randint(0, 10000)
        bootstrap_download_state.get_progress = lambda: random.randint(10, 100)

        self.session.lm.bootstrap.download.get_state = lambda: bootstrap_download_state

        self.endpoint = self.session.lm.api_manager.root_endpoint.trustview_endpoint

    def setUpPreSession(self):
        super(TestTrustViewEndpoint, self).setUpPreSession()
        self.config.set_trustchain_enabled(True)

    @inlineCallbacks
    def tearDown(self):
        yield self.mock_ipv8.unload()
        yield super(TestTrustViewEndpoint, self).tearDown()

    @inlineCallbacks
    def test_trustview_response(self):
        """
        Test whether the trust graph response is correctly returned.
        """
        root_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
        friends = [
            "4c69624e61434c504b3a2ee28ce24a2259b4e585b81106cdff4359fcf48e93336c11d133b01613f30b03b4db06df27"
            "80daac2cdf2ee60be611bf7367a9c1071ac50d65ca5858a50e9578",
            "4c69624e61434c504b3a5368c7b39a82063e29576df6d74fba3e0dba3af8e7a304b553b71f08ea6a0730e8cef767a4"
            "85dc6f390b6da5631f772941ea69ce2c098d802b7a28b500edf2b3",
            "4c69624e61434c504b3a0f3f6318e49ffeb0a160e7fcac5c1d3337ba409b45e1371ddca5e3b364ebdd1b73c775318a"
            "533a25335a5c36ae3695f1c3036b651893659fbf2e1f2bce66cf65",
        ]

        fofs = [
            "4c69624e61434c504b3a2ee28ce24a2259b4e585b81106cdff4359fcf48e93336c11d133b01613f30b03b4db06df27"
            "80daac2cdf2ee60be611bf7367a9c1071ac50d65ca5858a50e9579",
            "4c69624e61434c504b3a5368c7b39a82063e29576df6d74fba3e0dba3af8e7a304b553b71f08ea6a0730e8cef767a4"
            "85dc6f390b6da5631f772941ea69ce2c098d802b7a28b500edf2b4",
            "4c69624e61434c504b3a0f3f6318e49ffeb0a160e7fcac5c1d3337ba409b45e1371ddca5e3b364ebdd1b73c775318a"
            "533a25335a5c36ae3695f1c3036b651893659fbf2e1f2bce66cf66",
        ]

        fofofs = [
            "4c69624e61434c504b3a2ee28ce24a2259b4e585b81106cdff4359fcf48e93336c11d133b01613f30b03b4db06df27"
            "80daac2cdf2ee60be611bf7367a9c1071ac50d65ca5858a50e9580",
            "4c69624e61434c504b3a5368c7b39a82063e29576df6d74fba3e0dba3af8e7a304b553b71f08ea6a0730e8cef767a4"
            "85dc6f390b6da5631f772941ea69ce2c098d802b7a28b500edf2b5",
            "4c69624e61434c504b3a0f3f6318e49ffeb0a160e7fcac5c1d3337ba409b45e1371ddca5e3b364ebdd1b73c775318a"
            "533a25335a5c36ae3695f1c3036b651893659fbf2e1f2bce66cf67",
        ]

        def get_dummy_tx():
            return {
                b'up': random.randint(1, 101),
                b'down': random.randint(1, 101),
                b'total_up': random.randint(1, 101),
                b'total_down': random.randint(1, 101),
            }

        def verify_response(response, nodes, tx):
            response_json = json.twisted_loads(response)
            self.assertIsNotNone(response_json['graph'])
            self.assertEqual(response_json['num_tx'], tx)
            self.assertEqual(len(response_json['graph']['node']), nodes)

        test_block = TrustChainBlock()
        test_block.type = b'tribler_bandwidth'

        for seq, pub_key in enumerate(friends):
            test_block.transaction = get_dummy_tx()
            test_block._transaction = encode(test_block.transaction)

            test_block.sequence_number = seq
            test_block.public_key = root_key
            test_block.link_public_key = unhexlify(pub_key)

            test_block.hash = test_block.calculate_hash()
            self.session.lm.trustchain_community.persistence.add_block(test_block)

        for ind, friend in enumerate(friends):
            for ind2, fof in enumerate(fofs):
                test_block.transaction = get_dummy_tx()
                test_block._transaction = encode(test_block.transaction)

                test_block.sequence_number = ind + ind2
                test_block.public_key = unhexlify(friend)
                test_block.link_public_key = unhexlify(fof)

                test_block.hash = test_block.calculate_hash()
                self.session.lm.trustchain_community.persistence.add_block(test_block)

        for ind3, fof in enumerate(fofs):
            for ind4, fofof in enumerate(fofofs):
                test_block.transaction = get_dummy_tx()
                test_block._transaction = encode(test_block.transaction)

                test_block.sequence_number = ind3 + ind4
                test_block.public_key = unhexlify(fof)
                test_block.link_public_key = unhexlify(fofof)
                test_block.hash = test_block.calculate_hash()
                self.session.lm.trustchain_community.persistence.add_block(test_block)

        yield self.do_request(b'trustview?depth=1', expected_code=200)\
            .addCallback(lambda res: verify_response(res, 4, 3))
        yield self.do_request(b'trustview?depth=2', expected_code=200)\
            .addCallback(lambda res: verify_response(res, 7, 12))
        yield self.do_request(b'trustview?depth=3', expected_code=200)\
            .addCallback(lambda res: verify_response(res, 10, 21))
        yield self.do_request(b'trustview?depth=4', expected_code=200)\
            .addCallback(lambda res: verify_response(res, 10, 21))
        return

    @inlineCallbacks
    def test_trustview_max_response(self):
        """
        Test whether the trust graph response is limited.
        Here we redefine the max peers and max transactions limit for trust graph and add more peers and transactions,
        then test if the endpoint response is limited.
        """
        max_peers = 10
        max_tx = 10
        self.endpoint.initialize_graph()
        self.endpoint.trust_graph.set_limits(max_peers, max_tx)

        def get_dummy_tx():
            return {
                b'up': random.randint(1, 101),
                b'down': random.randint(1, 101),
                b'total_up': random.randint(1, 101),
                b'total_down': random.randint(1, 101),
            }

        def verify_response(response):
            response_json = json.twisted_loads(response)
            self.assertIsNotNone(response_json['graph'])
            self.assertLessEqual(response_json['num_tx'], max_tx)
            self.assertLessEqual(len(response_json['graph']['node']), max_peers)

        test_block = TestBlock(key=self.session.lm.trustchain_community.my_peer.key)
        test_block.sequence_number = 0
        test_block.type = b'tribler_bandwidth'
        for _ in xrange(max_peers * 2):
            test_block.transaction = get_dummy_tx()
            test_block._transaction = encode(test_block.transaction)
            test_block.link_public_key = default_eccrypto.generate_key(u"very-low").pub().key_to_bin()
            test_block.hash = test_block.calculate_hash()
            self.session.lm.trustchain_community.persistence.add_block(test_block)
            test_block.sequence_number = test_block.sequence_number + 1

        self.should_check_equality = False
        yield self.do_request(b'trustview?depth=0', expected_code=200) \
            .addCallback(verify_response)
        return
