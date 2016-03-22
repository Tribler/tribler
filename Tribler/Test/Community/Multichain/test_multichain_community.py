"""
This file contains the tests for the community.py for MultiChain community.
"""
from unittest.case import skip

from nose.tools import raises
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Session import Session

from Tribler.community.multichain.community import MultiChainCommunity, SIGNED, HALF_BLOCK, FULL_BLOCK, CRAWL, RESUME
from Tribler.community.multichain.block import MultiChainBlock

from Tribler.community.tunnel.routing import Circuit, RelayRoute
from Tribler.community.tunnel.tunnel_community import TunnelExitSocket
from Tribler.Test.test_as_server import AbstractServer
from Tribler.dispersy.message import DelayPacketByMissingMember
from Tribler.dispersy.tests.dispersytestclass import DispersyTestFunc
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.dispersy.tests.debugcommunity.node import DebugNode
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.requestcache import IntroductionRequestCache


class TestMultiChainCommunity(AbstractServer, DispersyTestFunc):
    """
    Class that tests the MultiChainCommunity on an integration level.
    """

    class MockSession():
        def add_observer(self, func, subject, changeTypes=[], objectID=None, cache=0):
            pass

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        self.assertEqual_block = MultiChainTestCase.assertEqual_block.__get__(self)
        Session.__single = self.MockSession()
        AbstractServer.setUp(self)
        yield DispersyTestFunc.setUp(self)

    def tearDown(self):
        Session.del_instance()
        DispersyTestFunc.tearDown(self)
        AbstractServer.tearDown(self)

    def test_on_tunnel_remove_circuit(self):
        """
        Test the on_tunnel_remove handler function for a circuit
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        target_node = self._create_target(other, node)
        tunnel_node = Circuit(long(0), 0)
        tunnel_other = Circuit(long(0), 0)
        up = 12
        down = 14
        tunnel_node.bytes_up = up * 1024 * 1024
        tunnel_node.bytes_down = down * 1024 * 1024
        tunnel_other.bytes_up = down * 1024 * 1024
        tunnel_other.bytes_down = up * 1024 * 1024
        # Act
        node.call(node.community.on_tunnel_remove, None, None, tunnel_node, target_other)
        other.call(other.community.on_tunnel_remove, None, None, tunnel_other, target_node)
        # Assert
        # Since there is a tie breaker for requests, exactly one of the nodes should send a signature request
        failures = 0
        try:
            _, signature_request = other.receive_message(names=[SIGNED]).next()
            other.give_message(signature_request, node)
            _, signature_response = node.receive_message(names=[HALF_BLOCK]).next()
            node.give_message(signature_response, node)
        except StopIteration:
            failures += 1
        try:
            _, signature_request = node.receive_message(names=[SIGNED]).next()
            node.give_message(signature_request, other)
            _, signature_response = other.receive_message(names=[HALF_BLOCK]).next()
            other.give_message(signature_response, other)
        except StopIteration:
            failures += 1
        self.assertEquals(failures, 1)
#        self.assertEqual((up, down), node.call(node.community._get_next_total, 0, 0))
#        self.assertEqual((down, up), other.call(other.community._get_next_total, 0, 0))

    def test_on_tunnel_remove_relay(self):
        """
        Test the on_tunnel_remove handler function for a relay
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        target_node = self._create_target(other, node)
        tunnel_node = RelayRoute(None, None, None)
        tunnel_other = RelayRoute(None, None, None)
        up = 12
        down = 14
        tunnel_node.bytes_up = up * 1024 * 1024
        tunnel_node.bytes_down = down * 1024 * 1024
        tunnel_other.bytes_up = down * 1024 * 1024
        tunnel_other.bytes_down = up * 1024 * 1024
        # Act
        node.call(node.community.on_tunnel_remove, None, None, tunnel_node, target_other)
        other.call(other.community.on_tunnel_remove, None, None, tunnel_other, target_node)
        # Assert
        # Since there is a tie breaker for requests, exactly one of the nodes should send a signature request
        failures = 0
        try:
            _, signature_request = other.receive_message(names=[SIGNED]).next()
            other.give_message(signature_request, node)
            _, signature_response = node.receive_message(names=[HALF_BLOCK]).next()
            node.give_message(signature_response, node)
        except StopIteration:
            failures += 1
        try:
            _, signature_request = node.receive_message(names=[SIGNED]).next()
            node.give_message(signature_request, other)
            _, signature_response = other.receive_message(names=[HALF_BLOCK]).next()
            other.give_message(signature_response, other)
        except StopIteration:
            failures += 1
        self.assertEquals(failures, 1)
