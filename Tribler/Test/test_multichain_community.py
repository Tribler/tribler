"""
This file contains the tests for the community.py for MultiChain community.
"""
import time
import uuid
import logging

from Tribler.Core.Session import Session

from Tribler.community.multichain.community import  MultiChainCommunity, CRAWL_REQUEST, CRAWL_RESPONSE, CRAWL_RESUME
from Tribler.community.multichain.conversion import EMPTY_HASH

from Tribler.community.tunnel.routing import Circuit

from Tribler.Test.test_as_server import BaseTestCase

from Tribler.dispersy.tests.dispersytestclass import DispersyTestFunc
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.dispersy.tests.debugcommunity.node import DebugNode


class TestMultiChainCommunity(DispersyTestFunc):
    """
    Class that tests the MultiChainCommunity on an integration level.
    """
    """ This test class only runs if there is another testcase in this file."""

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
        message = other.receive_message(names=[u"dispersy-signature-request"]).next()
        self.assertTrue(message)
        self.assertTrue(result)

    def test_receive_signature_response(self):
        """
        Test the community to receive a signature request message.
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
        """ Return the response. """
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, node)
        # Assert
        self.assertTrue(self.assertBlocksInDatabase(other, 1))
        self.assertTrue(self.assertBlocksInDatabase(node, 1))
        self.assertTrue(self.assertBlocksAreEqual(node, other))

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
        """ Return the response. """
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, other)
        # Assert
        self.assertEqual((10, 5), node.call(node.community._get_next_total, 0, 0))
        """ The up and down values are reversed for the responder. """
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

    def test_signature_request_timeout(self):
        """"
        Test the community to timeout on a signature request message.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        # Act
        node.call(node.community.publish_signature_request_message, target_other, 5, 5)
        """" Wait for the timeout. """
        time.sleep(10 + 2)  # 10 seconds is the default timeout for a signature request in dispersy
        # Assert
        self.assertTrue(self.assertBlocksInDatabase(node, 1))
        self.assertTrue(self.assertBlocksInDatabase(other, 0))

    def test_request_block_latest(self):
        """
        Test the crawler methods.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)
        other.send_identity(node)
        other.send_identity(crawler)
        node.send_identity(crawler)

        target_other_from_node = self._create_target(node, other)
        target_other_from_crawler = self._create_target(crawler, other)

        node.call(node.community.publish_signature_request_message, target_other_from_node, 5, 5)
        """ Create a block"""
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
        self.assertTrue(self.assertBlocksInDatabase(node, 1))
        self.assertTrue(self.assertBlocksInDatabase(crawler, 1))
        self.assertTrue(self.assertBlocksAreEqual(node, crawler))

    def test_get_next_total_no_block(self):
        # Arrange
        node, other, = self.create_nodes(2)
        other.send_identity(node)
        up_previous, down_previous = 5, 5

        target_other = self._create_target(node, other)
        node.call(node.community.publish_signature_request_message, target_other, up_previous, down_previous)
        """ Create a block"""
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
        Test the crawler methods.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)
        other.send_identity(node)
        other.send_identity(crawler)
        node.send_identity(crawler)

        target_other_from_node = self._create_target(node, other)
        target_other_from_crawler = self._create_target(crawler, other)
        node.call(node.community.publish_signature_request_message, target_other_from_node, 5, 5)
        """ Create a block"""
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
        self.assertTrue(self.assertBlocksInDatabase(node, 1))
        self.assertTrue(self.assertBlocksInDatabase(crawler, 1))
        self.assertTrue(self.assertBlocksAreEqual(node, crawler))

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
        Test the crawler methods.
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
        """ Create a block"""
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, node)
        """ Request the block"""
        crawler.call(crawler.community.send_crawl_request, target_other_from_crawler)
        _, block_request = other.receive_message(names=[CRAWL_REQUEST]).next()
        other.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[CRAWL_RESPONSE]).next()
        crawler.give_message(block_response, other)

        # Act
        """ Request the same block."""
        crawler.call(crawler.community.send_crawl_request, target_node_from_crawler)
        _, block_request = node.receive_message(names=[CRAWL_REQUEST]).next()
        node.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[CRAWL_RESPONSE]).next()
        crawler.give_message(block_response, node)
        # Assert
        self.assertTrue(self.assertBlocksInDatabase(node, 1))
        self.assertTrue(self.assertBlocksInDatabase(crawler, 1))
        self.assertTrue(self.assertBlocksAreEqual(node, crawler))

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

        """ Create blocks"""
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
        """ Request the same block."""
        crawler.call(crawler.community.send_crawl_request, target_node_from_crawler)
        _, block_request = node.receive_message(names=[CRAWL_REQUEST]).next()
        node.give_message(block_request, crawler)
        for _, block_response in crawler.receive_message(names=[CRAWL_RESPONSE,CRAWL_RESUME]):
            crawler.give_message(block_response, node)
            print "Got another block, %s" % block_response

        _, block_request = node.receive_message(names=[CRAWL_REQUEST]).next()
        node.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[CRAWL_RESPONSE]).next()
        crawler.give_message(block_response, node)

        # Assert
        self.assertTrue(self.assertBlocksInDatabase(node, 2))
        self.assertTrue(self.assertBlocksInDatabase(crawler, 2))
        self.assertTrue(self.assertBlocksAreEqual(node, crawler))


    @blocking_call_on_reactor_thread
    def assertBlocksInDatabase(self, node, amount):
        return len(node.community.persistence.get_all_hash_requester()) == amount

    @blocking_call_on_reactor_thread
    def assertBlocksAreEqual(self, node, other):
        ids_node = node.community.persistence.get_all_hash_requester()
        ids_other = other.community.persistence.get_all_hash_requester()
        if len(ids_node) != len(ids_other):
            return False
        blocks_node = map(node.community.persistence.get_by_hash_requester, ids_node)
        blocks_other = map(other.community.persistence.get_by_hash_requester, ids_other)

        for block_node, block_other in zip(blocks_node, blocks_other):
            if block_node.hash_requester != block_other.hash_requester or \
               block_node.hash_responder != block_other.hash_responder:
                return False
        return True

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
