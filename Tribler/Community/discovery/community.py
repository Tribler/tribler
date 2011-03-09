from hashlib import sha1

from communitymetadata import CommunityMetadata
from conversion import DiscoveryBinaryConversion02
from database import DiscoveryDatabase
from payload import UserMetadataPayload, CommunityMetadataPayload
from usermetadata import UserMetadata

from Tribler.Core.dispersy.authentication import MemberAuthentication
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.destination import CommunityDestination
from Tribler.Core.dispersy.distribution import DirectDistribution, LastSyncDistribution, FullSyncDistribution
from Tribler.Core.dispersy.message import Message
from Tribler.Core.dispersy.resolution import PublicResolution
from Tribler.Core.dispersy.singleton import Singleton

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

class DiscoveryCommunity(Community, Singleton):
    """
    The DiscoveryCommunity is a fundamental Dispersy community that
    can be used to distribute and discover available users and
    communities.

    It has the following privileges:
    - user-metadata: sync user alias and description
    - community-metadata: sync community alias and description
    """
    def __init__(self, cid, master_key):
        super(DiscoveryCommunity, self).__init__(cid, master_key)

        # discovery storage
        self._database = DiscoveryDatabase.get_instance()

    def initiate_meta_messages(self):
        return [Message(self, u"user-metadata", MemberAuthentication(), PublicResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order", history_size=1), CommunityDestination(node_count=10), UserMetadataPayload(), self.check_user_metadata, self.on_user_metadata),
                # todo: create a MasterMemberAuthentication, or parameter to MemberAuthentication
                Message(self, u"community-metadata", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"in-order"), CommunityDestination(node_count=10), CommunityMetadataPayload(), self.check_community_metadata, self.on_community_metadata)]

    def initiate_conversions(self):
        return [DefaultConversion(self), DiscoveryBinaryConversion02(self)]

    def create_user_metadata(self, address, alias, comment, update_locally=True, store_and_forward=True):
        meta = self.get_meta_message(u"user-metadata")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(address, alias, comment))

        if update_locally:
            assert self._timeline.check(message)
            message.handle_callback([message])

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        return message

    def create_community_metadata(self, cid, alias, comment, update_locally=True, store_and_forward=True):
        meta = self.get_meta_message(u"community-metadata")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.claim_global_time(), meta.distribution.claim_sequence_number()),
                                 meta.destination.implement(),
                                 meta.payload.implement(cid, alias, comment))

        if update_locally:
            assert self._timeline.check(message)
            message.handle_callback([message])

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        return message

    def check_user_metadata(self, messages):
        for message in messages:
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay of proof")
            yield message

    def on_user_metadata(self, messages):
        with self._database as execute:
            for message in messages:
                payload = message.payload
                if __debug__: dprint("Alias:", payload.alias, "; Comment:", payload.comment, "; Address:", payload.address[0], ":", payload.address[1])
                execute(u"INSERT OR REPLACE INTO user_metadata(user, host, port, alias, comment) VALUES(?, ?, ?, ?, ?)",
                        (message.authentication.member.database_id, buffer(payload.address[0]), payload.address[1], payload.alias, payload.comment))

                # update from database if there is an instance
                user_metadata = UserMetadata.has_instance(message.authentication.member)
                if user_metadata:
                    user_metadata.update()

    def check_community_metadata(self, messages):
        for message in messages:
            if not self._timeline.check(message):
                yield DropMessage("TODO: implement delay of proof")
            yield message

    def on_community_metadata(self, messages):
        with self._database as execute:
            for message in messages:
                payload = message.payload
                if __debug__: dprint("Alias:", payload.alias, "; Comment:", payload.comment)
                execute(u"INSERT OR REPLACE INTO community_metadata(cid, alias, comment) VALUES(?, ?, ?)",
                        (buffer(payload.cid), payload.alias, payload.comment))

                # update from database if there is an instance
                community_metadata = CommunityMetadata.has_instance(payload.cid)
                if community_metadata:
                    community_metadata.update()
