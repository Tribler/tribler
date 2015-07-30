"""
File containing the MultiChain Community.
The MultiChain Community is the first step in an incremental approach in building a new reputation system.
This reputation system builds a tamper proof interaction history contained in a chain data-structure.
Every node has a chain and these chains intertwine by blocks shared by chains.
Full documentation will be available at http://repository.tudelft.nl/.
"""

import logging
import base64
from twisted.internet.task import LoopingCall

from Tribler.dispersy.authentication import DoubleMemberAuthentication, MemberAuthentication
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.community import Community
from Tribler.dispersy.message import Message
from Tribler.dispersy.conversion import DefaultConversion

from Tribler.community.multichain.payload import SignaturePayload, BlockRequestPayload, BlockResponsePayload
from Tribler.community.multichain.database import MultiChainDB, DatabaseBlock
from Tribler.community.multichain.conversion import MultiChainConversion, split_function

SIGNATURE = u"signature"
BLOCK_REQUEST = u"block_request"
BLOCK_RESPONSE = u"block_response"

""" ID of the first block of the chain. """
GENESIS_ID = '0' * 20


class MultiChainScheduler:
    """
    Schedules when blocks are requested by the MultiChainCommunity.
    The Scheduler keeps track of the outstanding amount per candidate.
    This outstanding amount is not persisted and is lost when Tribler is restarted.
    This is a very simple version that should be expanded in the future.
    """
    """ The amount of bytes that the Scheduler will be altruistic about and allows to be outstanding. """
    threshold = 5000

    def __init__(self, community):
        """
        Create the MultiChainScheduler
        :param community: The MultiChainCommunity that will be used to send requests.
        """
        """ Key: candidate's mid Value: amount of data not yet created into a block """
        self._outstanding_amount_send = {}
        self._outstanding_amount_received = {}
        """ The MultiChainCommunity that will be used to send requests. """
        self._community = community

    def update_amount_send(self, peer, amount_send):
        """
        Update the amount of data send. If the amount is above the threshold, then a block will be created.
        :param peer: (address, port) translated into a Candidate.
        :param amount_send: amount of bytes send to the peer.
        :return: None
        """
        self._community.logger.debug("Updating amount send for: %s" % peer[0])
        total_amount_send = self._outstanding_amount_send.get(peer, 0) + amount_send
        self._outstanding_amount_send[peer] = total_amount_send
        if total_amount_send >= self.threshold:
            candidate = self._community.get_candidate(peer)
            if candidate and candidate.get_member():
                total_amount_received = self._outstanding_amount_received.get(peer, 0)
                """ Convert to MB """
                total_amount_sent_mb = total_amount_send / 1000
                total_amount_received_mb = total_amount_received / 1000
                """ Try to sent the request """
                request_sent = self._community. \
                    publish_signature_request_message(candidate, total_amount_sent_mb, total_amount_received_mb)
                if request_sent:
                    """ Reset the outstanding amounts and send a signature request for the outstanding amount"""
                    self._outstanding_amount_send[peer] = 0
                    self._outstanding_amount_received[peer] = 0
            else:
                self._community.logger.debug(
                    "No valid candidate found for: %s:%s to request block from." % (peer[0], peer[1]))

    def update_amount_received(self, peer, amount_received):
        """
        Update the amount of data send. If the amount is above the threshold, then a block will be created.
        :param peer: (address, port) translated into a Candidate.
        :param amount_received: amount of bytes received from a peer
        :return: None
        """
        self._community.logger.debug("Updating amount received for: %s" % peer[0])
        self._outstanding_amount_received[peer] = self._outstanding_amount_received.get(peer, 0) + amount_received
        # TODO this amount received has to be checked in the future when signature_requests come in.


