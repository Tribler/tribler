"""
The MultiChain Community is the first step in an incremental approach in building a new reputation system.
This reputation system builds a tamper proof interaction history contained in a chain data-structure.
Every node has a chain and these chains intertwine by blocks shared by chains.
"""
import logging
import base64
from twisted.internet.defer import inlineCallbacks

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_REMOVE
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.community import Community
from Tribler.dispersy.message import Message, DelayPacketByMissingMember
from Tribler.dispersy.conversion import DefaultConversion

from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.community.multichain.block import MultiChainBlock, ValidationResult, GENESIS_SEQ, UNKNOWN_SEQ
from Tribler.community.multichain.payload import HalfBlockPayload, CrawlRequestPayload
from Tribler.community.multichain.database import MultiChainDB
from Tribler.community.multichain.conversion import MultiChainConversion

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


class MultiChainCommunity(Community):
    """
    Community for reputation based on MultiChain tamper proof interaction history.
    """

    def __init__(self, *args, **kwargs):
        super(MultiChainCommunity, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.notifier = None
        self.persistence = MultiChainDB(self.dispersy.working_directory)

        # We store the bytes send and received in the tunnel community in a dictionary.
        # The key is the public key of the peer being interacted with, the value a tuple of the up and down bytes
        # This data is not used to create outgoing requests, but _only_ to verify incoming requests
        self.pending_bytes = dict()

        self.logger.debug("The multichain community started with Public Key: %s",
                          self.my_member.public_key.encode("hex"))

    def initialize(self, tribler_session=None):
        super(MultiChainCommunity, self).initialize()
        if tribler_session:
            self.notifier = tribler_session.notifier
            self.notifier.add_observer(self.on_tunnel_remove, NTFY_TUNNEL, [NTFY_REMOVE])

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Fri Jul 1 15:22:20 2016
        # curve: None
        # len:571 bits ~ 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000407afa96c83660dccfbf02a45b68f4bc
        # 4957539860a3fe1ad4a18ccbfc2a60af1174e1f5395a7917285d09ab67c3d80c56caf5396fc5b231d84ceac23627
        # 930b4c35cbfce63a49805030dabbe9b5302a966b80eefd7003a0567c65ccec5ecde46520cfe1875b1187d469823d
        # 221417684093f63c33a8ff656331898e4bc853bcfaac49bc0b2a99028195b7c7dca0aea65
        # pub-sha1 15ade4f5fb0f0f8019d8430473aaba4305e61753
        # -----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQHr6lsg2YNzPvwKkW2j0vElXU5hgo/4a1KGMy/wqYK8RdOH1OVp5FyhdCatnw9g
        # MVsr1OW/FsjHYTOrCNieTC0w1y/zmOkmAUDDau+m1MCqWa4Du/XADoFZ8ZczsXs3kZSDP4YdbEYfUaYI9IhQXaECT9jwzqP9l
        # YzGJjkvIU7z6rEm8CyqZAoGVt8fcoK6mU=
        # -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000407afa96c83660dccfbf02a45b68f4bc" + \
                     "4957539860a3fe1ad4a18ccbfc2a60af1174e1f5395a7917285d09ab67c3d80c56caf5396fc5b231d84ceac23627" + \
                     "930b4c35cbfce63a49805030dabbe9b5302a966b80eefd7003a0567c65ccec5ecde46520cfe1875b1187d469823d" + \
                     "221417684093f63c33a8ff656331898e4bc853bcfaac49bc0b2a99028195b7c7dca0aea65"
        return [dispersy.get_member(public_key=master_key.decode("HEX"))]

    def initiate_meta_messages(self):
        """
        Setup all message that can be received by this community and the super classes.
        :return: list of meta messages.
        """
        return super(MultiChainCommunity, self).initiate_meta_messages() + [
            Message(self, HALF_BLOCK,
                    MemberAuthentication(),
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
        return [DefaultConversion(self), MultiChainConversion(self)]

    def send_block(self, candidate, block):
        self.logger.debug("Sending block to %s (%s)", candidate.get_member().public_key.encode("hex")[-8:], block)
        message = self.get_meta_message(HALF_BLOCK).impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(block,))
        try:
            self.dispersy.store_update_forward([message], False, False, True)
        except DelayPacketByMissingMember:
            self.logger.warn("Missing member in MultiChain community to send signature request to")

    def sign_block(self, candidate, bytes_up=None, bytes_down=None, linked=None):
        """
        Create, sign, persist and send a block signed message
        :param candidate: The peer with whom you have interacted, as a dispersy candidate
        :param bytes_up: The bytes you have uploaded to the peer in this interaction
        :param bytes_down: The bytes you have downloaded from the peer in this interaction
        :param linked: The block that the requester is asking us to sign
        """
        # NOTE to the future: This method reads from the database, increments and then writes back. If in some future
        # this method is allowed to execute in parallel, be sure to lock from before .create upto after .add_block
        assert bytes_up is None and bytes_down is None and linked is not None or \
            bytes_up is not None and bytes_down is not None and linked is None, \
            "Either provide a linked block or byte counts, not both"
        assert linked is None or linked.link_public_key == self.my_member.public_key, \
            "Cannot counter sign block not addressed to me"
        assert linked is None or linked.link_sequence_number == UNKNOWN_SEQ, \
            "Cannot counter sign block that is not a request"

        if candidate.get_member():
            if linked is None:
                block = MultiChainBlock.create(self.persistence, self.my_member.public_key)
                block.up = bytes_up
                block.down = bytes_down
                block.total_up += bytes_up
                block.total_down += bytes_down
                block.link_public_key = candidate.get_member().public_key
            else:
                block = MultiChainBlock.create(self.persistence, self.my_member.public_key, linked)
            block.sign(self.my_member.private_key)
            validation = block.validate(self.persistence)
            self.logger.info("Signed block to %s (%s) validation result %s",
                             candidate.get_member().public_key.encode("hex")[-8:], block, validation)
            if validation[0] != ValidationResult.partial_next and validation[0] != ValidationResult.valid:
                self.logger.error("Signed block did not validate?!")
            else:
                self.persistence.add_block(block)
                self.send_block(candidate, block)
        else:
            self.logger.warn("Candidate %s has no associated member?! Unable to sign block.", candidate)

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
            if blk.link_sequence_number == UNKNOWN_SEQ and \
                    blk.link_public_key == self.my_member.public_key and \
                    self.persistence.get_linked(blk) is None:

                self.logger.info("Received request block addressed to us (%s)", blk)

                # determine if we want to (i.e. the requesting public key has enough pending bytes)
                pend = self.pending_bytes.get(message.candidate.get_member().public_key)
                if pend and pend.add(-blk.down, -blk.up):
                    # It is important that the request matches up with its previous block, gaps cannot be tolerated at
                    # this point. We already dropped invalids, so here we delay this message if the result is partial,
                    # partial_previous or no-info. We send a crawl request to the requester to (hopefully) close the gap
                    if validation[0] == ValidationResult.partial_previous or \
                                    validation[0] == ValidationResult.partial or \
                                    validation[0] == ValidationResult.no_info:
                        # Note that this code does not cover the scenario where we obtain this block indirectly.

                        self.send_crawl_request(message.candidate, max(GENESIS_SEQ, blk.sequence_number - 5))
                        # Correct pending bytes since we did not sign the block yet
                        pend.add(blk.down, blk.up)
                        # Make sure we get called again after a while. Note that the cleanup task on pend will prevent
                        # us from waiting on the peer forever
                        if not self.is_pending_task_active("crawl_%s" % blk.hash):
                            self.register_task("crawl_%s" % blk.hash, reactor.callLater(5.0, self.received_half_block,
                                                                                    [message]))
                    else:
                        self.sign_block(message.candidate, None, None, blk)

    def send_crawl_request(self, candidate, sequence_number=None):
        sq = sequence_number
        if sequence_number is None:
            blk = self.persistence.get_latest(candidate.get_member().public_key)
            sq = blk.sequence_number if blk else GENESIS_SEQ
        sq = max(GENESIS_SEQ, sq)
        self.logger.info("Requesting crawl of node %s:%d", candidate.get_member().public_key.encode("hex")[-8:], sq)
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
    def get_statistics(self):
        """
        Returns a dictionary with some statistics regarding the local multichain database
        :returns a dictionary with statistics
        """
        latest_block = self.persistence.get_latest(self.my_member.public_key)
        statistics = dict()
        statistics["self_id"] = self.my_member.public_key.encode("hex")
        (statistics["self_peers_helped"],
         statistics["self_peers_helped_you"]) = self.persistence.get_num_unique_interactors(self.my_member.public_key)
        if latest_block:
            statistics["self_total_blocks"] = latest_block.sequence_number
            statistics["self_total_up"] = latest_block.total_up
            statistics["self_total_down"] = latest_block.total_down
            statistics["latest_block_insert_time"] = str(latest_block.insert_time)
            statistics["latest_block_id"] = latest_block.hash.encode("hex")
            statistics["latest_block_link_public_key"] = latest_block.link_public_key.encode("hex")
            statistics["latest_block_link_sequence_number"] = latest_block.link_sequence_number
            statistics["latest_block_up"] = latest_block.up
            statistics["latest_block_down"] = latest_block.down
        else:
            statistics["self_total_blocks"] = 0
            statistics["self_total_up"] = 0
            statistics["self_total_down"] = 0
            statistics["latest_block_insert_time"] = ""
            statistics["latest_block_id"] = ""
            statistics["latest_block_link_public_key"] = ""
            statistics["latest_block_link_sequence_number"] = 0
            statistics["latest_block_up"] = 0
            statistics["latest_block_down"] = 0
        return statistics

    @inlineCallbacks
    def unload_community(self):
        self.logger.debug("Unloading the MultiChain Community.")
        if self.notifier:
            self.notifier.remove_observer(self.on_tunnel_remove)
        for pk in self.pending_bytes:
            if self.pending_bytes[pk].clean is not None:
                self.pending_bytes[pk].clean.reset(0)
        yield super(MultiChainCommunity, self).unload_community()
        # Close the persistence layer
        self.persistence.close()

    @forceDBThread
    def on_tunnel_remove(self, subject, change_type, tunnel, candidate):
        """
        Handler for the remove event of a tunnel. This function will attempt to create a block for the amounts that
        where transferred using the tunnel.
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
                                   reactor.callLater(5, self.sign_block, candidate, tunnel.bytes_up, tunnel.bytes_down))
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


class MultiChainCommunityCrawler(MultiChainCommunity):
    """
    Extended MultiChainCommunity that also crawls other MultiChainCommunities.
    It requests the chains of other MultiChains.
    """

    # Time the crawler waits between crawling a new candidate.
    CrawlerDelay = 5.0

    def on_introduction_response(self, messages):
        super(MultiChainCommunityCrawler, self).on_introduction_response(messages)
        for message in messages:
            self.send_crawl_request(message.candidate)

    def start_walking(self):
        self.register_task("take step", LoopingCall(self.take_step)).start(self.CrawlerDelay, now=False)
