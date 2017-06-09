"""
The TrustChain Community is the first step in an incremental approach in building a new reputation system.
This reputation system builds a tamper proof interaction history contained in a chain data-structure.
Every node has a chain and these chains intertwine by blocks shared by chains.
"""
import logging
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall

from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_REMOVE
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.authentication import NoAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message, DelayPacketByMissingMember
from Tribler.dispersy.resolution import PublicResolution

from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.community.trustchain.block import TrustChainBlock, ValidationResult, GENESIS_SEQ, UNKNOWN_SEQ
from Tribler.community.trustchain.payload import HalfBlockPayload, CrawlRequestPayload
from Tribler.community.trustchain.database import TrustChainDB
from Tribler.community.trustchain.conversion import TrustChainConversion

HALF_BLOCK = u"half_block"
CRAWL = u"crawl"
MIN_TRANSACTION_SIZE = 1024*1024


class PendingBytes(object):
    def __init__(self, up, down, clean=None):
        super(PendingBytes, self).__init__()
        self.up = up
        self.down = down
        self.clean = clean

    def add(self, up, down):
        if self.up + up >= 0 and self.down + down >= 0:
            self.up = max(0, self.up + up)
            self.down = max(0, self.down + down)
            if self.clean is not None:
                self.clean.reset(2 * 60)
            return True
        else:
            return False


