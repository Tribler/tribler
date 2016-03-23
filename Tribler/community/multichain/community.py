"""
The MultiChain Community is the first step in an incremental approach in building a new reputation system.
This reputation system builds a tamper proof interaction history contained in a chain data-structure.
Every node has a chain and these chains intertwine by blocks shared by chains.
"""
import logging
import base64
from twisted.internet.defer import inlineCallbacks

from twisted.internet.task import LoopingCall
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_REMOVE
from Tribler.dispersy.authentication import DoubleMemberAuthentication, MemberAuthentication
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.community import Community
from Tribler.dispersy.message import Message, DelayPacketByMissingMember
from Tribler.dispersy.conversion import DefaultConversion

from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_REMOVE
from Tribler.community.multichain.block import MultiChainBlock
from Tribler.community.multichain.payload import (HalfBlockPayload, FullBlockPayload, CrawlRequestPayload,
                                                  CrawlResumePayload)
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.community.multichain.database import MultiChainDB
from Tribler.community.multichain.conversion import MultiChainConversion

SIGNED = u"signed"
HALF_BLOCK = u"half_block"
FULL_BLOCK = u"full_block"
CRAWL = u"crawl"
RESUME = u"resume"


class MultiChainCommunity(Community):
    """
    Community for reputation based on MultiChain tamper proof interaction history.
    """

    def __init__(self, *args, **kwargs):
        super(MultiChainCommunity, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.notifier = None
        self.persistence = MultiChainDB(self.dispersy.working_directory)
        self.logger.debug("The multichain community started with Public Key: %s",
                          base64.encodestring(self.my_member.public_key).strip())

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
            Message(self, SIGNED,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    HalfBlockPayload(),
                    self._generic_timeline_check,
                    self.received_signed_block),
            Message(self, HALF_BLOCK,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    HalfBlockPayload(),
                    self._generic_timeline_check,
                    self.received_half_block),
            Message(self, FULL_BLOCK,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    FullBlockPayload(),
                    self._generic_timeline_check,
                    self.received_full_block),
            Message(self, CRAWL,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlRequestPayload(),
                    self._generic_timeline_check,
                    self.received_crawl_request),
            Message(self, RESUME,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlResumePayload(),
                    self._generic_timeline_check,
                    self.received_crawl_resumption)]

    def initiate_conversions(self):
        return [DefaultConversion(self), MultiChainConversion(self)]

    def sign_block(self, candidate, bytes_up, bytes_down):
            """
            Create, sign, persist and send a block signed message
            :param candidate: The peer with whom you have interacted, as a dispersy candidate
            :param bytes_up: The bytes you have uploaded to the peer in this interaction
            :param bytes_down: The bytes you have downloaded from the peer in this interaction
            """
            self.logger.info("Sign block called. Candidate: {0} [Up = {1} | Down = {2}]".
                             format(str(candidate), bytes_up, bytes_down))
            if candidate and candidate.get_member():
                # TODO: proper form requires a local lock here (up to db add) to ensure atomic db operation
                block = MultiChainBlock.create(self.persistence, self._public_key)
                block.up = bytes_up
                block.down = bytes_down
                block.total_up += bytes_up
                block.total_down += bytes_down
                block.link_public_key = candidate.get_member().public_key
                block.sign(self._private_key)
                self.persistence.add_block(block)
                message = self.get_meta_message(SIGNED).impl(
                    authentication=(self.my_member,),
                    distribution=(self.claim_global_time(),),
                    destination=(candidate,),
                    payload=(block,))
                try:
                    self.dispersy.store_update_forward([message], False, False, True)
                except DelayPacketByMissingMember:
                    self.logger.warn("Missing member in MultiChain community to send signature request to")
            else:
                self.logger.warn(
                    "No valid candidate found for: %s:%s to request block from." % (candidate[0], candidate[1]))

    def received_signed_block(self, messages):
        """
        We've received a signed block(s), and should consider counter signing
        :param messages The received half block messages
        """
        self.logger.info("%s signed block(s) received." % len(messages))
        for message in messages:
            blk = message.payload.block
            self.logger.info("Received signed block: [Up = {0} | Down = {1}]".format(blk.up, blk.down))
            validation = self.process_block(blk)
            if validation[0] == "invalid":
                continue

            match = MultiChainBlock.create(self.persistence, self._public_key, blk)
            match.sign(self._private_key)
            self.persistence.add_block(match)
            self.dispersy.store_update_forward([
                self.get_meta_message(HALF_BLOCK).impl(
                    authentication=(self.my_member,),
                    distribution=(self.claim_global_time(),),
                    destination=(message.candidate,),
                    payload=(match,))], False, False, True)

    def received_half_block(self, messages):
        """
        We've received a half block, either because we sent a SIGNED message to some one or we are crawling
        :param messages The half block messages
        """
        self.logger.info("%s half block(s) received." % len(messages))
        for message in messages:
            self.process_block(message.payload.block)

    def received_full_block(self, messages):
        """
        We've received a full block, either because we sent a SIGNED message to some one or we are crawling
        :param messages The full block messages
        """
        self.logger.info("%s full block(s) received." % len(messages))
        for message in messages:
            self.process_block(message.payload.block_this)
            self.process_block(message.payload.block_that)

    def send_crawl_request(self, candidate, sequence_number=None):
        sq = sequence_number
        if sequence_number is None:
            blk = self.persistence.get_latest(candidate.get_member().public_key)
            sq = blk.sequence_number if blk else 0
        self.logger.info("Crawler: Requesting crawl from node %s, from sequence number %d" %
                         (base64.encodestring(candidate.get_member().mid).strip(), sq))
        message = self.get_meta_message(CRAWL).impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(sq,))
        self.dispersy.store_update_forward([message], False, False, True)

    def received_crawl_request(self, messages):
        for message in messages:
            self.logger.info("Crawler: Received crawl request from node %s, from sequence number %d" %
                             (base64.encodestring(message.candidate.get_member().public_key).strip(),
                              message.payload.requested_sequence_number))
            self.crawl_requested(message.candidate, message.payload.requested_sequence_number)

    def crawl_requested(self, candidate, sequence_number):
        blocks = self.persistence.get_blocks_since(self._public_key, sequence_number)
        if len(blocks) > 0:
            self.logger.debug("Crawler: Sending %d blocks", len(blocks))
            messages = []
            for blk in blocks:
                linked = self.persistence.get_linked(blk)
                if linked is None:
                    messages.append(
                        self.get_meta_message(HALF_BLOCK).impl(
                            authentication=(self.my_member,),
                            distribution=(self.claim_global_time(),),
                            destination=(candidate,),
                            payload=(blk,)
                        )
                    )
                else:
                    messages.append(
                        self.get_meta_message(FULL_BLOCK).impl(
                            authentication=(self.my_member,),
                            distribution=(self.claim_global_time(),),
                            destination=(candidate,),
                            payload=(blk,linked)
                        )
                    )
            self.logger.info("Crawler: Sending %d blocks" % len(messages))
            self.dispersy.store_update_forward(messages, False, False, True)
        else:
            # This is slightly worrying since the last block should always be returned.
            # Or rather, the other side is requesting blocks starting from a point in the future.
            self.logger.info("Crawler: No blocks")
        if len(blocks) > 1:
            # we sent more than 1 block. Send a resumption token so the other side knows it should continue crawling
            message = self.get_meta_message(RESUME).impl(
                authentication=(self.my_member,),
                distribution=(self.claim_global_time(),),
                destination=(candidate,),
                payload=())
            self.dispersy.store_update_forward([message], False, False, True)

    def received_crawl_resumption(self, messages):
        self.logger.info("Crawler: Valid %s crawl resumptions received.", len(messages))
        for message in messages:
            self.send_crawl_request(message.candidate)

    @blocking_call_on_reactor_thread
    def get_statistics(self):
        """
        Returns a dictionary with some statistics regarding the local multichain database
        :returns a dictionary with statistics
        """
        latest_block = self.persistence.get_latest(self.my_member.public_key)
        statistics = dict()
        statistics["self_id"] = base64.encodestring(self._public_key).strip()
        (statistics["self_peers_helped"],
         statistics["self_peers_helped_you"]) = self.persistence.get_num_unique_interactors(self._public_key)
        if latest_block:
            statistics["self_total_blocks"] = latest_block.sequence_number
            statistics["self_total_up_mb"] = latest_block.total_up
            statistics["self_total_down_mb"] = latest_block.total_down
            statistics["latest_block_insert_time"] = str(latest_block.insert_time)
            statistics["latest_block_id"] = base64.encodestring(latest_block.hash)
            statistics["latest_block_link_public_key"] = base64.encodestring(latest_block.link_public_key)
            statistics["latest_block_link_sequence_number"] = base64.encodestring(latest_block.link_sequence_number)
            statistics["latest_block_up_mb"] = str(latest_block.up)
            statistics["latest_block_down_mb"] = str(latest_block.down)
        else:
            statistics["self_total_blocks"] = 0
            statistics["self_total_up_mb"] = 0
            statistics["self_total_down_mb"] = 0
            statistics["latest_block_insert_time"] = ""
            statistics["latest_block_id"] = ""
            statistics["latest_block_link_public_key"] = ""
            statistics["latest_block_link_sequence_number"] = ""
            statistics["latest_block_up_mb"] = ""
            statistics["latest_block_down_mb"] = ""
        return statistics

    def process_block(self, blk):
        """
        Validates blocks and adds them to the database if needed
        :param blk: the block to validate and add
        :return: the validation result tuple (see MultiChainBlock.validate for details)
        """
        validation = blk.validate(self.persistence)
        self.logger.info("Block validation result {0}, {1}".format(validation[0], validation[1]))
        if validation[0] == "invalid":
            pass
        elif self.persistence.contains(blk):
            self.logger.info("Processing already known block")
        else:
            self.persistence.add_block(blk)
        return validation

    @inlineCallbacks
    def unload_community(self):
        self.logger.debug("Unloading the MultiChain Community.")
        if self.notifier:
            self.notifier.remove_observer(self.on_tunnel_remove)
        yield super(MultiChainCommunity, self).unload_community()
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

        if isinstance(tunnel.bytes_up, int) and isinstance(tunnel.bytes_down, int):
            # Tie breaker to prevent both parties from requesting
            if self._public_key > candidate.get_member().public_key:
                self.schedule_block(candidate, tunnel.bytes_up, tunnel.bytes_down)
            # else:
                # TODO Note that you still expect a signature request for these bytes:
                # pending[peer] = (up, down)


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
