"""
This file contains the tests for the community.py for MultiChain community.
"""
import time
import uuid
import logging

from Tribler.community.multichain.community import MultiChainScheduler, MultiChainCommunity, CRAWL_REQUEST, CRAWL_RESPONSE, CRAWL_RESUME

from Tribler.Test.test_as_server import BaseTestCase

from Tribler.dispersy.tests.dispersytestclass import DispersyTestFunc
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.dispersy.tests.debugcommunity.node import DebugNode


class TestMultiChainScheduler(BaseTestCase):
    """
    Class that tests the MultiChainScheduler
    """

    data_threshold = MultiChainScheduler.threshold
    peer1 = ("127.0.0.1", 80)

    def __init__(self, *args, **kwargs):
        super(TestMultiChainScheduler, self).__init__(*args, **kwargs)

    class TestCandidate:
        """
        A mock candidate to test the MultiChainScheduler.
        """
        class TestMember:

            def __init__(self):
                self.mid = self.mid = uuid.uuid4()

        def __init__(self):
            self.member = self.TestMember()

        def get_member(self):
            return self.member

    class TestSchedulerCommunity:
        """
        A mock community to test the MultiChainScheduler.
        """

        def __init__(self, candidate):
            self.logger = logging.getLogger(self.__class__.__name__)
            self.signature_requested = False
            self.candidate = candidate
            self.publish_success = True
            self.up = None
            self.down = None
            return

        def get_candidate(self, peer):
            return self.candidate

        def publish_signature_request_message(self, candidate,  up, down):
            self.signature_requested = True
            self.up = up
            self.down = down
            return self.publish_success

    def setUp(self, annotate=True):
        super(TestMultiChainScheduler, self).setUp()
        self.candidate = self.TestCandidate()
        self.community = self.TestSchedulerCommunity(self.candidate)
        self.scheduler = MultiChainScheduler(self.community)

    def tearDown(self, annotate=True):
        super(TestMultiChainScheduler, self).tearDown()
        self.candidate = None
        self.community = None
        self.scheduler = None

    def test_update_amount_send_empty(self):
        """
        The scheduler can track the amount for a new candidate.
        """
        # Arrange
        amount = self.data_threshold / 2
        # Act
        self.scheduler.update_amount_send(self.peer1, amount)
        # Assert
        self.assertEqual(amount, self.scheduler._outstanding_amount_send[self.peer1])

    def test_update_amount_send_add(self):
        """
        The scheduler can track the amount when adding to a previous amount.
        """
        # Arrange
        first_amount = (self.data_threshold - 10) / 2
        second_amount = (self.data_threshold - 10) / 2
        self.scheduler.update_amount_send(self.peer1, first_amount)
        # Act
        self.scheduler.update_amount_send(self.peer1, second_amount)
        # Assert
        self.assertEqual(first_amount+second_amount,
                         self.scheduler._outstanding_amount_send[self.peer1])
        self.assertFalse(self.community.signature_requested)

    def test_update_amount_send_above_threshold(self):
        """
        The scheduler schedules a signature request if the amount is above the threshold.
        """
        # Arrange
        amount = self.data_threshold + 1000000
        # Act
        self.scheduler.update_amount_send(self.peer1, amount)
        # Assert
        """ No amount should be left open. """
        self.assertEqual(0, self.scheduler._outstanding_amount_send[self.peer1])
        self.assertTrue(self.community.signature_requested)

    def test_update_amount_send_remainder(self):
        """
        The scheduler should remember a remainder after converting to MB.
        """
        # Arrange
        remainder = 250
        amount = self.data_threshold + remainder
        # Act
        self.scheduler.update_amount_send(self.peer1, amount)
        # Assert
        """ The remainder should be left open. """
        self.assertEqual(remainder, self.scheduler._outstanding_amount_send[self.peer1])

    def test_update_amount_send_failed(self):
        """
        The scheduler schedules a signature request but fails and should remember the amount.
        """
        # Arrange
        amount = self.data_threshold + 10
        self.community.publish_success = False
        # Act
        self.scheduler.update_amount_send(self.peer1, amount)
        # Assert
        """ The whole amount should be left open."""
        self.assertEqual(amount, self.scheduler._outstanding_amount_send[self.peer1])
        self.assertTrue(self.community.signature_requested)

    def test_update_amount_received_empty(self):
        """
        The scheduler can track the amount for a new candidate.
        """
        # Arrange
        amount = self.data_threshold / 2
        # Act
        self.scheduler.update_amount_received(self.peer1, amount)
        # Assert
        self.assertEqual(amount, self.scheduler._outstanding_amount_received[self.peer1])
        self.assertFalse(self.community.signature_requested)

    def test_update_amount_received_add(self):
        """
        The scheduler can track the amount when adding to a previous amount.
        """
        # Arrange
        first_amount = (self.data_threshold - 10) / 2
        second_amount = (self.data_threshold - 10) / 2
        self.scheduler.update_amount_received(self.peer1, first_amount)
        # Act
        self.scheduler.update_amount_received(self.peer1, second_amount)
        # Assert
        self.assertEqual(first_amount+second_amount,
                         self.scheduler._outstanding_amount_received[self.peer1])
        self.assertFalse(self.community.signature_requested)

    def test_update_amount_received_above_threshold(self):
        """
        The scheduler does not schedule a signature request if the amount is above the threshold.
        """
        amount = self.data_threshold + 10
        # Act
        self.scheduler.update_amount_received(self.peer1, amount)
        # Assert
        """ No amount should be left open """
        self.assertEqual(amount, self.scheduler._outstanding_amount_received[self.peer1])
        self.assertFalse(self.community.signature_requested)

    def test_schedule_block(self):
        """
        The scheduler can schedule a block.
        """
        # Arrange
        sent = 4
        received = 4
        self.scheduler.update_amount_send(self.peer1, sent * MultiChainScheduler.mega_divider)
        self.scheduler.update_amount_received(self.peer1, received * MultiChainScheduler.mega_divider)
        # Act
        self.scheduler.schedule_block(self.peer1)
        # Assert
        self.assertTrue(self.community.signature_requested)
        self.assertEqual(sent, self.community.up)
        self.assertEqual(received, self.community.down)
        self.assertEqual(0, self.scheduler._outstanding_amount_received[self.peer1])
        self.assertEqual(0, self.scheduler._outstanding_amount_send[self.peer1])

    def test_schedule_block_negative(self):
        """
        The scheduler can deal with if a block cannot be sent.
        """
        # Arrange
        sent = 4
        received = 4
        self.scheduler.update_amount_send(self.peer1, sent * MultiChainScheduler.mega_divider)
        self.scheduler.update_amount_received(self.peer1, received * MultiChainScheduler.mega_divider)
        self.community.publish_success = False
        # Act
        self.scheduler.schedule_block(self.peer1)
        # Assert
        self.assertEqual(sent * MultiChainScheduler.mega_divider,
                         self.scheduler._outstanding_amount_received[self.peer1])
        self.assertEqual(received * MultiChainScheduler.mega_divider,
                         self.scheduler._outstanding_amount_send[self.peer1])


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

    def test_publish_signature_request_message_exclusion(self):
        """
        Test the community to not publish a signature request message if the chain exclusion is held.
        """
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        """ Set the chain exclusion. """
        node.community.chain_exclusion_flag = True
        # Act
        result = node.call(node.community.publish_signature_request_message, target_other, 5, 5)
        # Assert
        messages = other.receive_message(names=[u"dispersy-signature-request"])
        self.assertFalse(next(messages, False))
        self.assertFalse(result)

    def test_receive_signature_request_exclusion(self):
        """
        Test the community to not receive a signature request message if the chain exclusion is held.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)
        """ Set the chain exclusion. """
        other.community.chain_exclusion_flag = True
        node.call(node.community.publish_signature_request_message, target_other, 5, 5)
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        # Act
        other.give_message(signature_request, node)
        # Assert
        with self.assertRaises(ValueError):
            "No signature responses should have been sent"
            _, signature_responses = node.receive_message(names=[u"dispersy-signature-response"])
        self.assertTrue(self.assertBlocksInDatabase(other, 0))

    def test_receive_signature_response(self):
        """
        Test the community to receive a signature request message.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target_other = self._create_target(node, other)

        node.call(node.community.publish_signature_request_message, target_other, 5, 5)
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        # Act
        other.give_message(signature_request, node)
        """ Return the response. """
        # Ignore source, as it is a Candidate. We need to use DebugNodes in test.
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, node)
        # Assert
        self.assertFalse(other.community.chain_exclusion_flag)
        self.assertTrue(self.assertBlocksInDatabase(other, 1))
        self.assertTrue(self.assertBlocksInDatabase(node, 1))
        self.assertTrue(self.assertBlocksAreEqual(node, other))

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
        time.sleep(MultiChainCommunity.signature_request_timeout + 2)
        # Assert
        self.assertFalse(other.community.chain_exclusion_flag)
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
        return len(node.community.persistence.get_ids()) == amount

    @blocking_call_on_reactor_thread
    def assertBlocksAreEqual(self, node, other):
        ids_node = node.community.persistence.get_ids()
        ids_other = other.community.persistence.get_ids()
        return ids_node == ids_other

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
