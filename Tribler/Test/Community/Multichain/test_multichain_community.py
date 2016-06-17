"""
This file contains the tests for the community.py for MultiChain community.
"""
import time
from Tribler.Core.Session import Session
from Tribler.community.multichain.community import (MultiChainCommunity, MultiChainCommunityCrawler, CRAWL_REQUEST,
                                                    CRAWL_RESPONSE, CRAWL_RESUME)
from Tribler.community.multichain.conversion import EMPTY_HASH
from Tribler.community.tunnel.routing import Circuit, RelayRoute
from Tribler.community.tunnel.tunnel_community import TunnelExitSocket
from Tribler.Test.test_as_server import AbstractServer
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

    def setUp(self):
        Session.__single = self.MockSession()
        AbstractServer.setUp(self)
        DispersyTestFunc.setUp(self)

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
            _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
            other.give_message(signature_request, node)
            _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
            node.give_message(signature_response, node)
        except StopIteration:
            failures += 1
        try:
            _, signature_request = node.receive_message(names=[u"dispersy-signature-request"]).next()
            node.give_message(signature_request, other)
            _, signature_response = other.receive_message(names=[u"dispersy-signature-response"]).next()
            other.give_message(signature_response, other)
        except StopIteration:
            failures += 1
        self.assertEquals(failures, 1)
        self.assertEqual((up, down), node.call(node.community._get_next_total, 0, 0))
        self.assertEqual((down, up), other.call(other.community._get_next_total, 0, 0))

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
            _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
            other.give_message(signature_request, node)
            _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
            node.give_message(signature_response, node)
        except StopIteration:
            failures += 1
        try:
            _, signature_request = node.receive_message(names=[u"dispersy-signature-request"]).next()
            node.give_message(signature_request, other)
            _, signature_response = other.receive_message(names=[u"dispersy-signature-response"]).next()
            other.give_message(signature_response, other)
        except StopIteration:
            failures += 1
        self.assertEquals(failures, 1)
        self.assertEqual((up, down), node.call(node.community._get_next_total, 0, 0))
        self.assertEqual((down, up), other.call(other.community._get_next_total, 0, 0))

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
            _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
            other.give_message(signature_request, node)
            _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
            node.give_message(signature_response, node)
        except StopIteration:
            failures += 1
        try:
            _, signature_request = node.receive_message(names=[u"dispersy-signature-request"]).next()
            node.give_message(signature_request, other)
            _, signature_response = other.receive_message(names=[u"dispersy-signature-response"]).next()
            other.give_message(signature_response, other)
        except StopIteration:
            failures += 1
        self.assertEquals(failures, 1)
        self.assertEqual((up, down), node.call(node.community._get_next_total, 0, 0))
        self.assertEqual((down, up), other.call(other.community._get_next_total, 0, 0))

    def test_on_tunnel_remove_NoneType(self):
        """
        Test the on_tunnel_remove handler function to handle a NoneType
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        # Act
        try:
            node.call(node.community.on_tunnel_remove, None, None, None, None, None)
        except TypeError:
            error = True
        # Assert
        self.assertTrue(error)

    def test_schedule_block(self):
        """
        Test the schedule_block function.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        # Act
        node.call(node.community.schedule_block, target_other, 5 * 1024 * 1024, 10 * 1024 * 1024 + 42000)
        _, message = other.receive_message(names=[u"dispersy-signature-request"]).next()
        # Assert
        self.assertTrue(message)
        self.assertEqual((5, 10), node.call(node.community._get_next_total, 0, 0))

    def test_schedule_block_invalid_candidate(self):
        """
        Test the schedule_block function with an invalid candidate to cover all branches
        """
        # Arrange
        [node] = self.create_nodes(1)
        candidate = Candidate(("127.0.0.1", 10), False)
        # Act
        node.call(node.community.schedule_block, candidate, 0, 0)

    def test_publish_signature_request_message(self):
        """
        Test the community to publish a signature request message.
        """
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        # Act
        result = node.call(node.community.publish_signature_request_message, target_other, 5, 5)
        # Assert
        _, message = other.receive_message(names=[u"dispersy-signature-request"]).next()
        self.assertTrue(message)
        self.assertTrue(result)

    def test_receive_signature_request_and_response(self):
        """
        Test the community to receive a signature request and a signature response message.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        node.call(node.community.publish_signature_request_message, target_other, 10, 5)
        # Assert: Block should now be in the database of the node as halfsigned
        block = node.call(node.community.persistence.get_latest_block, node.community._public_key)
        self.assertEquals(block.hash_responder, EMPTY_HASH)
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        # Act
        other.give_message(signature_request, node)
        # Return the response.
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, node)
        # Assert
        self.assertBlocksInDatabase(other, 1)
        self.assertBlocksInDatabase(node, 1)
        self.assertBlocksAreEqual(node, other)

        block = node.call(node.community.persistence.get_latest_block, node.community._public_key)
        self.assertNotEquals(block.hash_responder, EMPTY_HASH)

        block = other.call(other.community.persistence.get_latest_block, other.community._public_key)
        self.assertNotEquals(block.hash_responder, EMPTY_HASH)

    def test_block_values(self):
        """
        If a block is created between two nodes both
        should have the correct total_up and total_down of the signature request.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)

        node.call(node.community.publish_signature_request_message, target_other, 10, 5)
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        # Act
        other.give_message(signature_request, node)
        # Return the response.
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, other)
        # Assert
        self.assertEqual((10, 5), node.call(node.community._get_next_total, 0, 0))
        # The up and down values are reversed for the responder.
        self.assertEqual((5, 10), other.call(other.community._get_next_total, 0, 0))

    def test_block_values_after_request(self):
        """
        After a request is sent, a node should update its totals.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        node.call(node.community.publish_signature_request_message, target_other, 10, 5)
        # Assert
        self.assertEqual((10, 5), node.call(node.community._get_next_total, 0, 0))

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

        node.call(node.community.publish_signature_request_message, target_other_from_node, 5, 5)
        # Create a block
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, node)
        # Act
        crawler.call(crawler.community.send_crawl_request, target_other_from_crawler)
        _, block_request = other.receive_message(names=[CRAWL_REQUEST]).next()
        other.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[CRAWL_RESPONSE]).next()
        crawler.give_message(block_response, other)
        # Assert
        self.assertBlocksInDatabase(node, 1)
        self.assertBlocksInDatabase(crawler, 1)
        self.assertBlocksAreEqual(node, crawler)

    def test_get_next_total_no_block(self):
        # Arrange
        node, other, = self.create_nodes(2)
        other.send_identity(node)
        up_previous, down_previous = 5, 5

        target_other = self._create_target(node, other)
        node.call(node.community.publish_signature_request_message, target_other, up_previous, down_previous)
        # Create a block
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, node)
        up, down = 500, 510
        # Act
        result_up, result_down = node.call(node.community._get_next_total, up, down)
        # assert
        self.assertEqual(up + up_previous, result_up)
        self.assertEqual(down + down_previous, result_down)

    def test_get_next_total_with_block(self):
        # Arrange
        node, = self.create_nodes(1)
        up, down = 500, 510
        # Act
        result_up, result_down = node.call(node.community._get_next_total, up, down)
        # assert
        self.assertEqual(up, result_up)
        self.assertEqual(down, result_down)

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
        node.call(node.community.publish_signature_request_message, target_other_from_node, 5, 5)
        # Create a block
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, node)
        # Act
        crawler.call(crawler.community.send_crawl_request, target_other_from_crawler, 0)
        _, block_request = other.receive_message(names=[CRAWL_REQUEST]).next()
        other.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[CRAWL_RESPONSE]).next()
        crawler.give_message(block_response, other)
        # Assert
        self.assertBlocksInDatabase(node, 1)
        self.assertBlocksInDatabase(crawler, 1)
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
        _, block_request = node.receive_message(names=[CRAWL_REQUEST]).next()
        node.give_message(block_request, crawler)

        with self.assertRaises(ValueError):
            "No signature responses should have been sent"
            _, block_responses = crawler.receive_message(names=[CRAWL_RESPONSE])

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
        node.call(node.community.publish_signature_request_message, target_other_from_node, 5, 5)
        # Create a block
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, node)
        # Request the block
        crawler.call(crawler.community.send_crawl_request, target_other_from_crawler)
        _, block_request = other.receive_message(names=[CRAWL_REQUEST]).next()
        other.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[CRAWL_RESPONSE]).next()
        crawler.give_message(block_response, other)

        # Act
        # Request the same block
        crawler.call(crawler.community.send_crawl_request, target_node_from_crawler)
        _, block_request = node.receive_message(names=[CRAWL_REQUEST]).next()
        node.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[CRAWL_RESPONSE]).next()
        crawler.give_message(block_response, node)
        # Assert
        self.assertBlocksInDatabase(node, 1)
        self.assertBlocksInDatabase(crawler, 1)
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
        target_other_from_crawler = self._create_target(crawler, other)
        target_node_from_crawler = self._create_target(crawler, node)

        # Create blocks
        node.call(node.community.publish_signature_request_message, target_other_from_node, 5, 5)
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, node)
        node.call(node.community.publish_signature_request_message, target_other_from_node, 5, 5)
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, node)

        # Act
        # Request the same block
        crawler.call(crawler.community.send_crawl_request, target_node_from_crawler)
        _, block_request = node.receive_message(names=[CRAWL_REQUEST]).next()
        node.give_message(block_request, crawler)
        for _, block_response in crawler.receive_message(names=[CRAWL_RESPONSE, CRAWL_RESUME]):
            crawler.give_message(block_response, node)
            print "Got another block, %s" % block_response

        _, block_request = node.receive_message(names=[CRAWL_REQUEST]).next()
        node.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[CRAWL_RESPONSE]).next()
        crawler.give_message(block_response, node)

        # Assert
        self.assertBlocksInDatabase(node, 2)
        self.assertBlocksInDatabase(crawler, 2)
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
        assert len(node.community.persistence.get_all_hash_requester()) == amount

    @blocking_call_on_reactor_thread
    def assertBlocksAreEqual(self, node, other):
        ids_node = node.community.persistence.get_all_hash_requester()
        ids_other = other.community.persistence.get_all_hash_requester()
        assert len(ids_node) == len(ids_other)
        blocks_node = map(node.community.persistence.get_by_hash_requester, ids_node)
        blocks_other = map(other.community.persistence.get_by_hash_requester, ids_other)

        for block_node, block_other in zip(blocks_node, blocks_other):
            assert block_node.hash_requester == block_other.hash_requester
            assert block_node.hash_responder == block_other.hash_responder

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
