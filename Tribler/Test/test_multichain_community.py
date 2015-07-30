"""
This file contains the tests for the community.py for MultiChain community.
"""
import time
import uuid
import logging

from Tribler.community.multichain.community import MultiChainScheduler, MultiChainCommunity, \
    BLOCK_REQUEST, BLOCK_RESPONSE

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
            return

        def get_candidate(self, peer):
            return self.candidate

        def publish_signature_request_message(self, candidate,  up, down):
            self.signature_requested = True
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
        amount = self.data_threshold + 10
        # Act
        self.scheduler.update_amount_send(self.peer1, amount)
        # Assert
        """ No amount should be left open """
        self.assertEqual(0, self.scheduler._outstanding_amount_send[self.peer1])
        self.assertTrue(self.community.signature_requested)

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


class TestMultiChainCommunity(DispersyTestFunc):
    """
    Class that tests the MultiChainCommunity on an integration level.
    """

    def __init__(self, *args, **kwargs):
        super(TestMultiChainCommunity, self).__init__(*args, **kwargs)

    def test_publish_signature_request_message(self):
        """
        Test the community to publish a signature request message.
        """
        node, other = self.create_nodes(2)
        other.send_identity(node)
        target = other.my_candidate
        target.associate(other.my_pub_member)
        # Act
        node.call(node.community.publish_signature_request_message, target, 5, 5)
        # Assert
        message = other.receive_message(names=[u"dispersy-signature-request"]).next()
        self.assertTrue(message)

    def test_receive_signature_response(self):
        """
        Test the community to receive a signature request message.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)

        target = other.my_candidate
        target.associate(other.my_pub_member)
        node.call(node.community.publish_signature_request_message, target, 5, 5)
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

    def test_signature_request_timeout(self):
        """"
        Test the community to timeout on a signature request message.
        """
        # Arrange
        node, other = self.create_nodes(2)
        other.send_identity(node)

        target = other.my_candidate
        target.associate(other.my_pub_member)
        # Act
        node.call(node.community.publish_signature_request_message, target, 5, 5)
        """" Wait for the timeout. """
        time.sleep(MultiChainCommunity.signature_request_timeout + 2)
        # Assert
        self.assertFalse(other.community.chain_exclusion_flag)
        self.assertTrue(self.assertBlocksInDatabase(node, 1))
        self.assertTrue(self.assertBlocksInDatabase(other, 0))

    def test_crawler(self):
        """
        Test the crawler methods.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)
        other.send_identity(node)
        other.send_identity(crawler)
        node.send_identity(crawler)

        target = other.my_candidate
        target.associate(other.my_pub_member)
        node.call(node.community.publish_signature_request_message, target, 5, 5)
        """ Create a block"""
        _, signature_request = other.receive_message(names=[u"dispersy-signature-request"]).next()
        other.give_message(signature_request, node)
        _, signature_response = node.receive_message(names=[u"dispersy-signature-response"]).next()
        node.give_message(signature_response, node)
        # Act
        crawler.call(crawler.community.publish_request_block_message, target)
        _, block_request = other.receive_message(names=[BLOCK_REQUEST]).next()
        other.give_message(block_request, crawler)
        _, block_response = crawler.receive_message(names=[BLOCK_RESPONSE]).next()
        crawler.give_message(block_response, other)
        # Assert
        self.assertTrue(self.assertBlocksInDatabase(other, 1))
        self.assertTrue(self.assertBlocksInDatabase(node, 1))
        self.assertTrue(self.assertBlocksInDatabase(crawler, 1))
        self.assertTrue(self.assertBlocksAreEqual(node, other))

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