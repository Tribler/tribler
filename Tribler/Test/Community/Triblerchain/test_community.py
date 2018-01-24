from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import deferLater
from twisted.internet.threads import blockingCallFromThread

from Tribler.Test.Community.Trustchain.test_community import BaseTestTrustChainCommunity
from Tribler.Test.Community.Trustchain.test_trustchain_utilities import TrustChainTestCase
from Tribler.community.triblerchain.block import TriblerChainBlock
from Tribler.community.triblerchain.community import TriblerChainCommunity, PendingBytes, TriblerChainCommunityCrawler
from Tribler.community.trustchain.community import HALF_BLOCK, CRAWL
from Tribler.community.tunnel.routing import Circuit
from Tribler.dispersy.requestcache import IntroductionRequestCache
from Tribler.dispersy.tests.dispersytestclass import DispersyTestFunc
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestPendingBytes(TrustChainTestCase):
    """
    This class contains tests for the PendingBytes object
    """

    def test_add_pending_bytes(self):
        """
        Test adding to pending bytes
        """
        pending_bytes = PendingBytes(20, 30)
        self.assertTrue(pending_bytes.add(20, 30))
        self.assertFalse(pending_bytes.add(-100, -100))


class TestTriblerChainCommunity(BaseTestTrustChainCommunity):
    """
    Class that tests the TrustChainCommunity on an integration level.
    """

    @staticmethod
    def set_expectation(node, req, up, down):
        node.community.pending_bytes[req.community.my_member.public_key] = PendingBytes(down, up)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def create_nodes(self, *args, **kwargs):
        nodes = yield DispersyTestFunc.create_nodes(self, *args, community_class=TriblerChainCommunity,
                                                    memory_database=False, **kwargs)
        for outer in nodes:
            for inner in nodes:
                if outer != inner:
                    outer.send_identity(inner)

        returnValue(nodes)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_cleanup_pending_bytes(self):
        """
        Test cleaning of pending bytes
        """
        node, = yield self.create_nodes(1)
        node.community.pending_bytes['a'] = 1234
        self.assertIn('a', node.community.pending_bytes)
        node.community.cleanup_pending('a')
        self.assertNotIn('a', node.community.pending_bytes)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_on_tunnel_remove(self):
        """
        Test the on_tunnel_remove handler function for a circuit
        """
        # Arrange
        node, other = yield self.create_nodes(2)
        tunnel_node = Circuit(long(0), 0)
        tunnel_other = Circuit(long(0), 0)
        tunnel_node.bytes_up = tunnel_other.bytes_down = 12 * 1024 * 1024
        tunnel_node.bytes_down = tunnel_other.bytes_up = 14 * 1024 * 1024

        # Act
        node.call(node.community.on_tunnel_remove, None, None, tunnel_node, self._create_target(node, other))
        other.call(other.community.on_tunnel_remove, None, None, tunnel_other, self._create_target(other, node))
        yield deferLater(reactor, 5.1, lambda: None)

        # Assert
        _, signature_request = node.receive_message(names=[HALF_BLOCK]).next()
        node.give_message(signature_request, other)
        yield deferLater(reactor, 0.1, lambda: None)
        _, signature_request = other.receive_message(names=[HALF_BLOCK]).next()
        other.give_message(signature_request, node)
        yield deferLater(reactor, 0.1, lambda: None)

        self.assertBlocksInDatabase(node, 2)
        self.assertBlocksInDatabase(other, 2)
        self.assertBlocksAreEqual(node, other)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_on_tunnel_remove_small(self):
        """
        Test the on_tunnel_remove handler function for a circuit
        """
        # Arrange
        node, other = yield self.create_nodes(2)
        tunnel_node = Circuit(long(0), 0)
        tunnel_other = Circuit(long(0), 0)
        tunnel_node.bytes_up = tunnel_other.bytes_down = 1024
        tunnel_node.bytes_down = tunnel_other.bytes_up = 2 * 1024

        # Act
        node.call(node.community.on_tunnel_remove, None, None, tunnel_node, self._create_target(node, other))
        other.call(other.community.on_tunnel_remove, None, None, tunnel_other, self._create_target(other, node))
        yield deferLater(reactor, 5.1, lambda: None)

        # Assert
        with self.assertRaises(StopIteration):
            self.assertFalse(node.receive_message(names=[HALF_BLOCK]).next())

        with self.assertRaises(StopIteration):
            self.assertFalse(other.receive_message(names=[HALF_BLOCK]).next())

        self.assertBlocksInDatabase(node, 0)
        self.assertBlocksInDatabase(other, 0)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_on_tunnel_remove_append_pending(self):
        """
        Test the on_tunnel_remove handler function for a circuit
        """
        # Arrange
        node, other = yield self.create_nodes(2)
        tunnel_node = Circuit(long(0), 0)
        tunnel_node.bytes_up = 12 * 1024 * 1024
        tunnel_node.bytes_down = 14 * 1024 * 1024

        # Act
        node.call(node.community.on_tunnel_remove, None, None, tunnel_node, self._create_target(node, other))
        node.call(node.community.on_tunnel_remove, None, None, tunnel_node, self._create_target(node, other))
        yield deferLater(reactor, 5.1, lambda: None)

        self.assertEqual(node.community.pending_bytes[other.community.my_member.public_key].up, 2*tunnel_node.bytes_up)
        self.assertEqual(node.community.pending_bytes[other.community.my_member.public_key].down,
                         2*tunnel_node.bytes_down)

    def test_receive_request_invalid(self):
        """
        Test the community to receive a request message.
        """
        # Arrange
        node, other = self.create_nodes(2)
        target_other = self._create_target(node, other)
        TestTriblerChainCommunity.set_expectation(other, node, 10, 5)
        transaction = {"up": 10, "down": 5}
        node.call(node.community.sign_block, target_other, other.my_member.public_key, transaction)
        _, block_req = other.receive_message(names=[HALF_BLOCK]).next()
        # Act
        # construct faked block
        block = block_req.payload.block
        block.transaction["up"] += 10
        block.transaction["total_up"] = block.transaction["up"]
        block_req = node.community.get_meta_message(HALF_BLOCK).impl(
            authentication=tuple(),
            distribution=(node.community.claim_global_time(),),
            destination=(target_other,),
            payload=(block,))
        other.give_message(block_req, node)

        # Assert
        self.assertBlocksInDatabase(other, 0)
        self.assertBlocksInDatabase(node, 1)

        with self.assertRaises(StopIteration):
            # No signature responses, or crawl requests should have been sent
            node.receive_message(names=[HALF_BLOCK, CRAWL]).next()

    def test_receive_request_twice(self):
        """
        Test the community to receive a request message twice.
        """
        # Arrange
        node, other = self.create_nodes(2)
        target_other = self._create_target(node, other)
        transaction = {"up": 10, "down": 5}
        TestTriblerChainCommunity.set_expectation(node, other, 50, 50)
        TestTriblerChainCommunity.set_expectation(other, node, 50, 50)
        TestTriblerChainCommunity.create_block(node, other, target_other, transaction)

        # construct faked block
        block = node.call(node.community.persistence.get_latest, node.my_member.public_key)
        block_req = node.community.get_meta_message(HALF_BLOCK).impl(
            authentication=tuple(),
            distribution=(node.community.claim_global_time(),),
            destination=(target_other,),
            payload=(block,))
        other.give_message(block_req, node)

        # Assert
        self.assertBlocksInDatabase(other, 2)
        self.assertBlocksInDatabase(node, 2)

        with self.assertRaises(StopIteration):
            # No signature responses, or crawl requests should have been sent
            node.receive_message(names=[HALF_BLOCK, CRAWL]).next()

    def test_receive_request_too_much(self):
        """
        Test the community to receive a request that claims more than we are prepared to sign
        """
        # Arrange
        node, other = self.create_nodes(2)
        target_other = self._create_target(node, other)
        TestTriblerChainCommunity.set_expectation(other, node, 3, 3)
        transaction = {"up": 10, "down": 5}
        node.call(node.community.sign_block, target_other, other.my_member.public_key, transaction)
        # Act
        other.give_message(other.receive_message(names=[HALF_BLOCK]).next()[1], node)

        # Assert
        self.assertBlocksInDatabase(other, 1)
        self.assertBlocksInDatabase(node, 1)

        with self.assertRaises(StopIteration):
            # No signature responses, or crawl requests should have been sent
            node.receive_message(names=[HALF_BLOCK, CRAWL]).next()

    def test_receive_request_unknown_pend(self):
        """
        Test the community to receive a request that claims about a peer we know nothing about
        """
        # Arrange
        node, other = self.create_nodes(2)
        target_other = self._create_target(node, other)
        transaction = {"up": 10, "down": 5}
        node.call(node.community.sign_block, target_other, other.my_member.public_key, transaction)
        # Act
        other.give_message(other.receive_message(names=[HALF_BLOCK]).next()[1], node)

        # Assert
        self.assertBlocksInDatabase(other, 1)
        self.assertBlocksInDatabase(node, 1)

        with self.assertRaises(StopIteration):
            # No signature responses, or crawl requests should have been sent
            node.receive_message(names=[HALF_BLOCK, CRAWL]).next()

    def test_block_values(self):
        """
        If a block is created between two nodes both
        should have the correct total_up and total_down of the signature request.
        """
        # Arrange
        node, other = self.create_nodes(2)
        TestTriblerChainCommunity.set_expectation(node, other, 50, 50)
        TestTriblerChainCommunity.set_expectation(other, node, 50, 50)
        transaction = {"up": 10, "down": 5}

        # Act
        TestTriblerChainCommunity.create_block(node, other, self._create_target(node, other), transaction)

        # Assert
        block = node.call(TriblerChainBlock.create, transaction, node.community.persistence,
                          node.community.my_member.public_key)
        self.assertEqual(20, block.transaction["total_up"])
        self.assertEqual(10, block.transaction["total_down"])
        block = other.call(TriblerChainBlock.create, transaction, other.community.persistence,
                           other.community.my_member.public_key)
        self.assertEqual(15, block.transaction["total_up"])
        self.assertEqual(15, block.transaction["total_down"])

    def test_block_values_after_request(self):
        """
        After a request is sent, a node should update its totals.
        """
        # Arrange
        node, other = self.create_nodes(2)
        transaction = {"up": 10, "down": 5}
        node.call(node.community.sign_block, self._create_target(node, other), other.my_member.public_key, transaction)

        # Assert
        block = node.call(TriblerChainBlock.create, transaction, node.community.persistence,
                          node.community.my_member.public_key)
        self.assertEqual(20, block.transaction["total_up"])
        self.assertEqual(10, block.transaction["total_down"])

    def test_crawler_on_introduction_received(self):
        """
        Test the crawler takes a step when an introduction is made by the walker
        """
        # Arrange
        TriblerChainCommunityCrawler.CrawlerDelay = 10000000
        crawler = DispersyTestFunc.create_nodes(self, 1, community_class=TriblerChainCommunityCrawler,
                                                memory_database=False)[0]
        node, = self.create_nodes(1)
        node._community.cancel_pending_task("take fast steps")
        node._community.cancel_pending_task("take step")
        node._community.cancel_pending_task("start_walking")
        target_node_from_crawler = self._create_target(node, crawler)

        # when we call on_introduction request it is going to forward the argument to it's super implementation.
        # Dispersy will error if it does not expect this, and the target code will not be tested. So we pick at
        # dispersy's brains to make it accept the intro response.
        intro_request_info = crawler.call(IntroductionRequestCache, crawler.community, None)
        intro_response = node.create_introduction_response(target_node_from_crawler, node.lan_address, node.wan_address,
                                                           node.lan_address, node.wan_address,
                                                           u"unknown", False, intro_request_info.number)
        intro_response._candidate = target_node_from_crawler
        crawler.community.request_cache._identifiers[
            crawler.community.request_cache._create_identifier(intro_request_info.number, u"introduction-request")
        ] = intro_request_info

        # and we don't actually want to send the crawl request since the counter party is fake, just count if it is run
        counter = [0]

        def on_crawl_request(cand, pk, sequence_number=None):
            # Ignore live edge request
            if sequence_number != -1:
                counter[0] += 1
        crawler.community.send_crawl_request = on_crawl_request

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
        transaction = {"up": 10, "down": 5}
        TestTriblerChainCommunity.create_block(node, other, self._create_target(node, other), transaction)

        # Get statistics
        statistics = node.community.get_statistics()
        assert isinstance(statistics, dict), type(statistics)
        assert len(statistics) > 0

    def test_get_statistics_for_not_self(self):
        """
        Test the get_statistics method where a last block exists
        """
        # Arrange
        node, other = self.create_nodes(2)
        transaction = {"up": 10, "down": 5}
        TestTriblerChainCommunity.create_block(node, other, self._create_target(node, other), transaction)

        # Get statistics
        statistics = node.community.get_statistics(public_key=other.community.my_member.public_key)
        assert isinstance(statistics, dict), type(statistics)
        assert len(statistics) > 0

    def test_get_trust(self):
        """
        Test that the trust nodes have for each other is the upload + the download total of all blocks.
        """
        # Arrange
        node, other = self.create_nodes(2)
        transaction = {'up': 10, 'down': 5, 'total_up': 10, 'total_down': 5}
        TestTriblerChainCommunity.create_block(node, other, self._create_target(node, other), transaction)
        TestTriblerChainCommunity.create_block(other, node, self._create_target(other, node), transaction)

        # Get statistics
        node_trust = blockingCallFromThread(reactor, node.community.get_trust, other.community.my_member)
        other_trust = blockingCallFromThread(reactor, other.community.get_trust, node.community.my_member)
        self.assertEqual(node_trust, 15)
        self.assertEqual(other_trust, 15)

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

    def test_get_bandwidth_tokens_for_self(self):
        """
        Test that the bandwidth tokens the own node has is the upload - the download total of all blocks.
        """
        # Arrange
        node, other = self.create_nodes(2)
        transaction = {'up': 10, 'down': 5}
        transaction2 = {'up': 5, 'down': 10}
        TestTriblerChainCommunity.create_block(node, other, self._create_target(node, other), transaction)
        TestTriblerChainCommunity.create_block(other, node, self._create_target(other, node), transaction2)

        # Get statistics
        node_trust = blockingCallFromThread(reactor, node.community.get_bandwidth_tokens, node.community.my_member)
        other_trust = blockingCallFromThread(reactor, other.community.get_bandwidth_tokens, other.community.my_member)
        self.assertEqual(node_trust, 5)
        self.assertEqual(other_trust, -5)

    def test_get_bandwidth_tokens(self):
        """
        Test that the bandwidth tokens nodes have is the upload - the download total of all blocks.
        """
        # Arrange
        node, other = self.create_nodes(2)
        transaction = {'up': 10, 'down': 5}
        transaction2 = {'up': 5, 'down': 10}
        TestTriblerChainCommunity.create_block(node, other, self._create_target(node, other), transaction)
        TestTriblerChainCommunity.create_block(other, node, self._create_target(other, node), transaction2)

        # Get statistics
        node_trust = blockingCallFromThread(reactor, node.community.get_bandwidth_tokens, other.community.my_member)
        other_trust = blockingCallFromThread(reactor, other.community.get_bandwidth_tokens, node.community.my_member)
        self.assertEqual(node_trust, -5)
        self.assertEqual(other_trust, 5)

    def test_get_default_bandwidth_tokens(self):
        """
        Test that the bandwidth token amount for nodes without blocks is 0.
        """
        # Arrange
        node, other = self.create_nodes(2)

        # Get statistics
        node_trust = blockingCallFromThread(reactor, node.community.get_bandwidth_tokens, other.community.my_member)
        other_trust = blockingCallFromThread(reactor, other.community.get_bandwidth_tokens, node.community.my_member)
        self.assertEqual(node_trust, 0)
        self.assertEqual(other_trust, 0)

    def test_bootstrapping(self):
        """
        Test that bootstrapping process works.
        """
        # Arrange
        node, = self.create_nodes(1)

        node_bootstrap = blockingCallFromThread(reactor, node.community.bootstrap_new_identity, 100)
        self.assertNotEqual(node_bootstrap['private_key'],
                            node.community.my_member.private_key.key_to_bin().encode('base64'))
        self.assertEqual(node_bootstrap['transaction']['up'], 100)
        self.assertEqual(node_bootstrap['transaction']['down'], 0)
        self.assertEqual(node_bootstrap['block']['sequence_number'], 1)
        self.assertNotEqual(node_bootstrap['block']['block_hash'], "")
