"""
The TrustChain Community is the first step in an incremental approach in building a new reputation system.
This reputation system builds a tamper proof interaction history contained in a chain data-structure.
Every node has a chain and these chains intertwine by blocks shared by chains.
"""
import logging
from random import randint
from time import time

from twisted.internet import reactor
from twisted.internet.defer import succeed, Deferred, inlineCallbacks

from Tribler.community.trustchain.block import TrustChainBlock, ValidationResult, GENESIS_SEQ, UNKNOWN_SEQ
from Tribler.community.trustchain.conversion import TrustChainConversion
from Tribler.community.trustchain.database import TrustChainDB
from Tribler.community.trustchain.payload import HalfBlockPayload, CrawlRequestPayload, BlockPairPayload
from Tribler.dispersy.authentication import NoAuthentication, MemberAuthentication
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination, NHopCommunityDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message, DelayPacketByMissingMember
from Tribler.dispersy.resolution import PublicResolution

HALF_BLOCK = u"half_block"
HALF_BLOCK_BROADCAST = u"half_block_community"
BLOCK_PAIR = u"block_pair"
BLOCK_PAIR_BROADCAST = u"block_pair_broadcast"
CRAWL = u"crawl"


class TrustChainCommunity(Community):
    """
    Community for reputation based on TrustChain tamper proof interaction history.
    """
    BLOCK_CLASS = TrustChainBlock
    DB_CLASS = TrustChainDB
    DB_NAME = 'trustchain'

    def __init__(self, *args, **kwargs):
        super(TrustChainCommunity, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.persistence = self.DB_CLASS(self.dispersy.working_directory, self.DB_NAME)

        self._live_edge = []
        self._live_edge_id = 0
        self._live_edge_cb = None
        self._live_edge_next = None
        self._live_edges_enabled = True

        self.logger.debug("The trustchain community started with Public Key: %s",
                          self.my_member.public_key.encode("hex"))

        self.expected_intro_responses = {}
        self.expected_sig_requests = {}
        self.expected_sig_responses = {}
        self.received_block_ids = set()

        self.relayed_broadcasts = []

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Tue Jun 13 14:42:46 2017
        # curve: None
        # len: 571 bits ~ 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000403428b0fa33d3ed62dd39852481f535e21617144a95e682
        # ad5733b9a739b27051dc6ad1da743a463821fc8d3d1849191d5fb84fab1f3fe3ad44fb2b83f07d0c78a13b7ad1d311063069f49070ca
        # d7dc15620996cdd625c1abcdbfabf750727f1dec706f6f16cb28ce6946fdf39887a84fc457a5f9edc660adbe0a72ea5219f9578dd643
        # 2de825c167e80987ca4c6a2bf
        # pub-sha1 3199e175392a876e8cc7fbcabe5c948eeaeafa23
        # -----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQDQosPoz0+1i3TmFJIH1NeIWFxRKle
        # aCrVczuac5snBR3GrR2nQ6Rjgh/I09GEkZHV+4T6sfP+OtRPsrg/B9DHihO3rR0x
        # EGMGn0kHDK19wVYgmWzdYlwavNv6v3UHJ/Hexwb28WyyjOaUb985iHqE/EV6X57c
        # Zgrb4KcupSGflXjdZDLeglwWfoCYfKTGor8=
        # -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000403428b0fa33d3ed62dd39852481f535e21617144a95" \
                     "e682ad5733b9a739b27051dc6ad1da743a463821fc8d3d1849191d5fb84fab1f3fe3ad44fb2b83f07d0c78a13b7ad1d" \
                     "311063069f49070cad7dc15620996cdd625c1abcdbfabf750727f1dec706f6f16cb28ce6946fdf39887a84fc457a5f9" \
                     "edc660adbe0a72ea5219f9578dd6432de825c167e80987ca4c6a2bf"
        return [dispersy.get_member(public_key=master_key.decode("HEX"))]

    def initialize(self, tribler_session=None):
        super(TrustChainCommunity, self).initialize()
        if tribler_session:
            self._live_edges_enabled = tribler_session.config.get_trustchain_live_edges_enabled()

    def initiate_meta_messages(self):
        """
        Setup all message that can be received by this community and the super classes.
        :return: list of meta messages.
        """
        return super(TrustChainCommunity, self).initiate_meta_messages() + [
            Message(self, HALF_BLOCK,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    HalfBlockPayload(),
                    self._generic_timeline_check,
                    self.received_half_block),
            Message(self, HALF_BLOCK_BROADCAST,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    NHopCommunityDestination(10, depth=2),
                    HalfBlockPayload(),
                    self._generic_timeline_check,
                    self.received_half_block),
            Message(self, BLOCK_PAIR,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    BlockPairPayload(),
                    self._generic_timeline_check,
                    self.received_block_pair),
            Message(self, BLOCK_PAIR_BROADCAST,
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    NHopCommunityDestination(10, depth=2),
                    BlockPairPayload(),
                    self._generic_timeline_check,
                    self.received_block_pair),
            Message(self, CRAWL,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlRequestPayload(),
                    self._generic_timeline_check,
                    self.received_crawl_request)]

    def initiate_conversions(self):
        return [DefaultConversion(self), TrustChainConversion(self)]

    def should_sign(self, message):
        """
        Return whether we should sign the block in the passed message.
        @param message: the message containing a block we want to sign or not.
        """
        return True

    def send_block(self, block, candidate=None):
        """
        Send a block to a candidate or a community.
        :param block: The block to send.
        :param candidate: The candidate to send the block to. If not specified, it will be broadcasted to your
        known peers.
        """
        if candidate is None:
            self.logger.debug("Broadcasting block to neighbour nodes (%s)", block)
        elif candidate.get_member():
            self.logger.debug("Sending block to %s (%s)", candidate.get_member().public_key.encode("hex")[-8:], block)
        else:
            self.logger.debug("Sending block to %s (%s)", candidate, block)
        message = self.get_meta_message(HALF_BLOCK if candidate else HALF_BLOCK_BROADCAST).impl(
            authentication=tuple(),
            distribution=(self.claim_global_time(),),
            destination=(candidate,) if candidate else (),
            payload=(block,))
        try:
            self.dispersy.store_update_forward([message], False, False, True)
        except DelayPacketByMissingMember:
            self.logger.warn("Missing member in TrustChain community to send signature request to")

    def send_block_pair(self, block1, block2, candidate=None):
        """
        Send a pair of blocks to a candidate or a community.
        :param block1: The first block to send.
        :param candidate: The candidate to send the block to. If not specified, it will be broadcasted to your
        known peers.
        """
        if candidate is None:
            self.logger.debug("Broadcasting block pair to neighbour nodes (%s, %s)", block1, block2)
        elif candidate.get_member():
            self.logger.debug("Sending block pair to %s (%s, %s)", candidate.get_member().public_key.encode("hex")[-8:],
                              block1, block2)
        else:
            self.logger.debug("Sending block pair to %s (%s, %s)", candidate, block1, block2)
        message = self.get_meta_message(BLOCK_PAIR if candidate else BLOCK_PAIR_BROADCAST).impl(
            authentication=tuple(),
            distribution=(self.claim_global_time(),),
            destination=(candidate,) if candidate else (),
            payload=(block1, block2))
        try:
            self.dispersy.store_update_forward([message], False, False, True)
        except DelayPacketByMissingMember:
            self.logger.warn("Missing member in TrustChain community to send signature request to")

    def wait_for_intro_of_candidate(self, candidate):
        """
        Returns a Deferred that fires when we receive an introduction response from a given candidate.
        """
        response_deferred = Deferred()
        self.expected_intro_responses[candidate.sock_addr] = response_deferred
        return response_deferred

    def wait_for_signature_request(self, block_id):
        """
        Returns a Deferred that fires when we receive a signature request with a specific block hash.
        """
        if block_id in self.received_block_ids:
            return succeed(None)

        response_deferred = Deferred()
        self.expected_sig_requests[block_id] = response_deferred
        return response_deferred

    def wait_for_signature_response(self, block_id):
        """
        Returns a Deferred that fires when we receive a signature response with a specific block hash.
        """
        if block_id in self.received_block_ids:
            return succeed(None)

        response_deferred = Deferred()
        self.expected_sig_responses[block_id] = response_deferred
        return response_deferred

    def sign_block(self, candidate, public_key=None, transaction=None, linked=None):
        """
        Create, sign, persist and send a block signed message
        :param candidate: The peer with whom you have interacted, as a dispersy candidate
        :param transaction: A string describing the interaction in this block
        :param linked: The block that the requester is asking us to sign
        :return block: The block that has been created and signed
        """
        # NOTE to the future: This method reads from the database, increments and then writes back. If in some future
        # this method is allowed to execute in parallel, be sure to lock from before .create up to after .add_block
        assert transaction is None and linked is not None or transaction is not None and linked is None, \
            "Either provide a linked block or a transaction, not both"
        assert linked is None or linked.link_public_key == self.my_member.public_key, \
            "Cannot counter sign block not addressed to self"
        assert linked is None or linked.link_sequence_number == UNKNOWN_SEQ, \
            "Cannot counter sign block that is not a request"
        assert transaction is None or isinstance(transaction, list), "Transaction should be a list not %r" % transaction

        block = self.BLOCK_CLASS.create(transaction, self.persistence, self.my_member.public_key,
                                        link=linked, link_pk=public_key)
        block.sign(self.my_member.private_key)
        validation = block.validate(self.persistence)
        self.logger.info("Signed block to %s (%s) validation result %s",
                         block.link_public_key.encode("hex")[-8:], block, validation)
        if validation[0] != ValidationResult.partial_next and validation[0] != ValidationResult.valid:
            self.logger.error("Signed block did not validate?! Result %s", repr(validation))
            return None
        else:
            self.persistence.add_block(block)
            self.send_block(block, candidate)
            return block

    def validate_persist_block(self, block):
        """
        Validate a block and if it's valid, persist it. Return the validation result.
        :param block: The block to validate and persist.
        :return: [ValidationResult]
        """
        validation = block.validate(self.persistence)
        self.logger.debug("Block validation result %s, %s, (%s)", validation[0], validation[1], block)
        if validation[0] == ValidationResult.invalid:
            pass
        elif not self.persistence.contains(block):
            self.persistence.add_block(block)
        else:
            self.logger.debug("Received already known block (%s)", block)

        return validation

    def received_half_block(self, messages):
        """
        We've received a half block, either because we sent a SIGNED message to some one or we are crawling
        :param messages The half block messages
        """
        self.logger.debug("Received %d half block messages.", len(messages))
        for message in messages:
            blk = message.payload.block
            block_id = "%s.%s" % (blk.public_key.encode('hex'), blk.sequence_number)

            if message.name == HALF_BLOCK_BROADCAST and message.destination.depth > 0 \
                    and block_id not in self.relayed_broadcasts:
                message.regenerate_packet()
                self.dispersy.store_update_forward([message], False, False, True)
                self.relayed_broadcasts.append(block_id)

            validation = self.validate_persist_block(blk)

            # Check if we are waiting for this block
            if block_id in self.expected_sig_requests:
                self.expected_sig_requests[block_id].callback(block_id)
                del self.expected_sig_requests[block_id]

            link_block_id = "%s.%s" % (blk.link_public_key.encode('hex'), blk.link_sequence_number)
            if link_block_id in self.expected_sig_responses:
                self.expected_sig_responses[link_block_id].callback(block_id)
                del self.expected_sig_responses[link_block_id]

            self.received_block_ids.add(block_id)

            # Is this a request, addressed to us, and have we not signed it already?
            if blk.link_sequence_number != UNKNOWN_SEQ or \
                    blk.link_public_key != self.my_member.public_key or \
                    self.persistence.get_linked(blk) is not None:
                continue

            self.logger.info("Received request block addressed to us (%s)", blk)

            # determine if we want to sign this block
            if not self.should_sign(message):
                continue

            crawl_task = "crawl_%s" % blk.hash
            # It is important that the request matches up with its previous block, gaps cannot be tolerated at
            # this point. We already dropped invalids, so here we delay this message if the result is partial,
            # partial_previous or no-info. We send a crawl request to the requester to (hopefully) close the gap
            if validation[0] == ValidationResult.partial_previous or validation[0] == ValidationResult.partial or \
                    validation[0] == ValidationResult.no_info:
                self.logger.info("Request block could not be validated sufficiently, crawling requester. %s",
                                 validation)
                # Note that this code does not cover the scenario where we obtain this block indirectly.

                # Are we already waiting for this crawl to happen?
                # For example: it's taking longer than 5 secs or the block message reached us twice via different paths
                if self.is_pending_task_active(crawl_task):
                    continue

                self.send_crawl_request(message.candidate, blk.public_key, max(GENESIS_SEQ, blk.sequence_number - 5))

                # Make sure we get called again after a while. Note that the cleanup task on pend will prevent
                # us from waiting on the peer forever.
                self.register_task(crawl_task, reactor.callLater(5.0, self.received_half_block, [message]))
            else:
                self.sign_block(message.candidate, linked=blk)
                if self.is_pending_task_active(crawl_task):
                    self.cancel_pending_task(crawl_task)
                    continue

    def received_block_pair(self, messages):
        """
        We received block pairs. Verify them and persist them to the local storage.
        :param messages: The block pair messages
        """
        for message in messages:
            self.validate_persist_block(message.payload.block1)
            self.validate_persist_block(message.payload.block2)

            blk = message.payload.block1
            block_id = "%s.%s" % (blk.public_key.encode('hex'), blk.sequence_number)

            if message.name == BLOCK_PAIR_BROADCAST and message.destination.depth > 0 \
                    and block_id not in self.relayed_broadcasts:
                message.regenerate_packet()
                self.dispersy.store_update_forward([message], False, False, True)
                self.relayed_broadcasts.append(block_id)

    def send_crawl_request(self, candidate, public_key, sequence_number=None):
        sq = sequence_number
        if sequence_number is None:
            blk = self.persistence.get_latest(public_key)
            sq = blk.sequence_number if blk else GENESIS_SEQ
        sq = max(GENESIS_SEQ, sq) if sq >= 0 else sq
        self.logger.info("Requesting crawl of node %s:%d", public_key.encode("hex")[-8:], sq)
        message = self.get_meta_message(CRAWL).impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(sq,))
        self.dispersy.store_update_forward([message], False, False, True)

    def received_crawl_request(self, messages):
        self.logger.debug("Received %d crawl messages.", len(messages))
        for message in messages:
            self.logger.info("Received crawl request from node %s for sequence number %d",
                             message.candidate.get_member().public_key.encode("hex")[-8:],
                             message.payload.requested_sequence_number)
            sq = message.payload.requested_sequence_number
            if sq < 0:
                last_block = self.persistence.get_latest(self.my_member.public_key)
                # The -1 element is the last_block.seq_nr
                # The -2 element is the last_block.seq_nr - 1
                # Etc. until the genesis seq_nr
                sq = max(GENESIS_SEQ, last_block.sequence_number + (sq + 1)) if last_block else GENESIS_SEQ
            blocks = self.persistence.crawl(self.my_member.public_key, sq)
            count = len(blocks)
            for blk in blocks:
                self.send_block(blk, message.candidate)
            self.logger.info("Sent %d blocks", count)

    @inlineCallbacks
    def unload_community(self):
        self.logger.debug("Unloading the TrustChain Community.")
        yield super(TrustChainCommunity, self).unload_community()
        # Close the persistence layer
        self.persistence.close()

    def set_live_edge_callback(self, func):
        """
        Set the callback function for live edge updates.
        Passed arguments are:
          live_edge_id, [candidates]
        """
        self._live_edge_cb = func

    def reset_live_edges(self):
        """
        Reset the live edges counter and current live edge.
        """
        self._live_edge = []
        self._live_edge_next = None
        self._live_edge_id = 0

    def set_live_edges_enabled(self, value):
        """
        Enable or disable live edges.

        :param value: whether or not to enable live edges
        :type value: boolean
        """
        if value and not self._live_edges_enabled:
            # Make sure we don't inherit old edge data after a reset
            self.reset_live_edges()
        self._live_edges_enabled = value

    def get_trust(self, member):
        """
        Get the trust for another member.
        Currently this is just the length of their chain.

        :param member: the member we interacted with
        :type member: dispersy.member.Member
        :return: the trust value for this member
        :rtype: int
        """
        block = self.persistence.get_latest(member.public_key)
        if block:
            return block.sequence_number
        else:
            # We need a minimum of 1 trust to have a chance to be selected in the categorical distribution.
            return 1

    def dispersy_get_introduce_candidate(self, exclude_candidate=None):
        """
        Choose a trusted candidate to introduce to someone else.
        The more trust you have for someone, the higher the chance is to forward them.
        """
        if not self._live_edges_enabled:
            return super(TrustChainCommunity, self).dispersy_get_introduce_candidate(exclude_candidate)

        eligible = [candidate for candidate in self._candidates.itervalues()
                    if candidate.get_member() and candidate != exclude_candidate]

        if not eligible:
            # If we have no trusted candidates, bootstrap this process.
            return super(TrustChainCommunity, self).dispersy_get_introduce_candidate(exclude_candidate)

        total_trust = sum([self.get_trust(candidate.get_member()) for candidate in eligible])

        random_trust_i = randint(0, total_trust - 1)
        current_trust_i = 0
        for i in xrange(0, len(eligible)):
            next_trust_i = self.get_trust(eligible[i].get_member())
            if current_trust_i + next_trust_i > random_trust_i:
                return eligible[i]
            else:
                current_trust_i += next_trust_i

        return eligible[-1]

    def on_introduction_response(self, messages):
        super(TrustChainCommunity, self).on_introduction_response(messages)

        for message in messages:
            if message.candidate.sock_addr in self.expected_intro_responses:
                self.expected_intro_responses[message.candidate.sock_addr].callback(message.candidate)
                del self.expected_intro_responses[message.candidate.sock_addr]

        if self._live_edges_enabled:
            for message in messages:
                payload = message.payload
                candidate = self.get_candidate(message.candidate.sock_addr, replace=False)

                if not candidate.get_member():
                    candidate.associate(message.authentication.member)

                candidate.set_keepalive(self)
                self._live_edge.append(candidate)
                # Callback our live edge handler
                if self._live_edge_cb:
                    self._live_edge_cb(self._live_edge_id, self._live_edge)

                self.send_crawl_request(candidate, candidate.get_member().public_key, -1)

                lan_introduction_address = payload.lan_introduction_address
                wan_introduction_address = payload.wan_introduction_address
                if not (lan_introduction_address == ("0.0.0.0", 0) or wan_introduction_address == ("0.0.0.0", 0)):
                    sock_introduction_addr = lan_introduction_address if wan_introduction_address[0] == \
                                                                         self._dispersy.wan_address[
                                                                             0] else wan_introduction_address
                    self._live_edge_next = self.get_candidate(sock_introduction_addr, False, lan_introduction_address)
                else:
                    self._live_edge_next = None

    def take_step(self):
        if not self._live_edges_enabled:
            return super(TrustChainCommunity, self).take_step()

        now = time()
        self._logger.debug("previous sync was %.1f seconds ago",
                           now - self._last_sync_time if self._last_sync_time else -1)

        if not self._live_edge or len(self._live_edge) == 5 or self._live_edge_next is None:
            self._live_edge_id += 1

            # New live edges always start with our member
            my_candidate = Candidate(("127.0.0.1", self.dispersy.endpoint.get_address()[1]), False)
            my_candidate.associate(self.my_member)
            self._live_edge = [my_candidate]

            # Callback our live edge handler
            if self._live_edge_cb:
                self._live_edge_cb(self._live_edge_id, self._live_edge)

        if self._live_edge_next:
            candidate = self._live_edge_next
            self._live_edge_next = None
        else:
            candidate = self.dispersy_get_walk_candidate()

        if candidate:
            self._logger.debug("%s %s taking step towards %s",
                               self.cid.encode("HEX"), self.get_classification(), candidate)
            self.create_introduction_request(candidate, self.dispersy_enable_bloom_filter_sync)
        else:
            self._logger.debug("%s %s no candidate to take step", self.cid.encode("HEX"), self.get_classification())
        self._last_sync_time = time()