#        self.assertEqual((up, down), node.call(node.community._get_next_total, 0, 0))
#        self.assertEqual((down, up), other.call(other.community._get_next_total, 0, 0))

    def test_on_tunnel_remove_exit(self):
        """
        Test the on_tunnel_remove handler function
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        target_node = self._create_target(other, node)
        tunnel_node = TunnelExitSocket(None, None, None)
        tunnel_other = TunnelExitSocket(None, None, None)
        up = 12
        down = 14
        tunnel_node.bytes_up = up * 1024 * 1024
        tunnel_node.bytes_down = down * 1024 * 1024
        tunnel_other.bytes_up = down * 1024 * 1024
        tunnel_other.bytes_down = up * 1024 * 1024

        # Act
        node.call(node.community.on_tunnel_remove, None, None, tunnel_node, target_other)
        other.call(other.community.on_tunnel_remove, None, None, tunnel_other, target_node)
        # Assert
        # Since there is a tie breaker for requests, exactly one of the nodes should send a signature request
        failures = 0
        try:
            _, signature_request = other.receive_message(names=[SIGNED]).next()
            other.give_message(signature_request, node)
            _, signature_response = node.receive_message(names=[HALF_BLOCK]).next()
            node.give_message(signature_response, node)
        except StopIteration:
            failures += 1
        try:
            _, signature_request = node.receive_message(names=[SIGNED]).next()
            node.give_message(signature_request, other)
            _, signature_response = other.receive_message(names=[HALF_BLOCK]).next()
            other.give_message(signature_response, other)
        except StopIteration:
            failures += 1
        self.assertEquals(failures, 1)
#        self.assertEqual((up, down), node.call(node.community._get_next_total, 0, 0))
#        self.assertEqual((down, up), other.call(other.community._get_next_total, 0, 0))

    @raises(AssertionError)
    def test_on_tunnel_remove_NoneType(self):
        """
        Test the on_tunnel_remove handler function to handle a NoneType
        """
        node, other = self.create_nodes(2)
        node.call(node.community.on_tunnel_remove, None, None, None, None)

    def test_sign_block(self):
        """
        Test the community to publish a signature request message.
        """
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        # Act
        node.call(node.community.sign_block, target_other, 5, 5)
        # Assert
        _, message = other.receive_message(names=[SIGNED]).next()
        self.assertTrue(message)

    def test_sign_block_missing_member(self):
        """
        Test the sign_block function with a missing member
        """
        # Arrange
        def mocked_publish_sig(*_):
            raise DelayPacketByMissingMember(node.community, 'a' * 20)

        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        node.community.dispersy.store_update_forward = mocked_publish_sig
        # Act
        node.call(node.community.sign_block, target_other, 10, 10)

    def test_receive_signature_request_and_response(self):
        """
        Test the community to receive a signature request and a signature response message.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        node.call(node.community.sign_block, target_other, 10, 5)
        # Assert: Block should now be in the database of the node as halfsigned
        node.call(node.community.persistence.get_latest, node.community._public_key)
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_request = other.receive_message(names=[SIGNED]).next()
        # Act
        other.give_message(signature_request, node)
        # Return the response.
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_response = node.receive_message(names=[HALF_BLOCK]).next()
        node.give_message(signature_response, node)
        # Assert
        self.assertBlocksInDatabase(other, 2)
        self.assertBlocksInDatabase(node, 2)
        self.assertBlocksAreEqual(node, other)

        block = node.call(node.community.persistence.get_latest, node.community._public_key)
        linked = node.call(node.community.persistence.get_linked, block)
        self.assertNotEquals(linked, None)

        block = other.call(other.community.persistence.get_latest, other.community._public_key)
        linked = other.call(other.community.persistence.get_linked, block)
        self.assertNotEquals(linked, None)

    def test_block_values(self):
        """
        If a block is created between two nodes both
        should have the correct total_up and total_down of the signature request.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)

        node.call(node.community.sign_block, target_other, 10, 5)
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_request = other.receive_message(names=[SIGNED]).next()
        # Act
        other.give_message(signature_request, node)
        # Return the response.
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_response = node.receive_message(names=[HALF_BLOCK]).next()
        node.give_message(signature_response, other)
        # Assert
        block = node.call(MultiChainBlock.create, node.community.persistence, node.community._public_key)
        self.assertEqual(10, block.total_up)
        self.assertEqual(5, block.total_down)
        """ The up and down values are reversed for the responder. """
        block = other.call(MultiChainBlock.create, other.community.persistence, other.community._public_key)
        self.assertEqual(5, block.total_up)
        self.assertEqual(10, block.total_down)

    def test_block_values_after_request(self):
        """
        After a request is sent, a node should update its totals.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        node.call(node.community.sign_block, target_other, 10, 5)
        # Assert
        block = node.call(MultiChainBlock.create, node.community.persistence, node.community._public_key)
        self.assertEqual(10, block.total_up)
        self.assertEqual(5, block.total_down)

    def test_request_block_latest(self):
        """
        Test the crawler to request the latest block.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)
        other.send_identity(node)
        other.send_identity(crawler)
        node.send_identity(crawler)

        target_other_from_node = self._create_target(node, other)
        target_other_from_crawler = self._create_target(crawler, other)

        node.call(node.community.sign_block, target_other_from_node, 5, 5)
        """ Create a block"""
        _, signature_request = other.receive_message(names=[SIGNED]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[HALF_BLOCK]).next()
        node.give_message(signature_response, node)
        # Act
        crawler.call(crawler.community.send_crawl_request, target_other_from_crawler)
        _, block_request = other.receive_message(names=[CRAWL]).next()
        other.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[FULL_BLOCK]).next()
        crawler.give_message(block_response, other)
        # Assert
        self.assertBlocksInDatabase(node, 2)
        self.assertBlocksInDatabase(crawler, 2)
        self.assertBlocksAreEqual(node, crawler)

    def test_request_block_halfsigned(self):
        """
        Test the crawler to request a halfsigned block.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)
        other.send_identity(node)
        other.send_identity(crawler)
        node.send_identity(crawler)

        target_other_from_node = self._create_target(node, other)
        target_node_from_crawler = self._create_target(crawler, node)

        # Create a half-signed block
        node.call(node.community.sign_block, target_other_from_node, 5, 5)
        # Act
        crawler.call(crawler.community.send_crawl_request, target_node_from_crawler)
        _, block_request = node.receive_message(names=[CRAWL]).next()
        node.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[HALF_BLOCK]).next()
        crawler.give_message(block_response, node)
        # Assert
        self.assertBlocksInDatabase(node, 1)
        self.assertBlocksInDatabase(crawler, 1)

    def test_request_block_specified_sequence_number(self):
        """
        Test the crawler to fetch a block with a specified sequence number.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)
        other.send_identity(node)
        other.send_identity(crawler)
        node.send_identity(crawler)

        target_other_from_node = self._create_target(node, other)
        target_other_from_crawler = self._create_target(crawler, other)
        node.call(node.community.sign_block, target_other_from_node, 5, 5)
        """ Create a block"""
        _, signature_request = other.receive_message(names=[SIGNED]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[HALF_BLOCK]).next()
        node.give_message(signature_response, node)
        # Act
        crawler.call(crawler.community.send_crawl_request, target_other_from_crawler, 1)
        _, block_request = other.receive_message(names=[CRAWL]).next()
        other.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[FULL_BLOCK]).next()
        crawler.give_message(block_response, other)
        # Assert
        self.assertBlocksInDatabase(node, 2)
        self.assertBlocksInDatabase(crawler, 2)
        self.assertBlocksAreEqual(node, crawler)

    def test_crawler_no_block(self):
        """
        Test publish_block without a block.
        """
        # Arrange
        node, crawler = self.create_nodes(2)
        node.send_identity(crawler)
        target_node = self._create_target(crawler, node)
        # Act
        crawler.call(crawler.community.send_crawl_request, target_node)
        _, block_request = node.receive_message(names=[CRAWL]).next()
        node.give_message(block_request, crawler)

        with self.assertRaises(ValueError):
            "No signature responses should have been sent"
            _, block_responses = crawler.receive_message(names=[FULL_BLOCK])

    def test_request_block_known(self):
        """
        Test the crawler to request a known block.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)
        other.send_identity(node)
        other.send_identity(crawler)
        node.send_identity(crawler)

        target_other_from_node = self._create_target(node, other)
        target_other_from_crawler = self._create_target(crawler, other)
        target_node_from_crawler = self._create_target(crawler, node)
        node.call(node.community.sign_block, target_other_from_node, 5, 5)
        """ Create a block"""
        _, signature_request = other.receive_message(names=[SIGNED]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[HALF_BLOCK]).next()
        node.give_message(signature_response, node)
        # Request the block
        crawler.call(crawler.community.send_crawl_request, target_other_from_crawler)
        _, block_request = other.receive_message(names=[CRAWL]).next()
        other.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[FULL_BLOCK]).next()
        crawler.give_message(block_response, other)

        # Act
        # Request the same block
        crawler.call(crawler.community.send_crawl_request, target_node_from_crawler)
        _, block_request = node.receive_message(names=[CRAWL]).next()
        node.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[FULL_BLOCK]).next()
        crawler.give_message(block_response, node)
        # Assert
        self.assertBlocksInDatabase(node, 2)
        self.assertBlocksInDatabase(crawler, 2)
        self.assertBlocksAreEqual(node, crawler)

    def test_crawl_batch(self):
        """
        Test the crawler for fetching multiple blocks in one crawl.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)
        other.send_identity(node)
        other.send_identity(crawler)
        node.send_identity(crawler)

        target_other_from_node = self._create_target(node, other)
        target_node_from_crawler = self._create_target(crawler, node)

        """ Create blocks"""
        node.call(node.community.sign_block, target_other_from_node, 5, 5)
        _, signature_request = other.receive_message(names=[SIGNED]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[HALF_BLOCK]).next()
        node.give_message(signature_response, node)
        node.call(node.community.sign_block, target_other_from_node, 5, 5)
        _, signature_request = other.receive_message(names=[SIGNED]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[HALF_BLOCK]).next()
        node.give_message(signature_response, node)

        # Act
        # Request the same block
        crawler.call(crawler.community.send_crawl_request, target_node_from_crawler)
        _, block_request = node.receive_message(names=[CRAWL]).next()
        node.give_message(block_request, crawler)
        for _, block_response in crawler.receive_message(names=[FULL_BLOCK, RESUME]):
            crawler.give_message(block_response, node)
            print "Got another block, %s" % block_response

        _, block_request = node.receive_message(names=[CRAWL]).next()
        node.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[FULL_BLOCK]).next()
        crawler.give_message(block_response, node)

        # Assert
        self.assertBlocksInDatabase(node, 4)
        self.assertBlocksInDatabase(crawler, 4)
        self.assertBlocksAreEqual(node, crawler)

    def test_crawler_on_introduction_received(self):
        """
        Test the crawler takes a step when an introduction is made by the walker
        """
        # Arrange
        MultiChainCommunityCrawler.CrawlerDelay = 10000000
        crawler = super(TestMultiChainCommunity, self).create_nodes(1, community_class=MultiChainCommunityCrawler,
                                                                    memory_database=False)[0]
        node, = self.create_nodes(1)
        node._community.cancel_pending_task("take fast steps")
        node._community.cancel_pending_task("take step")
        node._community.cancel_pending_task("start_walking")
        target_node_from_crawler = self._create_target(node, crawler)

        intro_request_info = crawler.call(IntroductionRequestCache , crawler.community, None)
        intro_response = node.create_introduction_response(target_node_from_crawler, node.lan_address, node.wan_address,
                                                           node.lan_address, node.wan_address,
                                                           u"unknown", False, intro_request_info.number)
        intro_response._candidate = target_node_from_crawler
        crawler.community.request_cache._identifiers[
            crawler.community.request_cache._create_identifier(intro_request_info.number, u"introduction-request")
        ] = intro_request_info

        counter = [0]
        def replacement(cand):
            counter[0] += 1
        crawler._community.send_crawl_request = replacement

        # Act
        crawler.call(crawler.community.on_introduction_response, [intro_response])

        # Assert
        self.assertEqual(counter[0], 1)

    def test_get_statistics_no_blocks(self):
        """
        Test the get_statistics method where last block is none
        """
        node, = self.create_nodes(1)
        statistics = node.community.get_statistics()
        assert isinstance(statistics, dict), type(statistics)
        assert len(statistics) > 0

    def test_get_statistics_with_previous_block(self):
        """
        Test the get_statistics method where a last block exists
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        # Create a (halfsigned) block
        node.call(node.community.publish_signature_request_message, target_other, 10, 5)
        # Get statistics
        statistics = node.community.get_statistics()
        assert isinstance(statistics, dict), type(statistics)
        assert len(statistics) > 0

    @blocking_call_on_reactor_thread
    def assertBlocksInDatabase(self, node, amount):
        assert node.community.persistence.execute(u"SELECT COUNT(*) FROM multi_chain").fetchone()[0] == amount

    @blocking_call_on_reactor_thread
    def assertBlocksAreEqual(self, node, other):
        map(self.assertEqual_block,
            node.community.persistence.get_blocks_since(node.community._public_key, 0),
            other.community.persistence.get_blocks_since(node.community._public_key, 0))
        map(self.assertEqual_block,
            node.community.persistence.get_blocks_since(other.community._public_key, 0),
            other.community.persistence.get_blocks_since(other.community._public_key, 0))

    def create_nodes(self, *args, **kwargs):
        return super(TestMultiChainCommunity, self).create_nodes(*args, community_class=MultiChainCommunity,
                                                                 memory_database=False, **kwargs)

    def _create_node(self, dispersy, community_class, c_master_member):
        return DebugNode(self, dispersy, community_class, c_master_member, curve=u"curve25519")

    @blocking_call_on_reactor_thread
    def _create_target(self, source, destination):
        target = destination.my_candidate
        target.associate(source._dispersy.get_member(public_key=destination.my_pub_member.public_key))
        return target