class TrustChainCommunity(Community):
    """
    Community for reputation based on TrustChain tamper proof interaction history.
    """
    DB_CLASS = TrustChainDB
    DB_NAME = 'trustchain'

    def __init__(self, *args, **kwargs):
        super(TrustChainCommunity, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.notifier = None
        self.persistence = self.DB_CLASS(self.dispersy.working_directory, self.DB_NAME)

        # We store the bytes send and received in the tunnel community in a dictionary.
        # The key is the public key of the peer being interacted with, the value a tuple of the up and down bytes
        # This data is not used to create outgoing requests, but _only_ to verify incoming requests
        self.pending_bytes = dict()

        self.logger.debug("The trustchain community started with Public Key: %s",
                          self.my_member.public_key.encode("hex"))

    def initialize(self, tribler_session=None):
        super(TrustChainCommunity, self).initialize()
        if tribler_session:
            self.notifier = tribler_session.notifier
            self.notifier.add_observer(self.on_tunnel_remove, NTFY_TUNNEL, [NTFY_REMOVE])

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Sun Apr 23 10:06:29 2017
        # curve: None
        # len: 571 bits ~ 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b8104002703819200040503dac58c19267f12cb0cf667e480816cd2574acae5293b5
        # 9d7c3da32e02b4747f7e2e9e9c880d2e5e2ba8b7fcc9892cb39b797ef98483ffd58739ed20990f8e3df7d1ec5a7ad2c0338dc206c4383a
        # 943e3e2c682ac4b585880929a947ffd50057b575fc30ec88eada3ce6484e5e4d6fdf41984cd1e51aaacc5f9a51bcc8393aea1f786fc47c
        # bf994cb1339f706df4a
        # pub-sha1 b78a5e252bf2f7be8716c383734f325b9aaff844
        # -----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQFA9rFjBkmfxLLDPZn5ICBbNJXSsrl
        # KTtZ18PaMuArR0f34unpyIDS5eK6i3/MmJLLObeX75hIP/1Yc57SCZD44999HsWn
        # rSwDONwgbEODqUPj4saCrEtYWICSmpR//VAFe1dfww7Ijq2jzmSE5eTW/fQZhM0e
        # UaqsxfmlG8yDk66h94b8R8v5lMsTOfcG30o=
        # -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b8104002703819200040503dac58c19267f12cb0cf667e480816cd2574acae" \
                     "5293b59d7c3da32e02b4747f7e2e9e9c880d2e5e2ba8b7fcc9892cb39b797ef98483ffd58739ed20990f8e3df7d1ec5" \
                     "a7ad2c0338dc206c4383a943e3e2c682ac4b585880929a947ffd50057b575fc30ec88eada3ce6484e5e4d6fdf41984c" \
                     "d1e51aaacc5f9a51bcc8393aea1f786fc47cbf994cb1339f706df4a"
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

    def sign_block(self, candidate, public_key=None, bytes_up=None, bytes_down=None, linked=None):
        """
        Create, sign, persist and send a block signed message
        :param candidate: The peer with whom you have interacted, as a dispersy candidate
        :param bytes_up: The bytes you have uploaded to the peer in this interaction
        :param bytes_down: The bytes you have downloaded from the peer in this interaction
        :param linked: The block that the requester is asking us to sign
        """
        # NOTE to the future: This method reads from the database, increments and then writes back. If in some future
        # this method is allowed to execute in parallel, be sure to lock from before .create up to after .add_block
        assert bytes_up is None and bytes_down is None and linked is not None or \
            bytes_up is not None and bytes_down is not None and linked is None, \
            "Either provide a linked block or byte counts, not both"
        assert linked is None or linked.link_public_key == self.my_member.public_key, \
            "Cannot counter sign block not addressed to self"
        assert linked is None or linked.link_sequence_number == UNKNOWN_SEQ, \
            "Cannot counter sign block that is not a request"

        block = TrustChainBlock.create(self.persistence, self.my_member.public_key, linked)
        if linked is None:
            block.up = bytes_up
            block.down = bytes_down
            block.total_up += bytes_up
            block.total_down += bytes_down
            block.link_public_key = public_key
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

            # determine if we want to sign (i.e. the requesting public key has enough pending bytes)
            pend = self.pending_bytes.get(blk.public_key)
            if not pend or not pend.add(-blk.down, -blk.up):
                self.logger.info("Request block counter party does not have enough bytes pending.")
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

                # We modified the counters to get here, correct pending bytes since we did not really sign the block yet
                pend.add(blk.down, blk.up)

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

    @blocking_call_on_reactor_thread
    def get_statistics(self, public_key=None):
        """
        Returns a dictionary with some statistics regarding the local trustchain database
        :returns a dictionary with statistics
        """
        if public_key is None:
            public_key = self.my_member.public_key
        latest_block = self.persistence.get_latest(public_key)
        statistics = dict()
        statistics["id"] = public_key.encode("hex")
        interacts = self.persistence.get_num_unique_interactors(public_key)
        statistics["peers_that_pk_helped"] = interacts[0] if interacts[0] is not None else 0
        statistics["peers_that_helped_pk"] = interacts[1] if interacts[1] is not None else 0
        if latest_block:
            statistics["total_blocks"] = latest_block.sequence_number
            statistics["total_up"] = latest_block.total_up
            statistics["total_down"] = latest_block.total_down
            statistics["latest_block"] = dict(latest_block)
        else:
            statistics["total_blocks"] = 0
            statistics["total_up"] = 0
            statistics["total_down"] = 0
        return statistics

    @inlineCallbacks
    def unload_community(self):
        self.logger.debug("Unloading the TrustChain Community.")
        if self.notifier:
            self.notifier.remove_observer(self.on_tunnel_remove)
        for pk in self.pending_bytes:
            if self.pending_bytes[pk].clean is not None:
                self.pending_bytes[pk].clean.reset(0)
        yield super(TrustChainCommunity, self).unload_community()
        # Close the persistence layer
        self.persistence.close()

    @forceDBThread
    def on_tunnel_remove(self, subject, change_type, tunnel, candidate):
        """
        Handler for the remove event of a tunnel. This function will attempt to create a block for the amounts that
        were transferred using the tunnel.
        :param subject: Category of the notifier event
        :param change_type: Type of the notifier event
        :param tunnel: The tunnel that was removed (closed)
        :param candidate: The dispersy candidate with whom this node has interacted in the tunnel
        """
        from Tribler.community.tunnel.tunnel_community import Circuit, RelayRoute, TunnelExitSocket
        assert isinstance(tunnel, Circuit) or isinstance(tunnel, RelayRoute) or isinstance(tunnel, TunnelExitSocket), \
            "on_tunnel_remove() was called with an object that is not a Circuit, RelayRoute or TunnelExitSocket"
        assert isinstance(tunnel.bytes_up, int) and isinstance(tunnel.bytes_down, int),\
            "tunnel instance must provide byte counts in int"

        up = tunnel.bytes_up
        down = tunnel.bytes_down
        pk = candidate.get_member().public_key

        # If the transaction is not big enough we discard the bytes up and down.
        if up + down >= MIN_TRANSACTION_SIZE:
            # Tie breaker to prevent both parties from requesting
            if up > down or (up == down and self.my_member.public_key > pk):
                self.register_task("sign_%s" % tunnel.circuit_id,
                                   reactor.callLater(5, self.sign_block, candidate, pk,
                                                     tunnel.bytes_up, tunnel.bytes_down))
            else:
                pend = self.pending_bytes.get(pk)
                if not pend:
                    self.pending_bytes[pk] = PendingBytes(up,
                                                          down,
                                                          reactor.callLater(2 * 60, self.cleanup_pending, pk))
                else:
                    pend.add(up, down)

    def cleanup_pending(self, public_key):
        self.pending_bytes.pop(public_key, None)


class TrustChainCommunityCrawler(TrustChainCommunity):
    """
    Extended TrustChainCommunity that also crawls other TrustChainCommunities.
    It requests the chains of other TrustChains.
    """

    # Time the crawler waits between crawling a new candidate.
    CrawlerDelay = 5.0

    def on_introduction_response(self, messages):
        super(TrustChainCommunityCrawler, self).on_introduction_response(messages)
        for message in messages:
            self.send_crawl_request(message.candidate, message.candidate.get_member().public_key)

    def start_walking(self):
        self.register_task("take step", LoopingCall(self.take_step)).start(self.CrawlerDelay, now=False)