class MultiChainCommunity(Community):
    """
    Community for reputation based on MultiChain tamper proof interaction history.
    """

    """ Amount of time the MultiChain waits on a signature requests before it times out"""
    signature_request_timeout = 5.0

    def __init__(self, *args, **kwargs):
        super(MultiChainCommunity, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

        self._ec = self.my_member.private_key
        self._mid = self.my_member.mid
        self.persistence = MultiChainDB(self.dispersy, self.dispersy.working_directory)
        """
        Exclusion flag for operations on the chain. Only one operation can be pending on the chain at any time.
        Without exclusion the chain will be corrupted and branches will be created.
        This exclusion flag ensures that only one operation is pending.
        """
        self.chain_exclusion_flag = False
        # No response is expected yet.
        self.expected_response = None

    def initialize(self, a=None, b=None):
        super(MultiChainCommunity, self).initialize()

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Wed Dec  3 10:31:16 2014
        # curve: NID_sect571r1
        # len: 571 bits ~ 144 bytes signature
        # pub: 170  3081a7301006072a8648ce3d020106052b810400270381920004059f45b75d63f865e3c7b350bd3ccdc99dbfbf76f
        # dfb524939f070223c3ea9ea5d0536721cf9afbbec5693798e289b964fefc930961dfe1a7f71c445031434aba637bb9
        # 3b947fb81603f649d4a08e5698e677059b9d3a441986c16f8da94d4aa2afbf10fe056cd65741108fe6a880606869c
        # a81fdcb2db302ac15905d6e75f96b39ccdaf068bdbbda81a6356f53f7ce4e
        # pub-sha1 f66a50b35c4a0d45abd0052f574c5ecc233b8e54
        # -----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQFn0W3XWP4ZePHs1C9PM3Jnb+/dv37
        # Ukk58HAiM+qepdBTZyHPmvu+xWk3mOKJuWT+/JMJYd/hp/ccRFAxQ0q6Y3u5O5R/
        # uBYD9knUoI5WmOZ3BZudOkQZhsFvjalNSqKvvxD+BWzWV0EQj+aogGBoacqB/cst
        # swKsFZBdbnX5aznM2vBovbvagaY1b1P3zk4=
        # -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b810400270381920004059f45b75d63f865e3c7b350bd3ccdc99dbfbf76f" + \
                     "dfb524939f0702233ea9ea5d0536721cf9afbbec5693798e289b964fefc930961dfe1a7f71c445031434aba637bb9" + \
                     "3b947fb81603f649d4a08e5698e677059b9d3a441986c16f8da94d4aa2afbf10fe056cd65741108fe6a880606869c" + \
                     "a81fdcb2db302ac15905d6e75f96b39ccdaf068bdbbda81a6356f53f7ce4e"
        master_key_hex = master_key.decode("HEX")
        master = dispersy.get_member(public_key=master_key_hex)
        return [master]

    def initiate_meta_messages(self):
        """
        Setup all message that can be received by this community and the super classes.
        :return: list of meta messages.
        """
        return super(MultiChainCommunity, self).initiate_meta_messages() + [
            Message(self, SIGNATURE,
                    DoubleMemberAuthentication(
                        allow_signature_func=self.allow_signature_request, split_payload_func=split_function),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    SignaturePayload(),
                    self._generic_timeline_check,
                    self.received_signature_response),
            Message(self, BLOCK_REQUEST,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    BlockRequestPayload(),
                    self._generic_timeline_check,
                    self.received_request_block),
            Message(self, BLOCK_RESPONSE,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    BlockResponsePayload(),
                    self._generic_timeline_check,
                    self.received_block_response), ]

    def initiate_conversions(self):
        return [DefaultConversion(self), MultiChainConversion(self)]

    def publish_signature_request_message(self, candidate, up, down):
        """
        Creates and sends out a signed signature_request message if the chain is free for operations.
        If it is the request is send and True is returned, else False.
        :param candidate: The candidate that the signature request will send to.
        :param (int) up: The amount of bytes that have been sent to the candidate that need to signed.
        :param (int) down: The amount of bytes that have been received from the candidate that need to signed.
        return (bool) if request is sent.
        """

        """
        Acquire exclusive flag to perform operations on the chain.
        The chain_exclusion_flag is lifted after the timeout or a valid signature response is received.
        """
        self.logger.debug("Chain Exclusion: signature request: %s" % self.chain_exclusion_flag)
        if not self.chain_exclusion_flag:
            self.chain_exclusion_flag = True
            self.logger.debug("Chain Exclusion: acquired, sending signature request.")
            self.logger.info("Sending signature request.")

            message = self.create_signature_request_message(candidate, up, down)
            self.create_signature_request(candidate, message, self.allow_signature_response,
                                          timeout=self.signature_request_timeout)
            return True
        else:
            self.logger.debug("Chain Exclusion: not acquired, dropping signature request.")
            return False

    def create_signature_request_message(self, candidate, up, down):
        """
        Create a signature request message using the current time stamp.
        :return: Signature_request message ready for distribution.
        """
        # Instantiate the data
        total_up_requester, total_down_requester = self._get_next_total(up, down)
        # Instantiate the personal information
        sequence_number_requester = self._get_next_sequence_number()
        previous_hash_requester = self._get_latest_hash()

        payload = (up, down, total_up_requester, total_down_requester,
                   sequence_number_requester, previous_hash_requester)
        meta = self.get_meta_message(SIGNATURE)

        message = meta.impl(authentication=([self.my_member, candidate.get_member()],),
                            distribution=(self.claim_global_time(),),
                            payload=payload)
        return message

    def allow_signature_request(self, message):
        """
        We've received a signature request message, we must either:
            a. append to this message our data (Afterwards we sign the message.).
            b. None (if we want to drop this message)
        """
        self.logger.info("Received signature request.")
        self.logger.debug("Chain Exclusion: process request: %s" % self.chain_exclusion_flag)
        # Check if the exclusion flag can be acquired without blocking to perform operations on the chain.
        if not self.chain_exclusion_flag:
            self.chain_exclusion_flag = True
            self.logger.debug("Chain Exclusion: acquired to process request.")
            # TODO: This code always signs a request. Checks and rejects should be inserted here!
            # TODO: Like basic total_up == previous_total_up + block.up or more sophisticated chain checks.
            payload = message.payload

            total_up_responder, total_down_responder = self._get_next_total(payload.up, payload.down)
            sequence_number_responder = self._get_next_sequence_number()
            previous_hash_responder = self._get_latest_hash()

            payload = (payload.up, payload.down, payload.total_up_requester, payload.total_down_requester,
                       payload.sequence_number_requester, payload.previous_hash_requester,
                       total_up_responder, total_down_responder,
                       sequence_number_responder, previous_hash_responder)

            meta = self.get_meta_message(SIGNATURE)

            message = meta.impl(authentication=(message.authentication.members, message.authentication.signatures),
                                distribution=(message.distribution.global_time,),
                                payload=payload)
            self.persist_signature_response(message)
            # Operation on chain done, release the chain_exclusion_flag for other operations.
            self.chain_exclusion_flag = False
            self.logger.debug("Chain Exclusion: released processing request.")
            self.logger.info("Sending signature response.")
            return message
        else:
            self.logger.debug("Chain Exclusion: not acquired. Dropping request.")
            return None

    def allow_signature_response(self, request, response, modified):
        """
        We've received a signature response message after sending a request, we must return either:
            a. True, if we accept this message
            b. False, if not (because of inconsistencies in the payload)
        """
        if not response:
            self.logger.info("Timeout received for signature request.")
            # Unpack the message from the cache object and store a half-signed record.
            self.persist_signature_response(request.request.payload.message)
            self.chain_exclusion_flag = False
            return False
        else:
            # TODO: Check expecting response
            self.logger.info("Signature response received. Modified: %s" % modified)
            return request.payload.sequence_number_requester == response.payload.sequence_number_requester and \
                   request.payload.previous_hash_requester == response.payload.previous_hash_requester and \
                   modified

    def received_signature_response(self, messages):
        """
        We've received a valid signature response and must process this message.
        """
        self.logger.info("Valid %s signature response(s) received." % len(messages))
        for message in messages:
            self.persist_signature_response(message)
            # Release exclusion flag because the operation is done.
            self.logger.debug("Chain exclusion: released received signature response.")
            self.chain_exclusion_flag = False

    def persist_signature_response(self, message):
        """
        Persist the signature response message.
        A hash will be created from the message and this will be used as an unique identifier.
        :param message:
        """
        block = DatabaseBlock.from_signature_response_message(message)
        self.logger.info("Persisting sr: %s" % base64.encodestring(block.id))
        self.persistence.add_block(block)

    def publish_request_block_message(self, candidate, sequence_number=-1):
        """
        Request a specific block from a chain of another candidate.
        :param candidate: The candidate that the block is requested from
        :param sequence_number: The requested sequence_number or default the latest sequence number
        """
        self.logger.info("Crawler: Requesting Block:%s" % sequence_number)
        meta = self.get_meta_message(BLOCK_REQUEST)

        message = meta.impl(authentication=(self.my_member,),
                            distribution=(self.claim_global_time(),),
                            destination=(candidate,),
                            payload=(sequence_number,))
        self.dispersy.store_update_forward([message], False, False, True)

    def received_request_block(self, messages):
        for message in messages:
            requested_sequence_number = message.payload.requested_sequence_number
            self.logger.info("Crawler: Received request for block: %s" % requested_sequence_number)
            self.publish_block(message.candidate, requested_sequence_number)

    def publish_block(self, candidate, sequence_number):
        if sequence_number == -1:
            # latest sequence number to be published.
            sequence_number = self.persistence.get_latest_sequence_number(self._mid)
        requested_block = self.persistence.get_by_sequence_number_and_mid(sequence_number, self._mid)
        if requested_block:
            self.logger.info("Crawler: Sending block: %s" % sequence_number)
            meta = self.get_meta_message(BLOCK_RESPONSE)

            message = meta.impl(authentication=(self.my_member,),
                                distribution=(self.claim_global_time(),),
                                destination=(candidate,),
                                payload=requested_block.to_payload())

            self.dispersy.store_update_forward([message], False, False, True)
        else:
            self.logger.info("Crawler: Received invalid request for block: %s" % sequence_number)

    def received_block_response(self, messages):
        """
        We've received a valid block response and must process this message.
        """
        self.logger.info("Crawler: Valid %s block response(s) received." % len(messages))
        for message in messages:
            requester = self.dispersy.get_member(public_key=message.payload.public_key_requester)
            responder = self.dispersy.get_member(public_key=message.payload.public_key_responder)
            block = DatabaseBlock.from_block_response_message(message, requester, responder)
            # Create the hash of the message
            if not self.persistence.contains(block.id):
                self.logger.info("Crawler: Persisting sr: %s" % base64.encodestring(block.id))
                self.persistence.add_block(block)
                # Crawl further down the chain.
                self.crawl_down(block.previous_hash_requester, block.sequence_number_requester - 1,
                                block.public_key_requester)
                self.crawl_down(block.previous_hash_responder, block.sequence_number_responder - 1,
                                block.public_key_responder)
            else:
                self.logger.info("Crawler: Received already known block")

    def crawl_down(self, next_hash, sequence_number, public_key):
        # Check if it is not the genesis block.
        if sequence_number >= 0:
            # Check if the block is not already known.
            if not self.persistence.contains(next_hash):
                member = self.dispersy.get_member(public_key=public_key)
                candidate = self.get_candidate_mid(member.mid) if member else None
                # Check if the candidate is known.
                if candidate:
                    self.logger.info("Crawler: down: crawling down.")
                    self.publish_request_block_message(candidate, sequence_number)
                else:
                    self.logger.info("Crawler: down: candidate unknown.")
            else:
                self.logger.info("Crawler: down: reached known block.")
        else:
            self.logger.info("Crawler: down: reached genesis block.")

    def get_key(self):
        return self._ec

    def _get_next_total(self, up, down):
        """
        Returns the next total numbers of up and down incremented with the current interaction up and down metric.
        :param up: Up metric for the interaction.
        :param down: Down metric for the interaction.
        :return: (total_up (int), total_down (int)
        """
        total_up, total_down = self.persistence.get_total(self._mid)
        if total_up == total_down == -1:
            return up, down
        else:
            return total_up + up, total_down + down

    def _get_next_sequence_number(self):
        return self.persistence.get_latest_sequence_number(self._mid) + 1

    def _get_latest_hash(self):
        previous_hash = self.persistence.get_previous_id(self._mid)
        return previous_hash if previous_hash else GENESIS_ID

    def unload_community(self):
        self.logger.debug("Unloading the MultiChain Community.")
        super(MultiChainCommunity, self).unload_community()
        # Close the persistence layer
        self.persistence.close()


class MultiChainCommunityCrawler(MultiChainCommunity):
    """
    Extended MultiChainCommunity that also crawls other MultiChainCommunities.
    It requests the chains of other MultiChains.
    """

    """ Time the crawler waits between crawling a new candidate."""
    CrawlerDelay = 5.0

    def __init__(self, *args, **kwargs):
        super(MultiChainCommunityCrawler, self).__init__(*args, **kwargs)

    def on_introduction_response(self, messages):
        super(MultiChainCommunityCrawler, self).on_introduction_response(messages)
        for message in messages:
            self.publish_request_block_message(message.candidate)

    def start_walking(self):
        self.register_task("take step", LoopingCall(self.take_step)).start(self.CrawlerDelay, now=True)
