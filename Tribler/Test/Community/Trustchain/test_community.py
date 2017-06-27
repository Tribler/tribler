"""
This file contains the tests for the community.py for TrustChain community.
"""
import time

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.threads import blockingCallFromThread

from Tribler.Test.Community.Trustchain.test_trustchain_utilities import TrustChainTestCase
from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.trustchain.block import GENESIS_SEQ
from Tribler.community.trustchain.community import (TrustChainCommunity, HALF_BLOCK, CRAWL)
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.message import DelayPacketByMissingMember
from Tribler.dispersy.requestcache import IntroductionRequestCache
from Tribler.dispersy.tests.debugcommunity.node import DebugNode
from Tribler.dispersy.tests.dispersytestclass import DispersyTestFunc
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class BaseTestTrustChainCommunity(TrustChainTestCase, DispersyTestFunc):
    """
    Base class of the TrustChain tests.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        AbstractServer.setUp(self)
        yield DispersyTestFunc.setUp(self)

    def tearDown(self):
        DispersyTestFunc.tearDown(self)
        AbstractServer.tearDown(self)

    @blocking_call_on_reactor_thread
    def assertBlocksInDatabase(self, node, amount):
        db_name = node.community.persistence.db_name
        count = node.community.persistence.execute(u"SELECT COUNT(*) FROM %s" % db_name).fetchone()[0]
        assert count == amount, "Wrong number of blocks in database, was {0} but expected {1}".format(count, amount)

    @blocking_call_on_reactor_thread
    def assertBlocksAreEqual(self, node, other):
        map(self.assertEqual_block,
            node.community.persistence.crawl(node.community.my_member.public_key, 0),
            other.community.persistence.crawl(node.community.my_member.public_key, 0))
        map(self.assertEqual_block,
            node.community.persistence.crawl(other.community.my_member.public_key, 0),
            other.community.persistence.crawl(other.community.my_member.public_key, 0))

    @blocking_call_on_reactor_thread
    def get_node_sq_from_db(self, node, sq_owner_node, sequence_number):
        return node.community.persistence.get(sq_owner_node.community.my_member.public_key, sequence_number)

    @staticmethod
    def create_block(req, resp, target_resp, transaction):
        req.call(req.community.sign_block, target_resp, resp.my_member.public_key, transaction)

        # Process packets until there are no more to process. This should give enough margin to allow for a crawl
        # during block creation + retry of block signing.
        rounds = 13
        while rounds > 0:
            responder_packets = resp.process_packets(timeout=0.2)
            requester_packets = req.process_packets(timeout=0.2)
            if len(responder_packets if responder_packets else []) + \
                    len(requester_packets if requester_packets else []) == 0:
                rounds -= 1

    @staticmethod
    def crawl_node(crawler, crawlee, target_to_crawlee, sequence_number=None):
        crawler.call(crawler.community.send_crawl_request,
                     target_to_crawlee, crawlee.my_member.public_key, sequence_number)
        crawlee.give_message(crawlee.receive_message(names=[CRAWL]).next()[1], crawler)
        TestTrustChainCommunity.transport_halfblocks(crawlee, crawler)

    @staticmethod
    def transport_halfblocks(source, destination):
        count = -1
        while count != 0:
            count = 0
            try:
                gen = destination.receive_message(names=[HALF_BLOCK])
                message = gen.next()[1]
                while message:
                    count += 1
                    destination.give_message(message, source)
                    message = gen.next()[1]
            except StopIteration:
                pass

    @staticmethod
    @blocking_call_on_reactor_thread
    def clean_database(node):
        node.community.persistence.execute(u"DELETE FROM %s;" % node.community.persistence.db_name)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def create_nodes(self, *args, **kwargs):
        nodes = yield super(BaseTestTrustChainCommunity, self).create_nodes(*args, community_class=TrustChainCommunity,
                                                                            memory_database=False, **kwargs)
        for outer in nodes:
            for inner in nodes:
                if outer != inner:
                    outer.send_identity(inner)

        returnValue(nodes)

    def _create_node(self, dispersy, community_class, c_master_member):
        return DebugNode(self, dispersy, community_class, c_master_member, curve=u"curve25519")

    @blocking_call_on_reactor_thread
    def _create_target(self, source, destination):
        target = destination.my_candidate
        target.associate(source._dispersy.get_member(public_key=destination.my_pub_member.public_key))
        return target


class TestTrustChainCommunity(BaseTestTrustChainCommunity):
    """
    Class that tests the TrustChainCommunity on an integration level.
    """

    def test_sign_block(self):
        """
        Test the community to send a signature request message.
        """
        node, other = self.create_nodes(2)
        target_other = self._create_target(node, other)
        # Act
        node.call(node.community.sign_block, target_other, other.my_member.public_key, {"id": 42})
        # Assert
        _, message = other.receive_message(names=[HALF_BLOCK]).next()
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
        node.call(node.community.sign_block, target_other, other.my_member.public_key, {"id": 42})

    def test_sign_invalid_block(self):
        """
        Test the community to publish a signature request message.
        """
        node, other = self.create_nodes(2)
        target_other = self._create_target(node, other)
        # Act
        node.call(node.community.sign_block, target_other, 'a' * 10, {"id": 42})
        # Assert

        with self.assertRaises(StopIteration):
            # No signature requests
            other.receive_message(names=[HALF_BLOCK]).next()

    def test_receive_signature_request_and_response(self):
        """
        Test the community to receive a signature request and a signature response message.
        """
        # Arrange
        node, other = self.create_nodes(2)

        # Act
        TestTrustChainCommunity.create_block(node, other, self._create_target(node, other), {"id": 42})

        # Assert
        self.assertBlocksInDatabase(other, 2)
        self.assertBlocksInDatabase(node, 2)
        self.assertBlocksAreEqual(node, other)

        block = node.call(node.community.persistence.get_latest, node.community.my_member.public_key)
        linked = node.call(node.community.persistence.get_linked, block)
        self.assertIsNotNone(block.transaction)
        self.assertIsNotNone(linked.transaction)
        self.assertNotEquals(linked, None)

        block = other.call(other.community.persistence.get_latest, other.community.my_member.public_key)
        linked = other.call(other.community.persistence.get_linked, block)
        self.assertNotEquals(linked, None)

    def test_crawl_on_partial(self):
        """
        Test that a crawl is requested if the signer cannot validate the previous hash of a request
        """
        # Arrange
        node, other, another = self.create_nodes(3)

        # Act
        TestTrustChainCommunity.create_block(node, other, self._create_target(node, other), {"id": 42})

        node.call(node.community.sign_block, self._create_target(node, another),
                  another.my_member.public_key, {"id": 42})
        another.give_message(another.receive_message(names=[HALF_BLOCK]).next()[1], node)

        # Assert
        message = node.receive_message(names=[CRAWL]).next()[1]
        self.assertTrue(message)

    def test_crawl_not_double(self):
        """
        Test that a crawl is not send multiple times when a crawl is already happening as a result of an incoming block
        """
        # Arrange
        node, other, another = self.create_nodes(3)

        # Act
        TestTrustChainCommunity.create_block(node, other, self._create_target(node, other), {"id": 42})
        node.call(node.community.sign_block, self._create_target(node, another),
                  another.my_member.public_key, {"id": 42})
        message = another.receive_message(names=[HALF_BLOCK]).next()[1]
        # this triggers the crawl
        another.give_message(message, node)
        TestTrustChainCommunity.clean_database(another)
        # this should not trigger another crawl
        another.give_message(message, node)

        # Assert
        self.assertTrue(node.receive_message(names=[CRAWL]).next()[1])
        with self.assertRaises(StopIteration):
            self.assertFalse(node.receive_message(names=[CRAWL]).next()[1])

    def test_crawl_on_partial_complete(self):
        """
        Test that a crawl is requested and serviced if the signer cannot validate the previous hash of a request
        """
        # Arrange
        node, other, another = self.create_nodes(3)

        # Act
        TestTrustChainCommunity.create_block(node, other, self._create_target(node, other), {"id": 42})
        TestTrustChainCommunity.create_block(node, another, self._create_target(node, another), {"id": 42})

        # Assert
        self.assertBlocksInDatabase(node, 4)
        self.assertBlocksInDatabase(other, 2)
        self.assertBlocksInDatabase(another, 4)
        self.assertBlocksAreEqual(node, another)

    def test_crawl_block_latest(self):
        """
        Test the crawler to request the latest block.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)

        # Act
        TestTrustChainCommunity.create_block(node, other, self._create_target(node, other), {"id": 42})
        TestTrustChainCommunity.crawl_node(crawler, node, self._create_target(crawler, node))

        # Assert
        self.assertBlocksInDatabase(node, 2)
        self.assertBlocksInDatabase(crawler, 2)
        self.assertBlocksAreEqual(node, crawler)

    def test_crawl_block_specified_sequence_number(self):
        """
        Test the crawler to fetch a block with a specified sequence number.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)

        # Act
        TestTrustChainCommunity.create_block(node, other, self._create_target(node, other), {"id": 42})
        TestTrustChainCommunity.crawl_node(crawler, node, self._create_target(crawler, node), GENESIS_SEQ)

        # Assert
        self.assertBlocksInDatabase(node, 2)
        self.assertBlocksInDatabase(crawler, 2)
        self.assertBlocksAreEqual(node, crawler)

    def test_crawl_blocks_negative_sequence_number(self):
        """
        Test the crawler to fetch blocks starting from a negative sequence number.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)

        # Act
        TestTrustChainCommunity.create_block(node, other, self._create_target(node, other), {}) # sq 1
        TestTrustChainCommunity.create_block(node, other, self._create_target(node, other), {}) # sq 2
        TestTrustChainCommunity.create_block(node, other, self._create_target(node, other), {}) # sq 3

        self.clean_database(crawler)
        self.assertBlocksInDatabase(crawler, 0)
        TestTrustChainCommunity.crawl_node(crawler, node, self._create_target(crawler, node), -2)

        # Assert
        self.assertBlocksInDatabase(node, 6)
        self.assertBlocksInDatabase(crawler, 4)
        self.assertIsNone(self.get_node_sq_from_db(crawler, node, 1))
        self.assertIsNone(self.get_node_sq_from_db(crawler, other, 1))
        self.assertIsNotNone(self.get_node_sq_from_db(crawler, node, 2))
        self.assertIsNotNone(self.get_node_sq_from_db(crawler, other, 2))
        self.assertIsNotNone(self.get_node_sq_from_db(crawler, node, 3))
        self.assertIsNotNone(self.get_node_sq_from_db(crawler, other, 3))

    def test_crawl_no_block(self):
        """
        Test crawl without a block.
        """
        # Arrange
        node, crawler = self.create_nodes(2)

        # Act
        TestTrustChainCommunity.crawl_node(crawler, node, self._create_target(crawler, node))

        self.assertBlocksInDatabase(node, 0)
        self.assertBlocksInDatabase(crawler, 0)

    def test_crawl_block_known(self):
        """
        Test the crawler to request a known block.
        """
        # Arrange
        node, other, crawler = self.create_nodes(3)

        TestTrustChainCommunity.create_block(node, other, self._create_target(node, other), {"id": 42})
        TestTrustChainCommunity.crawl_node(crawler, other, self._create_target(crawler, other))

        # Act
        # Request the same blocks form different node
        TestTrustChainCommunity.crawl_node(crawler, node, self._create_target(crawler, node))

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
        target_other = self._create_target(node, other)

        TestTrustChainCommunity.create_block(node, other, target_other, {"id": 42})
        TestTrustChainCommunity.create_block(node, other, target_other, {"id": 42})

        # Act
        # Request the same block
        TestTrustChainCommunity.crawl_node(crawler, node, self._create_target(crawler, node))

        # Assert
        self.assertBlocksInDatabase(node, 4)
        self.assertBlocksInDatabase(other, 4)
        self.assertBlocksInDatabase(crawler, 4)
        self.assertBlocksAreEqual(node, other)
        self.assertBlocksAreEqual(node, crawler)
        self.assertBlocksAreEqual(other, crawler)

    def test_get_trust(self):
        """
        Test that the trust nodes have for each other is the sum of the length of both chains.
        """
        # Arrange
        node, other = self.create_nodes(2)
        transaction = {}
        TestTrustChainCommunity.create_block(node, other, self._create_target(node, other), transaction)
        TestTrustChainCommunity.create_block(other, node, self._create_target(other, node), transaction)

        # Get statistics
        node_trust = blockingCallFromThread(reactor, node.community.get_trust, other.community.my_member)
        other_trust = blockingCallFromThread(reactor, other.community.get_trust, node.community.my_member)
        self.assertEqual(node_trust, 2)
        self.assertEqual(other_trust, 2)

    def test_get_default_trust(self):
        """
        Test that the trust between nodes without blocks is 1.
        """
        # Arrange
        node, other = self.create_nodes(2)

        # Get statistics
        node_trust = blockingCallFromThread(reactor, node.community.get_trust, other.community.my_member)
        other_trust = blockingCallFromThread(reactor, other.community.get_trust, node.community.my_member)
        self.assertEqual(node_trust, 1)
        self.assertEqual(other_trust, 1)

    def test_live_edge_bootstrapping(self):
        """
        A node without trust for anyone should still find a candidate.
        """
        # Arrange
        node, other = self.create_nodes(2)
        candidate = node.community.create_or_update_walkcandidate(other.my_candidate.sock_addr,
                                                                  other.my_candidate.sock_addr,
                                                                  ('0.0.0.0', 0),
                                                                  other.my_candidate.tunnel,
                                                                  u"unknown")
        candidate.associate(other.community.my_member)
        candidate.walk_response(time.time())

        # Assert
        intro = blockingCallFromThread(reactor, node.community.dispersy_get_introduce_candidate,
                                       node.my_candidate)
        self.assertIsNotNone(intro)
        self.assertIsInstance(intro, Candidate)
        self.assertEqual(intro, candidate)

    def test_live_edge_recommend_valid(self):
        """
        Live edges should never include invalid/old candidates.
        """
        # Arrange
        node, other, another = self.create_nodes(3)

        # Stop the community from walking/crawling once it gets reactor control
        node.community.cancel_all_pending_tasks()
        node.community.reset_live_edges()
        node.community.candidates.clear()

        candidate = node.community.create_or_update_walkcandidate(other.my_candidate.sock_addr,
                                                                  other.my_candidate.sock_addr,
                                                                  ('0.0.0.0', 0),
                                                                  other.my_candidate.tunnel,
                                                                  u"unknown")
        candidate.associate(other.community.my_member)
        candidate.walk_response(time.time())

        node.community.create_or_update_walkcandidate(another.my_candidate.sock_addr,
                                                      another.my_candidate.sock_addr,
                                                      ('0.0.0.0', 0),
                                                      another.my_candidate.tunnel,
                                                      u"unknown")

        # Assert
        intro = blockingCallFromThread(reactor, node.community.dispersy_get_introduce_candidate,
                                       node.my_candidate)
        self.assertIsNotNone(intro)
        self.assertIsInstance(intro, Candidate)
        self.assertEqual(intro, candidate)

    def test_live_edge_callback_no_candidates(self):
        """
        Test live edges start with my member.
        """
        # Arrange
        node, = self.create_nodes(1)

        def check_live_edge(edge_id, candidates):
            self.assertEqual(1, edge_id)
            self.assertEqual(node.my_member.mid, candidates[0].get_member().mid)
            check_live_edge.called = True

        node.community.set_live_edge_callback(check_live_edge)

        # Stop the community from walking/crawling once it gets reactor control
        node.community.cancel_all_pending_tasks()
        node.community.reset_live_edges()

        # Act
        node.community.take_step()

        # Assert
        self.assertTrue(check_live_edge.called)

    def test_live_edge_callback(self):
        """
        Test creation and handling of a new live edge.
        """
        # Arrange
        node, other = self.create_nodes(2)

        # Create a cache, so our introduction response is expected by the node
        cache = object.__new__(IntroductionRequestCache)
        blockingCallFromThread(reactor, IntroductionRequestCache.__init__, cache,
                               node.community, other.my_candidate.sock_addr)
        cache = blockingCallFromThread(reactor, node.community.request_cache.add, cache)

        # Create the actual response message
        response = other.create_introduction_response(node.my_candidate,
                                                      other.my_candidate.sock_addr,
                                                      other.my_candidate.sock_addr,
                                                      ("0.0.0.0", 0),
                                                      ("0.0.0.0", 0),
                                                      u"unknown",
                                                      False,
                                                      cache.number)
        response._candidate = other.my_candidate # Fake its arrival from other

        def check_live_edge(edge_id, candidates):
            # We have no more valid candidates, increment id
            self.assertEqual(1, edge_id)
            # Start with our member
            self.assertEqual(node.my_member.mid, candidates[0].get_member().mid)
            # End with new member
            self.assertEqual(other.my_member.mid, candidates[1].get_member().mid)
            check_live_edge.called = True
        node.community.set_live_edge_callback(check_live_edge)

        # Act
        blockingCallFromThread(reactor, node.community.on_introduction_response, [response])

        # Assert
        self.assertTrue(check_live_edge.called)
