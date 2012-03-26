from conversion import BarterCommunityConversion
from database import BarterDatabase
from payload import BarterRecordPayload

from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.message import Message, DropMessage
from Tribler.Core.dispersy.authentication import MultiMemberAuthentication
from Tribler.Core.dispersy.resolution import PublicResolution
from Tribler.Core.dispersy.distribution import LastSyncDistribution, FullSyncDistribution
from Tribler.Core.dispersy.destination import CommunityDestination

from random import random

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint
    from lencoder import log

class BarterCommunity(Community):
    """
    Community to that stored barter records (person A uploaded so and so much data to person B)
    distributely.  Using these barter records we can order members based on how much they
    contributed and consumed from the community.
    """

    def __init__(self, cid, master_key):
        super(BarterCommunity, self).__init__(cid, master_key)

        # storage
        self._database = BarterDatabase.get_instance()

        # mapping between public_keys and peer_ids
        self._peer_ids = {}

    @property
    def dispersy_randomness(self):
        "defines whether to use randomness or not"
        return False

    @property
    def dispersy_sync_initial_delay(self):
        "5.0"
        if self.dispersy_randomness:
            return 10.0 * random()
        else:
            return 5.0


    @property
    def dispersy_sync_interval(self):
        "20.0"
        if self.dispersy_randomness:
            return 10.0 + 20.0 * random()
        else:
            return 20.0

    @property
    def dispersy_sync_member_count(self):
        return 1

    @property
    def dispersy_candidate_request_initial_delay(self):
        return 12 * 3600.0

    @property
    def dispersy_candidate_request_interval(self):
        return 12 * 3600.0

    @property
    def dispersy_candidate_request_member_count(self):
        return 1

    @property
    def dispersy_sync_response_limit(self):
       return 5 * 1024

    @property
    def barter_forward_record_on_creation(self):
        return True

    def initiate_meta_messages(self):
        # return [Message(self, u"barter-record", MultiMemberAuthentication(count=2, allow_signature_func=self.allow_signature_request), PublicResolution(), LastSyncDistribution(synchronization_direction=u"out-order", history_size=1), CommunityDestination(node_count=10), BarterRecordPayload(), self.check_barter_record, self.on_barter_record)]
        return [Message(self, u"barter-record", MultiMemberAuthentication(count=2, allow_signature_func=self.allow_signature_request), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), BarterRecordPayload(), self.check_barter_record, self.on_barter_record)]

    def initiate_conversions(self):
        return [DefaultConversion(self), BarterCommunityConversion(self)]

    def create_barter_record(self, second_member, first_upload, second_upload, store=True, forward=True):
        """
        Create and return a signature request for a new barter record.

        A barter-record message is created, this message is owned by self._my_member.  A
        dispersy-signature-request message is then created to encapsulate the barter-record, send to
        OTHER_MEMBER, and returned.

        OTHER_MEMBER: the second person who will be asked to sign the barter-record message.

        MY_UPLOAD: the number of MB uploaded by self._my_member.

        OTHER_UPLOAD: the number of MB uploaded by OTHER_MEMBER.

        STORE_AND_FORWARD: when True, dispersy-signature-request is send to OTHER_MEMBER.
        """
        if __debug__:
            from Tribler.Core.dispersy.member import Member
        assert isinstance(second_member, Member)
        assert second_member.public_key
        assert isinstance(second_member, Member)
        assert not second_member.private_key
        assert isinstance(first_upload, (int, long))
        assert isinstance(second_upload, (int, long))

        if __debug__: log("barter.log", "create-dispersy-signature-request")

        meta = self.get_meta_message(u"barter-record")
        request = meta.impl(authentication=([self._my_member, second_member],),
                            distribution=(self.claim_global_time(),),
                            payload=(first_upload, second_upload))
        return self.create_dispersy_signature_request(request, self.on_signature_response, (request, 1), store=store, forward=forward)

    def allow_signature_request(self, message):
        """ Decide whether to reply or not to a signature request

        Currently I always sign for testing proposes
        """
        assert message.name == u"barter-record"
        assert not message.authentication.is_signed
        if __debug__: dprint(message)

        is_signed, other_member = message.authentication.signed_members[0]
        if other_member == self._my_member:
            if __debug__: dprint("refuse signature: we should be the first signer", level="warning")
            return False

        if not is_signed:
            if __debug__: dprint("refuse signature: the other member did not sign it", level="warning")
            return False

        my_member = message.authentication.members[1]
        if not my_member == self._my_member:
            if __debug__: dprint("refuse signature: we should be the second signer")
            return False

        # todo: decide if we want to use add our signature to this # record
        if True:
            # recalculate the limits of what we want to upload to member.authentication.members[0]
            return True

        # we will not add our signature
        return False

    def on_signature_response(self, message, request, retry):
        """ Handle a newly created double signed message or a timeout while signing

        When request for signing times out I just return. When I receive the signature for the
        message that I created then I send it to myself and then store and forward it to others of
        the community
        """
        if __debug__: dprint(message)

        if message:
            assert message.name == u"barter-record"
            assert message.authentication.is_signed

            if __debug__: dprint(message)

            # store, update, and forward to the community
            self._dispersy.store_update_forward([message], True, True, self.barter_forward_record_on_creation)
            log("dispersy.log", "created-barter-record") # TODO: maybe move to barter.log

        elif retry < 5:
            # signature timeout
            # retry
            if __debug__:
                log("barter.log", "barter-community-signature-request-timeout", retry=retry)
                dprint("Signature request timeout. Retry!")
                self.create_dispersy_signature_request(request, self.on_signature_response, (request, retry + 1))

        else:
            # close the transfer
            if __debug__:
                log("barter.log", "barter-community-signature-request-timeout", retry=retry)
                dprint("Signature request timeout")

    def check_barter_record(self, messages):
        # stupidly accept everything...
        return messages

    def on_barter_record(self, messages):
        """ I handle received barter records

        I create or update a row in my database
        """
        if __debug__: dprint("storing ", len(messages), " records")
        execute = self._database.execute
        for message in messages:
            if __debug__: log("dispersy.log", "handled-barter-record") # TODO: maybe move to barter.log
            # check if there is already a record about this pair
            try:
                first_member, second_member, global_time = \
                              execute(u"SELECT first_member, second_member, global_time FROM \
                              record WHERE (first_member = ? AND second_member = ?) OR \
                              (first_member = ? AND second_member = ?)",
                                      (message.authentication.members[0].database_id,
                                       message.authentication.members[1].database_id,
                                       message.authentication.members[1].database_id,
                                       message.authentication.members[0].database_id)).next()
            except StopIteration:
                global_time = -1
                first_member = message.authentication.members[0].database_id
                second_member = message.authentication.members[1].database_id

            if global_time >= message.distribution.global_time:
                # ignore the message
                if __debug__:
                    dprint("Ignoring older message")
            else:
                self._database.execute(u"INSERT OR REPLACE INTO \
                record(community, global_time, first_member, second_member, \
                upload_first_member, upload_second_member) \
                VALUES(?, ?, ?, ?, ?, ?)",
                                       (self._database_id,
                                        message.distribution.global_time,
                                        first_member,
                                        second_member,
                                        message.payload.first_upload,
                                        message.payload.second_upload))
                if __debug__:
                    peer1_id = self._peer_ids.get(message.authentication.members[0].public_key, -1)
                    peer2_id = self._peer_ids.get(message.authentication.members[1].public_key, -1)
                    peer1_upload = message.payload.first_upload
                    peer2_upload = message.payload.second_upload
                    if peer1_id > peer2_id:
                        peer1_id, peer2_id = peer2_id, peer1_id
                        peer1_upload, peer2_upload = peer2_upload, peer1_upload
                    log("barter.log", "barter-record", first=peer1_id, second=peer2_id, first_upload=peer1_upload, second_upload=peer2_upload)
