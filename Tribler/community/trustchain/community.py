"""
The TrustChain Community is the first step in an incremental approach in building a new reputation system.
This reputation system builds a tamper proof interaction history contained in a chain data-structure.
Every node has a chain and these chains intertwine by blocks shared by chains.
"""
import logging
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from Tribler.community.trustchain.database import TrustChainDB
from Tribler.dispersy.authentication import NoAuthentication, MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message, DelayPacketByMissingMember
from Tribler.dispersy.resolution import PublicResolution

from Tribler.community.trustchain.block import TrustChainBlock, ValidationResult, GENESIS_SEQ, UNKNOWN_SEQ
from Tribler.community.trustchain.payload import HalfBlockPayload, CrawlRequestPayload
from Tribler.community.trustchain.conversion import TrustChainConversion

HALF_BLOCK = u"half_block"
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
        self.logger.debug("The trustchain community started with Public Key: %s",
                          self.my_member.public_key.encode("hex"))

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

    def should_sign(self, block):
        """
        Return whether we should sign the passed block.
        @param block: the block that we should sign or not.
        """
        return True

    def send_block(self, candidate, block):
        if candidate.get_member():
            self.logger.debug("Sending block to %s (%s)", candidate.get_member().public_key.encode("hex")[-8:], block)
        else:
            self.logger.debug("Sending block to %s (%s)", candidate, block)
        message = self.get_meta_message(HALF_BLOCK).impl(
            authentication=tuple(),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(block,))
        try:
            self.dispersy.store_update_forward([message], False, False, True)
        except DelayPacketByMissingMember:
            self.logger.warn("Missing member in TrustChain community to send signature request to")

    def sign_block(self, candidate, public_key=None, transaction=None, linked=None):
        """
        Create, sign, persist and send a block signed message
        :param candidate: The peer with whom you have interacted, as a dispersy candidate
        :param transaction: A string describing the interaction in this block
        :param linked: The block that the requester is asking us to sign
        """
        # NOTE to the future: This method reads from the database, increments and then writes back. If in some future
        # this method is allowed to execute in parallel, be sure to lock from before .create up to after .add_block
        assert transaction is None and linked is not None or transaction is not None and linked is None, \
            "Either provide a linked block or a transaction, not both"
        assert linked is None or linked.link_public_key == self.my_member.public_key, \
            "Cannot counter sign block not addressed to self"
        assert linked is None or linked.link_sequence_number == UNKNOWN_SEQ, \
            "Cannot counter sign block that is not a request"
        assert transaction is None or isinstance(transaction, dict), "Transaction should be a dictionary"

        block = self.BLOCK_CLASS.create(transaction, self.persistence, self.my_member.public_key,
                                        link=linked, link_pk=public_key)
        block.sign(self.my_member.private_key)
        validation = block.validate(self.persistence)
        self.logger.info("Signed block to %s (%s) validation result %s",
                         block.link_public_key.encode("hex")[-8:], block, validation)
        if validation[0] != ValidationResult.partial_next and validation[0] != ValidationResult.valid:
            self.logger.error("Signed block did not validate?! Result %s", repr(validation))
        else:
            self.persistence.add_block(block)
            self.send_block(candidate, block)

    def received_half_block(self, messages):
        """
        We've received a half block, either because we sent a SIGNED message to some one or we are crawling
        :param messages The half block messages
        """
        self.logger.debug("Received %d half block messages.", len(messages))
        for message in messages:
            blk = message.payload.block
            validation = blk.validate(self.persistence)
            self.logger.debug("Block validation result %s, %s, (%s)", validation[0], validation[1], blk)
            if validation[0] == ValidationResult.invalid:
                continue
            elif not self.persistence.contains(blk):
                self.persistence.add_block(blk)
            else:
                self.logger.debug("Received already known block (%s)", blk)

            # Is this a request, addressed to us, and have we not signed it already?
            if blk.link_sequence_number != UNKNOWN_SEQ or \
                    blk.link_public_key != self.my_member.public_key or \
                    self.persistence.get_linked(blk) is not None:
                continue

            self.logger.info("Received request block addressed to us (%s)", blk)

            # determine if we want to sign this block
            if not self.should_sign(blk):
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

    def send_crawl_request(self, candidate, public_key, sequence_number=None):
        sq = sequence_number
        if sequence_number is None:
            blk = self.persistence.get_latest(public_key)
            sq = blk.sequence_number if blk else GENESIS_SEQ
        sq = max(GENESIS_SEQ, sq)
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
            blocks = self.persistence.crawl(self.my_member.public_key, message.payload.requested_sequence_number)
            count = len(blocks)
            for blk in blocks:
                self.send_block(message.candidate, blk)
            self.logger.info("Sent %d blocks", count)

    @inlineCallbacks
    def unload_community(self):
        self.logger.debug("Unloading the TrustChain Community.")
        yield super(TrustChainCommunity, self).unload_community()
        # Close the persistence layer
        self.persistence.close()
