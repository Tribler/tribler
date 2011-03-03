"""
The Distributed Permission System, or Dispersy, is a platform to simplify the design of distributed
communities.  At the heart of Dispersy lies a simple identity and message handling system where each
community and each user is uniquely and securely identified using elliptic curve cryptography.

Since we can not guarantee each member to be online all the time, messages that they created at one
point in time should be able to retain their meaning even when the member is off-line.  This can be
achieved by signing such messages and having them propagated though other nodes in the network.
Unfortunately, this increases the strain on these other nodes, which we try to alleviate using
specific message policies, which will be described below.

Following from this, we can easily package each message into one UDP packet to simplify
connectability problems since UDP packets are much easier to pass though NAT's and firewalls.

Earlier we hinted that messages can have different policies.  A message has the following four
different policies, and each policy defines how a specific part of the message should be handled.

 - Authentication defines if the message is signed, and if so, by how many members.

 - Resolution defines how the permission system should resolve conflicts between messages.

 - Distribution defines if the message is send once or if it should be gossipped around.  In the
   latter case, it can also define how many messages should be kept in the network.

 - Destination defines to whom the message should be send or gossipped.

To ensure that every node handles a messages in the same way, i.e. has the same policies associated
to each message, a message exists in two stages.  The meta-message and the implemented-message
stage.  Each message has one meta-message associated to it and tells us how the message is supposed
to be handled.  When a message is send or received an implementation is made from the meta-message
that contains information specifically for that message.  For example: a meta-message could have the
member-authentication-policy that tells us that the message must be signed by a member but only the
an implemented-message will have data and this signature.

A community can tweak the policies and how they behave by changing the parameters that the policies
supply.  Aside from the four policies, each meta-message also defines the community that it is part
of, the name it uses as an internal identifier, and the class that will contain the payload.
"""

from hashlib import sha1
from os.path import abspath

from authentication import NoAuthentication, MemberAuthentication, MultiMemberAuthentication
from bloomfilter import BloomFilter
from crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from destination import CommunityDestination, AddressDestination, MemberDestination, SubjectiveDestination, SimilarityDestination
from dispersydatabase import DispersyDatabase
from distribution import SyncDistribution, FullSyncDistribution, LastSyncDistribution, DirectDistribution
from member import PrivateMember, MasterMember
from message import Message
from message import DropPacket, DelayPacket, DelayPacketByMissingMember
from message import DropMessage, DelayMessage, DelayMessageBySequence, DelayMessageBySubjectiveSet, DelayMessageBySimilarity
from payload import AuthorizePayload, RevokePayload
from payload import MissingSequencePayload
from payload import SyncPayload
from payload import SignatureRequestPayload, SignatureResponsePayload
from payload import RoutingRequestPayload, RoutingResponsePayload
from payload import IdentityPayload, IdentityRequestPayload
from payload import SubjectiveSetPayload, SubjectiveSetRequestPayload
from payload import SimilarityRequestPayload, SimilarityPayload
from payload import DestroyCommunityPayload
from resolution import PublicResolution, LinearResolution
from singleton import Singleton
from trigger import TriggerCallback, TriggerPacket, TriggerMessage

if __debug__:
    from dprint import dprint
    from lencoder import log

class DummySocket(object):
    """
    A dummy socket class.

    When Dispersy starts it does not yet have a socket object, however, it may (under certain
    conditions) start sending packets anyway.

    To avoid problems we initialize the Dispersy socket to this dummy object that will do nothing
    but throw away all packets it is supposed to sent.
    """
    def send(address, data):
        if __debug__: dprint("Thrown away ", len(data), " bytes worth of outgoing data")

class Dispersy(Singleton):
    """
    The Dispersy class provides the interface to all Dispersy related commands, managing the in- and
    outgoing data for, possibly, multiple communities.
    """
    def __init__(self, rawserver, working_directory):
        """
        Initialize the Dispersy singleton instance.

        Currently we use the rawserver to schedule events.  This may change in the future to offload
        all data processing to a different thread.  The only mechanism used from the rawserver is
        the add_task method.

        @param rawserver: The rawserver BitTorrent instance.
        @type rawserver: Rawserver

        @param working_directory: The directory where all files should be stored.
        @type working_directory: unicode
        """
        # the raw server
        self._rawserver = rawserver

        # where we store all data
        self._working_directory = abspath(working_directory)

        # our data storage
        self._database = DispersyDatabase.get_instance(working_directory)

        # our external address
        try:
            ip, = self._database.execute(u"SELECT value FROM option WHERE key = 'my_external_ip' LIMIT 1").next()
            port, = self._database.execute(u"SELECT value FROM option WHERE key = 'my_external_port' LIMIT 1").next()
            self._my_external_address = (str(ip), port)
        except StopIteration:
            self._my_external_address = ("", -1)

        try:
            public_key, = self._database.execute(u"SELECT value FROM option WHERE key == 'my_public_key' LIMIT 1").next()
            public_key = str(public_key)
            private_key = None
        except StopIteration:
            # one of the keys was not found in the database, we need
            # to generate a new one
            ec = ec_generate_key(u"low")
            public_key = ec_to_public_bin(ec)
            private_key = ec_to_private_bin(ec)
            self._database.execute(u"INSERT INTO option VALUES('my_public_key', ?)", (buffer(public_key),))

        # all available communities.  cid:Community pairs.
        self._communities = {}

        # outgoing communication
        self._socket = DummySocket()

        # triggers for incoming messages
        self._triggers = []

        self._incoming_distribution_map = {FullSyncDistribution.Implementation:self._check_incoming_full_sync_distribution,
                                           LastSyncDistribution.Implementation:self._check_incoming_last_sync_distribution}


        # cleanup the database periodically
        self._rawserver.add_task(self._periodically_cleanup_database, 120.0)

        # statistics...
        self._total_send = 0
        self._total_received = 0
        if __debug__:
            self._rawserver.add_task(self._periodically_stats, 1.0)

    @property
    def working_directory(self):
        """
        The full directory path where all dispersy related files are stored.
        @rtype: unicode
        """
        return self._working_directory

    @property
    def socket(self):
        """
        The socket object used to send packets.
        @rtype: Object with a send(address, data) method
        """
        return self._socket

    @socket.setter
    def socket(self, socket):
        """
        Set a socket object.
        @param socket: The socket object.
        @type socket: Object with a send(address, data) method
        """
        self._socket = socket
        if self._my_external_address == ("", -1):
            self._my_external_address = socket.get_address()

    @property
    def rawserver(self):
        return self._rawserver

    @property
    def database(self):
        """
        The Dispersy database singleton.
        @rtype: DispersyDatabase
        """
        return self._database

    def initiate_meta_messages(self, community):
        """
        Create the meta messages that Dispersy uses.

        This method is called once for each community when it is created.  The resulting meta
        messages can be obtained by either community.get_meta_message(name) or
        community.get_meta_messages().

        Since these meta messages will be used along side the meta messages that each community
        provides, all message names are prefixed with 'dispersy-' to ensure that the names are
        unique.

        @param community: The community that will get the messages.
        @type community: Community

        @return: The new meta messages.
        @rtype: [Message]
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        return [Message(community, u"dispersy-routing-request", MemberAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), RoutingRequestPayload(), self.check_routing_request, self.on_routing_request),
                Message(community, u"dispersy-routing-response", MemberAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), RoutingResponsePayload(), self.check_routing_response, self.on_routing_response),
                Message(community, u"dispersy-identity", MemberAuthentication(encoding="bin"), PublicResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order", history_size=1), CommunityDestination(node_count=10), IdentityPayload(), self.check_identity, self.on_identity),
                Message(community, u"dispersy-identity-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), IdentityRequestPayload(), self.check_identity_request, self.on_identity_request),
                Message(community, u"dispersy-sync", MemberAuthentication(), PublicResolution(), DirectDistribution(), CommunityDestination(node_count=community.dispersy_sync_member_count), SyncPayload(), self.check_sync, self.on_sync),
                Message(community, u"dispersy-missing-sequence", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), MissingSequencePayload(), self.check_missing_sequence, self.on_missing_sequence),
                Message(community, u"dispersy-signature-request", NoAuthentication(), PublicResolution(), DirectDistribution(), MemberDestination(), SignatureRequestPayload(), self.check_signature_request, self.on_signature_request),
                Message(community, u"dispersy-signature-response", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), SignatureResponsePayload(), self.check_signature_response, self.on_signature_response),
                Message(community, u"dispersy-similarity", MemberAuthentication(), PublicResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order", history_size=1), CommunityDestination(node_count=10), SimilarityPayload(), self.check_similarity, self.on_similarity),
                Message(community, u"dispersy-similarity-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), SimilarityRequestPayload(), self.check_similarity_request, self.on_similarity_request),
                Message(community, u"dispersy-authorize", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"in-order"), CommunityDestination(node_count=10), AuthorizePayload(), self.check_authorize, self.on_authorize),
                Message(community, u"dispersy-revoke", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"in-order"), CommunityDestination(node_count=10), RevokePayload(), self.check_revoke, self.on_revoke),
                Message(community, u"dispersy-destroy-community", MemberAuthentication(), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order"), CommunityDestination(node_count=50), DestroyCommunityPayload(), self.check_destroy_community, self.on_destroy_community),
                Message(community, u"dispersy-subjective-set", MemberAuthentication(), PublicResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order", history_size=1), CommunityDestination(node_count=10), SubjectiveSetPayload(), self.check_subjective_set, self.on_subjective_set),
                Message(community, u"dispersy-subjective-set-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), SubjectiveSetRequestPayload(), self.check_subjective_set_request, self.on_subjective_set_request)]

    def add_community(self, community):
        """
        Add a community to the Dispersy instance.

        Each community must be known to Dispersy, otherwise an incoming message will not be able to
        be passed along to it's associated community.

        In general this method is called from the Community.__init__(...) method.

        @param community: The community that will be added.
        @type community: Community
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert not community.cid in self._communities
        self._communities[community.cid] = community

        # periodically send dispery-sync messages
        if community.dispersy_sync_initial_delay > 0.0 and community.dispersy_sync_interval > 0.0:
            self._rawserver.add_task(lambda: self._periodically_create_sync(community), community.dispersy_sync_initial_delay, "id:sync-" + community.cid)

        # periodically send dispery-routing-request messages
        if community.dispersy_routing_request_initial_delay > 0.0 and community.dispersy_routing_request_interval > 0.0:
            self._rawserver.add_task(lambda: self._periodically_create_routing_request(community), community.dispersy_routing_request_initial_delay, "id:routing-" + community.cid)

    def remove_community(self, community):
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert community.cid in self._communities
        self._rawserver.kill_tasks("id:sync-" + community.cid)
        self._rawserver.kill_tasks("id:routing-" + community.cid)
        del self._communities[community.cid]

    def get_community(self, cid):
        """
        Returns a community by its community id.

        The community id, or cid, is the binary representation of the public key of the master
        member for the community.

        @param cid: The community identifier.
        @type cid: string

        @warning: It is possible, however unlikely, that multiple communities will have the same
         cid.  This is currently not handled.
        """
        assert isinstance(cid, str)
        assert len(cid) == 20
        return self._communities[cid]

    def get_communities(self):
        """
        Returns a list with all known Community instances.
        """
        return self._communities.values()

    def _check_incoming_full_sync_distribution(self, address, message):
        """
        Ensure that we do not yet have the message and that, if sequence numbers are enabled, we are
        not missing any previous messages.

        This method is called when a message with the FullSyncDistribution policy is received.
        Duplicate messages result in the DropMessage exception.  And if enable_sequence_number is
        True, missing messages result in the DelayMessageBySequence exception.

        @param address: The address where we got this message from.  Will be ('', -1) when the
         message was created locally.
        @type address: (string, int)

        @param message: The message that is to be checked.
        @type message: Message.Implementation

        @raise DropMessage: When duplicate.
        @raise DelayMessageBySequence: When missing one or more previous messages.
        """
        assert isinstance(message, Message.Implementation)
        # check for duplicates based on global_time
        try:
            self._database.execute(
                u"""SELECT 1
                    FROM sync
                    JOIN reference_user_sync ON reference_user_sync.sync = sync.id
                    WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ? AND sync.global_time = ?
                    LIMIT 1""",
                (message.community.database_id,
                 message.authentication.member.database_id,
                 message.database_id,
                 message.distribution.global_time)).next()

        except StopIteration:
            pass

        else:
            # we have the previous message (drop)
            raise DropMessage("duplicate message")

        if message.distribution.enable_sequence_number:
            try:
                sequence_number, = self._database.execute(
                    u"""SELECT sync.distribution_sequence
                        FROM sync
                        JOIN reference_user_sync ON reference_user_sync.sync = sync.id
                        WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?
                        ORDER BY sync.distribution_sequence DESC
                        LIMIT 1""",
                    (message.community.database_id,
                     message.authentication.member.database_id,
                     message.database_id)).next()
            except StopIteration:
                sequence_number = 0

            if sequence_number >= message.distribution.sequence_number:
                # we already have this message (drop)
                raise DropMessage("duplicate message")

            elif sequence_number + 1 == message.distribution.sequence_number:
                # we have the previous message (process)
                pass

            else:
                #  we do not have the previous message (delay and request)
                raise DelayMessageBySequence(message, sequence_number+1, message.distribution.sequence_number-1)

    def _check_incoming_last_sync_distribution(self, address, message):
        """
        Ensure that we do not yet have the message and that, if sequence numbers are enabled, we are
        not missing any previous messages.

        This method is called when a message with the LastSyncDistribution policy is received.
        Duplicate messages result in the DropMessage exception.  And if enable_sequence_number is
        True, missing messages result in the DelayMessageBySequence exception.

        @param address: The address where we got this message from.  Will be ('', -1) when the
         message was created locally.
        @type address: (string, int)

        @param message: The message that is to be checked.
        @type message: Message.Implementation

        @raise DropMessage: When duplicate.
        @raise DelayMessageBySequence: When missing one or more previous messages.
        """
        assert isinstance(message, Message.Implementation)
        # check for duplicates based on global_time
        times = [x for x, in self._database.execute(u"""SELECT sync.global_time
                                                        FROM sync
                                                        JOIN reference_user_sync ON (reference_user_sync.sync = sync.id)
                                                        WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?
                                                        LIMIT ?""",
                                                    (message.community.database_id,
                                                     message.authentication.member.database_id,
                                                     message.database_id,
                                                     message.distribution.history_size))]

        if message.distribution.global_time in times:
            raise DropMessage("duplicate message")

        if len(times) >= message.distribution.history_size and min(times) > message.distribution.global_time:
            # the sender of this message is apparently missing one or more messages
            if message.distribution.history_size == 1:
                # we can sent back the one message that proves that the received message is old
                try:
                    packet, = self._database.execute(u"""SELECT sync.packet
                                                         FROM sync
                                                         JOIN reference_user_sync ON (reference_user_sync.sync = sync.id)
                                                         WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ? AND sync.global_time = ?""",
                                                     (message.community.database_id,
                                                      message.authentication.member.database_id,
                                                      message.database_id,
                                                      times[0])).next()
                    packet = str(packet)
                except StopIteration:
                    # should not occur, as we just selected the associated global_time in the
                    # previous query... but you never know
                    pass
                else:
                    if __debug__: dprint("prooving ", len(packet), " bytes from _check_incoming_last_sync_distribution to ", address[0], ":", address[1])
                    self._send([address], [packet])

            elif message.distribution.enable_sequence_number:
                # we limit the response by byte_limit bytes
                byte_limit = self._total_send + message.community.dispersy_sync_response_limit

                # we can sent back everything higher than message.distribution.global_time
                for packet in self._database.execute(u"""SELECT sync.packet
                                                         FROM sync
                                                         JOIN reference_user_sync ON (reference_user_sync.sync = sync.id)
                                                         WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ? AND sync.global_time > ?
                                                         ORDER BY sync.global_time ASC""",
                                                     (message.community.database_id,
                                                      message.authentication.member.database_id,
                                                      message.database_id,
                                                      message.distribution.global_time)):
                    packet = str(packet)

                    if __debug__: dprint("prooving ", len(packet), " bytes from _check_incoming_last_sync_distribution to ", address[0], ":", address[1])
                    self._send([address], [packet])

                    if self._total_send > byte_limit:
                        if __debug__: dprint("bandwidth throttle")
                        break

            raise DropMessage("old message")

        if message.distribution.enable_sequence_number:
            try:
                sequence_number, = self._database.execute(
                    u"""SELECT sync.distribution_sequence
                        FROM sync
                        JOIN reference_user_sync ON (reference_user_sync.sync = sync.id)
                        WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?
                        ORDER BY sync.distribution_sequence DESC
                        LIMIT 1""",
                    (message.community.database_id,
                     message.authentication.member.database_id,
                     message.database_id)).next()
            except StopIteration:
                sequence_number = 0

            if sequence_number >= message.distribution.sequence_number:
                # we already have this message (drop)
                raise DropMessage("duplicate message")

            elif sequence_number + 1 == message.distribution.sequence_number:
                # we have the previous message (process)
                pass

            else:
                #  we do not have the previous message (delay and request)
                raise DelayMessageBySequence(message, max(sequence_number+1, message.distribution.sequence_number-message.distribution.history_size), message.distribution.sequence_number-1)

    def _check_incoming_OTHER_distribution(self, address, message):
        """
        Does not do anything.

        This method is called when a message with the DirectDistribution policy is received.  This
        message is not stored and hence we will not be able to see if we have already received this
        message.

        Receiving the same DirectDistribution multiple times indicates that the sending -wanted- to
        send this message multiple times.

        @param address: The address where we got this message from.  Will be ('', -1) when the
         message was created locally.
        @type address: (string, int)

        @param message: Ignored.
        @type message: Message.Implementation assert isinstance(message, Message.Implementation)
        """
        assert isinstance(message, Message.Implementation)

    def on_incoming_packets(self, packets):
        """
        Process UDP packets.

        This method is called to process one or more UDP packets.  This occurs when new packets are
        received, to attempt to process previously delayed packets, or when a user explicitly
        creates a packet to process.  The last option should only occur for debugging purposes.

        Each packet is processed in the following way:

         1. The associated community is retrieved.  Failure results in packet drop.

         2. The associated converion is retrieved.  Failure results in packet drop, this probably
            indicates that we are running outdated software.

         3. The packet is decoded into a Message.Implementation instance.  Failure results in either
            a packet drop or a packet delay.

         4. The on_incoming_message(...) method is called.

        The packets are given as a sequence of (address, packet) tuples.  Where each address is a
        (string, int) and each packet a string.

        @param packets: The sequence of packets.
        @type packets: [(address, packet)]
        """
        assert isinstance(packets, (tuple, list))
        assert len(packets) > 0
        assert not filter(lambda x: not len(x) == 2, packets)

        for address, packet in packets:
            assert isinstance(address, tuple)
            assert isinstance(address[0], str)
            assert isinstance(address[1], int)
            assert isinstance(packet, str)

            if __debug__: dprint(address[0], ":", address[1], ": ", len(packet), " bytes were received")
            self._total_received += len(packet)

            # is it from an external source
            if not self._is_valid_external_address(address):
                if __debug__: dprint("drop a ", len(packet), " byte packet (received from an invalid source) from ", address[0], ":", address[1])
                continue

            # find associated community
            try:
                community = self.get_community(packet[:20])
            except KeyError:
                if __debug__: dprint("drop a ", len(packet), " byte packet (received packet for unknown community) from ", address[0], ":", address[1])
                continue

            # find associated conversion
            try:
                conversion = community.get_conversion(packet[:22])
            except KeyError:
                if __debug__: dprint("drop a ", len(packet), " byte packet (received packet for unknown conversion) from ", address[0], ":", address[1])
                continue

            try:
                # converty binary date to internal Message
                message = conversion.decode_message(packet)

            except DropPacket as exception:
                if __debug__: dprint(address[0], ":", address[1], ": drop a ", len(packet), " byte packet (", exception, ")", level="warning")
                if __debug__: log("dispersy.log", "drop-packet", address=address, packet=packet, exception=str(exception))

            except DelayPacket as delay:
                if __debug__: dprint(address[0], ":", address[1], ": delay a ", len(packet), " byte packet (", delay, ")")
                trigger = TriggerPacket(delay.pattern, self.on_incoming_packets, [(address, packet)])
                self._triggers.append(trigger)
                self._rawserver.add_task(trigger.on_timeout, 10.0)
                self._send([address], [delay.request_packet])
                if __debug__: log("dispersy.log", "delay-packet", address=address, packet=packet, pattern=delay.pattern)

            else:
                # update routing table.  We know that some peer (not necessarily
                # message.authentication.member) exists at this address.
                self._database.execute(u"UPDATE routing SET incoming_time = DATETIME() WHERE community = ? AND host = ? AND port = ?",
                                       (message.community.database_id, unicode(address[0]), address[1]))
                if self._database.changes == 0:
                    self._database.execute(u"INSERT INTO routing(community, host, port, incoming_time, outgoing_time) VALUES(?, ?, ?, DATETIME(), '2010-01-01 00:00:00')",
                                           (message.community.database_id, unicode(address[0]), address[1]))

                # handle the message
                self.on_incoming_message(address, message)

    def on_incoming_message(self, address, message):
        """
        Process one dispersy message.

        This method is called to process one dispersy message.  This occurs when new message is
        received, to attempt to process previously delayed message, or when a user explicitly
        creates a message to process.  The last option should only occur for debugging purposes.

        Each message is processed in the following way:

         1. When the member is tagged with 'drop' the message is dropped.

         2. The distribution policy is checked.  Failure occurs when this message is already
            processed or when the message is to old.

         3. The community is allowed to process the message though the on_message method.  Note that
            even though the member may be tagged with 'ignore', these callbacks will take place.

         4. If the message uses the SyncDistribution policy is may be stored in the database.

         5. The message may match one of the existing Triggers causing a callback or a delayed
            packet or message to be processed.

        @param address: The address where we got this message from.  Will be ('', -1) when the
         message was created locally.
        @type address: (string, int)

        @param message: The message.
        @type message: Message.Implementation
        """
        if __debug__: dprint("incoming ", message.name, " (", len(message.packet), " bytes) from ", address[0], ":", address[1])
        try:
            # drop if this is a blacklisted member
            if isinstance(message.authentication, (MemberAuthentication.Implementation, MultiMemberAuthentication.Implementation)) and message.authentication.member.must_drop:
                # todo: we currently do not add this message in the bloomfilter, hence we will
                # continually receive this packet.
                raise DropMessage("Packets from this member are explicitly dropped")

            # filter messages based on distribution (usually duplicate or old messages)
            self._incoming_distribution_map.get(type(message.distribution), self._check_incoming_OTHER_distribution)(address, message)

            # allow community code to test the message
            message.check_callback(address, message)

        except DropMessage as exception:
            if __debug__: dprint(address[0], ":", address[1], ": drop a ", len(message.packet), " byte message (", exception, ")", level="warning")
            if __debug__: log("dispersy.log", "drop-message", address=address, message=message.name, packet=message.packet, exception=str(exception))

        except DelayMessage as delay:
            if __debug__: dprint(address[0], ":", address[1], ": delay a ", len(message.packet), " byte message (", delay, ")")
            trigger = TriggerMessage(delay.pattern, self.on_incoming_message, address, message)
            self._triggers.append(trigger)
            self._rawserver.add_task(trigger.on_timeout, 10.0)
            self._send([address], [delay.request_packet])

        else:
            # sync messages need to be stored (so they can be synced later)
            if isinstance(message.distribution, SyncDistribution.Implementation):
                self._sync_distribution_store(message)

            # allow community code to handle the message
            message.handle_callback(address, message)

            if __debug__: log("dispersy.log", "handled", address=address, packet=message.packet, message=message.name)

            # this message may 'trigger' a previously delayed message
            self._triggers = [trigger for trigger in self._triggers if trigger.on_message(address, message)]

    def _sync_distribution_store(self, message):
        """
        Store a message in the database.

        Messages with the Last- or Full-SyncDistribution policies need to be stored in the database
        to allow them to propagate to other members.

        Messages with the LastSyncDistribution policy may also cause an older message to be removed
        from the database.

        Messages created by a member that we have marked with must_store will also be stored in the
        database, and hence forwarded to others.

        @param message: The unstored message with the SyncDistribution policy.
        @type message: Message.Implementation
        """
        assert isinstance(message.distribution, SyncDistribution.Implementation)
        assert isinstance(message.authentication, (MemberAuthentication.Implementation, MultiMemberAuthentication.Implementation)), message.authentication
        assert message.authentication.is_signed
        # the signature must be set
        assert not message.packet[-10:] == "\x00" * 10, message.packet[-10:].encode("HEX")

        # we do not store a message when it uses SubjectiveDestination and it is not in our set
        if isinstance(message.destination, SubjectiveDestination.Implementation) and not message.destination.is_valid:
            # however, ignore the SimilarityDestination when we are forced so store this message
            if not message.authentication.member.must_store:
                if __debug__: dprint("Not storing message")
                return

        # we do not store a message when it uses SimilarityDestination and it is not similar
        if isinstance(message.destination, SimilarityDestination.Implementation) and not message.destination.is_similar:
            # however, ignore the SimilarityDestination when we are forced so store this message
            if not message.authentication.member.must_store:
                if __debug__: dprint("Not storing message.  bic:", message.destination.bic_occurrence, "  threshold:", message.destination.threshold)
                return

        # sync bloomfilter
        message.community.get_bloom_filter(message.distribution.global_time).add(message.packet)

        with self._database as execute:

            # delete packet if there are to many stored
            if isinstance(message.distribution, LastSyncDistribution.Implementation):
                for id_, in execute(u"""SELECT sync.id
                                        FROM sync
                                        JOIN reference_user_sync ON (reference_user_sync.sync = sync.id)
                                        WHERE sync.community = ? AND reference_user_sync.user = ? AND sync.name = ?
                                        ORDER BY sync.global_time DESC
                                        LIMIT 100 OFFSET ?""",
                                    (message.community.database_id,
                                     message.authentication.member.database_id,
                                     message.database_id,
                                     message.distribution.history_size - 1)):
                    execute(u"DELETE FROM reference_user_sync WHERE user = ? AND sync = ?", (message.authentication.member.database_id, id_))
                    execute(u"DELETE FROM sync WHERE id = ?", (id_,))

            # add packet to database
            execute(u"INSERT INTO sync (community, name, global_time, synchronization_direction, distribution_sequence, destination_cluster, packet) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (message.community.database_id,
                     message.database_id,
                     message.distribution.global_time,
                     message.distribution.synchronization_direction_id,
                     isinstance(message.distribution, FullSyncDistribution.Implementation) and message.distribution.sequence_number or 0,
                     # isinstance(message.distribution, LastSyncDistribution.Implementation) and message.distribution.cluster or 0,
                     isinstance(message.destination, SimilarityDestination.Implementation) and message.destination.cluster or 0,
                     buffer(message.packet)))

            # ensure that we can reference this packet
            message.packet_id = self._database.last_insert_rowid

            # link one or more users to this packet
            # todo: add more when this is MultiMemberAuthentication
            execute(u"INSERT INTO reference_user_sync (user, sync) VALUES (?, ?)",
                    (message.authentication.member.database_id,
                     message.packet_id))

    def _select_routing_addresses(self, community_id, address_count, diff_range, age_range):
        assert isinstance(community_id, (int, long))
        assert community_id >= 0
        assert isinstance(address_count, int)
        assert address_count > 0
        assert isinstance(diff_range, tuple)
        assert len(diff_range) == 2
        assert isinstance(diff_range[0], float)
        assert isinstance(diff_range[1], float)
        assert 0.0 <= diff_range[0] <= diff_range[1]
        assert isinstance(age_range, tuple)
        assert len(age_range) == 2
        assert isinstance(age_range[0], float)
        assert isinstance(age_range[1], float)
        assert 0.0 <= age_range[0] <= age_range[1]

        # todo: we can remove the returning diff and age from the query since it is not used
        # (especially in the 2nd query)

        # the theory behind the address selection is:
        # a. we want to keep contact with those who are online, hence we send messages to those that
        #    have a small diff.
        # b. we want to get connections to those that have been away for some time, hence we send
        #    messages to those that have a high age.
        sql = u"""SELECT host, port
                  FROM routing
                  WHERE community = ? AND (ABS(STRFTIME('%s', outgoing_time) - STRFTIME('%s', incoming_time)) BETWEEN ? AND ?
                                           OR STRFTIME('%s', DATETIME()) - STRFTIME('%s', incoming_time) BETWEEN ? AND ?)
                  ORDER BY RANDOM()
                  LIMIT ?"""
        addresses = set((str(host), port)
                        for host, port
                        in self._database.execute(sql, (community_id, diff_range[0], diff_range[1], age_range[0], age_range[1], address_count)))

        if len(addresses) >= address_count:
            return addresses

        # we will try a few addresses from external sources (3rd party).  note that selecting these
        # will add a value to the outgoing_time column because we will sent something to this
        # address.
        sql = u"""SELECT host, port
                  FROM routing
                  WHERE community = ? AND STRFTIME('%s', DATETIME()) - STRFTIME('%s', external_time) BETWEEN ? AND ?
                  ORDER BY RANDOM()
                  LIMIT ?"""
        addresses.update([(str(host), port)
                          for host, port
                          in self._database.execute(sql, (community_id, age_range[0], age_range[1], address_count - len(addresses)))])

        if len(addresses) >= address_count:
            return addresses

        # at this point we do not have sufficient nodes that were online recently.  as an
        # alternative we will add the addresses of dispersy routers that should always be online
        sql = u"""SELECT host, port
                  FROM routing
                  WHERE community = 0
                  ORDER BY RANDOM()
                  LIMIT ?"""
        addresses.update([(str(host), port)
                          for host, port
                          in self._database.execute(sql, (address_count - len(addresses),))])

        if len(addresses) >= address_count:
            return addresses

        # fallback to just picking random addresses within this community.  unfortunately it is
        # likely that the addresses will contain nodes that are offline
        sql = u"""SELECT host, port
                  FROM routing
                  WHERE community = ?
                  ORDER BY RANDOM()
                  LIMIT ?"""
        addresses.update([(str(host), port)
                          for host, port
                          in self._database.execute(sql, (community_id, address_count - len(addresses)))])

        # return what we have
        return addresses

    def store_and_forward(self, messages):
        """
        Queue a sequence of messages to be sent to other members.

        First all messages that use the SyncDistribution policy are stored to the database to allow
        them to propagate when a dispersy-sync message is received.

        Second all messages are sent depending on their destination policy:

         - AddressDestination causes a message to be sent to the addresses in
           message.destination.addresses.

         - MemberDestination causes a message to be sent to the address associated to the member in
           message.destination.members.

         - CommunityDestination causes a message to be sent to one or more addresses to be picked
           from the database routing table.

         - SubjectiveDestination is currently handled in the same way as CommunityDestination.
           Obviously this needs to be modified.

         - SimilarityDestination is currently handled in the same way as CommunityDestination.
           Obviously this needs to be modified.

        @param messages: A sequence with one or more messages.
        @type messages: [Message.Implementation]

        @todo: Ensure messages with the SimilarityDestination policy are only sent to similar
         members.
        """
        if __debug__:
            from message import Message
        assert isinstance(messages, (tuple, list))
        assert len(messages) > 0
        assert not filter(lambda x: not isinstance(x, Message.Implementation), messages)

        for message in messages:

            # Store
            if isinstance(message.distribution, SyncDistribution.Implementation):
                self._sync_distribution_store(message)

            # Forward
            if isinstance(message.destination, (CommunityDestination.Implementation, SubjectiveDestination.Implementation, SimilarityDestination.Implementation)):
                addresses = self._select_routing_addresses(message.community.database_id,
                                                           message.destination.node_count,
                                                           (0.0, 30.0),
                                                           (120.0, 300.0))
                if __debug__: dprint("outgoing ", message.name, " (", len(message.packet), " bytes) to ", ", ".join("{0[0]}:{0[1]}".format(address) for address in addresses))
                self._send(addresses, [message.packet])

            elif isinstance(message.destination, AddressDestination.Implementation):
                if __debug__: dprint("outgoing ", message.name, " (", len(message.packet), " bytes) to ", ", ".join("{0[0]}:{0[1]}".format(address) for address in message.destination.addresses))
                self._send(message.destination.addresses, [message.packet])

            elif isinstance(message.destination, MemberDestination.Implementation):
                if __debug__: dprint("outgoing ", message.name, " (", len(message.packet), " bytes) to ", ", ".join("{0[0]}:{0[1]}".format(member.address) for member in message.destination.members))
                self._send([member.address for member in message.destination.members], [message.packet])

            else:
                raise NotImplementedError(message.destination)

    def _send(self, addresses, packets):
        """
        Send one or more packets to one or more addresses.

        To clarify: every packet is sent to every address.

        @param addresses: A sequence with one or more addresses.
        @type addresses: [(string, int)]

        @patam packets: A sequence with one or more packets.
        @type packets: string
        """
        assert isinstance(addresses, (tuple, list, set)), type(addresses)
        assert isinstance(packets, (tuple, list, set)), type(packets)

        if __debug__:
            if not addresses:
                dprint("no addresses given (wanted to send ", len(packets), " packets)", level="error")
            if not packets:
                dprint("no packets given (wanted to send to ", len(addresses), " addresses)", level="error")

        # update statistics
        self._total_send += len(addresses) * sum([len(packet) for packet in packets])

        # update routing table and send packets
        with self._database as execute:
            for address in addresses:
                assert isinstance(address, tuple)
                assert isinstance(address[0], str)
                assert isinstance(address[1], int)

                if not self._is_valid_external_address(address):
                    # this is a programming bug.  apparently an invalid address is being used
                    if __debug__: dprint("aborted sending a ", len(packet), " byte packet (invalid external address) to ", address[0], ":", address[1], level="error")
                    continue

                for packet in packets:
                    assert isinstance(packet, str)
                    if __debug__: dprint(len(packet), " bytes to ", address[0], ":", address[1])
                    self._socket.send(address, packet)
                execute(u"UPDATE routing SET outgoing_time = DATETIME() WHERE host = ? AND port = ?", (unicode(address[0]), address[1]))

    def await_message(self, footprint, response_func, response_args=(), timeout=10.0, max_responses=1):
        """
        Register a callback to occur when a message with a specific footprint is received, or after
        a certain timeout occurs.

        When the footprint of an incoming message matches the regular expression footprint it is
        passed to both the response_func (or several if the message matches multiple footprints) and
        its regular message handler.  First the regular message handler is called, followed by
        response_func.

        The response_func is called each time when a message is received that matches the expression
        footprint or after timeout seconds when fewer than max_responses incoming messages have
        matched footprint.  The first argument is the sender address (or ('', -1) on a timeout), the
        second argument is the incoming message, following this are any optional arguments in
        response_args.

        Response_args is a tuple that can be given optional values that are included in the call to
        response_func, following the address and message arguments.

        When the timeout expires and less than max_responses messages have matched the expression
        footprint, the response_func is called one last time.  The address and the message will be
        sent to ('', -1) None, respectively and response_args will be appended as normal.  Once a
        timeout callback is given no further callbacks will be made.

        The Trigger that is created will be removed either on timeout or when max_responses messages
        have matched the expression footprint.

        The footprint matching is done as follows: for each incoming message a message footprint is
        made.  This footprint is a string that contains a summary of all the message properties.
        Such as 'MemberAuthentication:ABCDE' and 'FullSyncDistribution:102'.

        @param footprint: The regular expression to match all incoming messages.
        @type footprint: string

        @param response_func: The method called when a message matches footprint.
        @type response_func: callable

        @param response_args: Optional arguments to added when calling response_func.
        @type response_args: tuple

        @param timeout: Number of seconds until a timeout occurs.
        @type timeout: float

        @param max_responses: Maximal number of messages to match until the Trigger is removed.
        @type max_responses: int
        """
        assert isinstance(footprint, str)
        assert hasattr(response_func, "__call__")
        assert isinstance(response_args, tuple)
        assert isinstance(timeout, float)
        assert timeout > 0.0
        assert isinstance(max_responses, (int, long))
        assert max_responses > 0

        trigger = TriggerCallback(footprint, response_func, response_args, max_responses)
        self._triggers.append(trigger)
        self._rawserver.add_task(trigger.on_timeout, timeout)

    def create_routing_request(self, community, address, routes, response_func=None, response_args=(), timeout=10.0, max_responses=1, store_and_forward=True):
        """
        Create a dispersy-routing-request message.

        The dispersy-routing-request and -response messages are used to keep track of the address
        where a member can be found.  It is also used to check if the member is still alive because
        it triggers a response message.  Finally, it is used to spread addresses of other members
        aswell.

        The optional response_func is used to obtain a callback for this specific request.  The
        parameters response_func, response_args, timeout, and max_responses are all related to this
        callback and are explained in the await_message method.

        @param community: The community for wich the dispersy-routing-request message will be
         created.
        @type community: Community

        @param address: The destination address.
        @type address: (string, int)

        @param response_func: The method called when a message matches footprint.
        @type response_func: callable

        @param response_args: Optional arguments to added when calling response_func.
        @type response_args: tuple

        @param timeout: Number of seconds until a timeout occurs.
        @type timeout: float

        @param max_responses: Maximal number of messages to match until the Trigger is removed.
        @type max_responses: int

        @param store_and_forward: When True the created messages are stored (as defined by the
         message distribution policy) in the local Dispersy database and the messages are forewarded
         to other peers (as defined by the message destination policy).  This parameter should
         (almost always) be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store_and_forward: bool
        """
        assert isinstance(community, Community)
        assert isinstance(address, tuple)
        assert isinstance(address[0], str)
        assert isinstance(address[1], int)
        assert isinstance(routes, (tuple, list))
        assert not filter(lambda route: not isinstance(route, tuple), routes)
        assert not filter(lambda route: not len(route) == 2, routes)
        assert not filter(lambda route: not isinstance(route[0], tuple), routes)
        assert not filter(lambda route: not len(route[0]) == 2, routes)
        assert not filter(lambda route: not isinstance(route[0][0], str), routes)
        assert not filter(lambda route: not isinstance(route[0][1], (int, long)), routes)
        assert not filter(lambda route: not isinstance(route[1], float), routes)
        assert hasattr(response_func, "__call__")
        assert isinstance(response_args, tuple)
        assert isinstance(timeout, float)
        assert timeout > 0.0
        assert isinstance(max_responses, (int, long))
        assert max_responses > 0
        assert isinstance(store_and_forward, bool)
        meta = community.get_meta_message(u"dispersy-routing-request")
        request = meta.implement(meta.authentication.implement(community.my_member),
                                 meta.distribution.implement(meta.community._timeline.global_time),
                                 meta.destination.implement(address),
                                 meta.payload.implement(self._my_external_address, address, community.get_conversion(), routes))

        if store_and_forward:
            self.store_and_forward([request])

        if response_func:
            meta = community.get_meta_message(u"dispersy-routing-response")
            footprint = meta.generate_footprint(payload=(sha1(request.packet).digest(),))
            self.await_message(footprint, response_func, response_args, timeout, max_responses)

        return request

    def check_routing_request(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

    def _is_valid_external_address(self, address):
        # if address[0] in ("0.0.0.0", "127.0.0.1"):
        #     return False

        # if address[0].endswith(".255"):
        #     return False

        return True

    def _update_routes_from_external_source(self, community, routes):
        assert isinstance(routes, (tuple, list))
        assert not filter(lambda x: not isinstance(x, tuple), routes)
        assert not filter(lambda x: not len(x) == 2, routes)
        assert not filter(lambda x: not isinstance(x[0], tuple), routes), "(host, ip) tuple"
        assert not filter(lambda x: not isinstance(x[1], float), routes), "age in seconds"

        with self._database as execute:
            for address, age in routes:
                if self._is_valid_external_address(address):
                    if __debug__: dprint("update routing table for ", address[0], ":", address[1])

                    # TODO: we are overwriting our own age... first check that if we have this
                    # address, that our age is higher before updating
                    age = u"-%d seconds" % age
                    execute(u"UPDATE routing SET external_time = DATETIME('now', ?) WHERE community = ? AND host = ? AND port = ?",
                            (age, community.database_id, unicode(address[0]), address[1]))
                    if self._database.changes == 0:
                        execute(u"INSERT INTO routing(community, host, port, external_time) VALUES(?, ?, ?, DATETIME('now', ?))",
                                (community.database_id, unicode(address[0]), address[1], age))

                elif __debug__:
                    dprint("dropping invalid route ", address[0], ":", address[1], level="warning")

    def on_routing_request(self, address, message):
        """
        We received a dispersy-routing-request message.

        This message contains the external address that the sender believes it has
        (message.payload.source_address), and our external address
        (message.payload.destination_address).

        We should send a dispersy-routing-response message back.  Allowing us to inform them of
        their external address.

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-sync message.
        @type message: Message.Implementation
        """
        if __debug__:
            from message import Message
        assert message.name == u"dispersy-routing-request"
        assert isinstance(message, Message.Implementation)
        if __debug__: dprint(message)

        if __debug__: dprint("Our external address may be: ", message.payload.destination_address)
        self._my_external_address = message.payload.destination_address

        # update or insert the member who sent the request
        # self._database.execute(u"UPDATE user SET user = ? WHERE community = ? AND host = ? AND port = ?",
        #                        (message.authentication.member.database_id, message.community.database_id, unicode(address[0]), address[1]))

        # add routes in our routing table
        self._update_routes_from_external_source(message.community, message.payload.routes)

        # send response
        minimal_age, maximal_age = message.community.dispersy_routing_age_range
        sql = u"""SELECT host, port, STRFTIME('%s', DATETIME()) - STRFTIME('%s', incoming_time) AS age
                  FROM routing
                  WHERE community = ? AND age BETWEEN ? AND ?
                  ORDER BY age
                  LIMIT 30"""
        routes = [((str(host), port), float(age)) for host, port, age in self._database.execute(sql, (message.community.database_id, minimal_age, maximal_age))]

        meta = message.community.get_meta_message(u"dispersy-routing-response")
        response = meta.implement(meta.authentication.implement(meta.community.my_member),
                                  meta.distribution.implement(meta.community._timeline.global_time),
                                  meta.destination.implement(address),
                                  meta.payload.implement(sha1(message.packet).digest(), self._my_external_address, address, meta.community.get_conversion().version, routes))
        self.store_and_forward([response])

    def check_routing_response(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

    def on_routing_response(self, address, message):
        """
        We received a dispersy-routing-response message.

        This message contains the external address that the sender believes it has
        (message.payload.source_address), and our external address
        (message.payload.destination_address).

        We need to be carefull with this message.  It is very much possible that the
        destination_address is invalid.  Furthermore, currently anyone is free to send this message,
        making it very easy to generate any number of members to override simple security schemes
        that use counting.

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-routing-response message.
        @type message: Message.Implementation
        """
        if __debug__:
            from message import Message
        assert message.name == u"dispersy-routing-response"
        assert isinstance(message, Message.Implementation)
        if __debug__: dprint(message)

        if __debug__: dprint("Our external address may be: ", message.payload.destination_address)
        self._my_external_address = message.payload.destination_address

        # self._database.execute(u"UPDATE user SET user = ? WHERE community = ? AND host = ? AND port = ?",
        #                        (message.authentication.member.database_id, message.community.database_id, unicode(address[0]), address[1]))

        # add routes in our routing table
        self._update_routes_from_external_source(message.community, message.payload.routes)

    def create_identity(self, community, store_and_forward=True):
        """
        Create a dispersy-identity message.

        The dispersy-identity message contains information on community.my_member.  Such as your
        public key and the IP address and port where you are reachable.

        Typically, every member is represented my the most recent dispersy-identity message that she
        created and provided to the network.  Generally one such message is created whenever a
        member joins an existing community for the first time, or when she creates a new community.

        @param community: The community for wich the dispersy-identity message will be created.
        @type community: Community

        @param store_and_forward: When True the created messages are stored (as defined by the
         message distribution policy) in the local Dispersy database and the messages are forewarded
         to other peers (as defined by the message destination policy).  This parameter should
         (almost always) be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store_and_forward: bool
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(store_and_forward, bool)
        meta = community.get_meta_message(u"dispersy-identity")
        message = meta.implement(meta.authentication.implement(community.my_member),
                                 meta.distribution.implement(community._timeline.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(self._my_external_address))
        if store_and_forward:
            self.store_and_forward([message])

        return message

    def check_identity(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

    def on_identity(self, address, message):
        """
        We received a dispersy-identity message.

        @see: create_identity

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-identity message.
        @type message: Message.Implementation
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message.Implementation)
        assert message.name == u"dispersy-identity"
        if __debug__: dprint(message)
        host, port = message.payload.address
        # TODO: we should drop messages that contain invalid addresses... or at the very least we
        # should ignore the address part.
        with self._database as execute:
            # execute(u"INSERT OR IGNORE INTO routing(community, host, port, incoming_time, outgoing_time) VALUES(?, ?, ?, DATETIME(), '2010-01-01 00:00:00')", (message.community.database_id, unicode(host), port))
            execute(u"UPDATE user SET host = ?, port = ? WHERE id = ?", (unicode(host), port, message.authentication.member.database_id))
            # execute(u"UPDATE identity SET packet = ? WHERE user = ? AND community = ?", (buffer(message.packet), message.authentication.member.database_id, message.community.database_id))
            # if self._database.changes == 0:
            #     execute(u"INSERT INTO identity(user, community, packet) VALUES(?, ?, ?)", (message.authentication.member.database_id, message.community.database_id, buffer(message.packet)))
        message.authentication.member.update()

    def create_identity_request(self, community, mid, address, store_and_forward=True):
        """
        Create a dispersy-identity-request message.

        To verify a message signature we need the corresponding public key from the member who made
        the signature.  When we are missing a public key, we can request a dispersy-identity message
        which contains this public key.

        The missing member is identified by the sha1 digest over the member key.  This mid can
        indicate multiple members, hence the dispersy-identity-response will contain one or more
        public keys.

        Most often we will need to request a dispersy-identity when we receive a message containing
        an, to us, unknown mid.  Hence, sending the request to the address where we got that message
        from is usually most effective.

        @see: create_identity

        @param community: The community for wich the dispersy-identity message will be created.
        @type community: Community

        @param mid: The 20 byte identifier for the member.
        @type mid: string

        @param address: The address to send the request to.
        @type address: (string, int)

        @param store_and_forward: When True the created messages are stored (as defined by the
         message distribution policy) in the local Dispersy database and the messages are forewarded
         to other peers (as defined by the message destination policy).  This parameter should
         (almost always) be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store_and_forward: bool
        """
        meta = community.get_meta_message(u"dispersy-identity-request")
        message = meta.implement(meta.authentication.implement(),
                                 meta.distribution.implement(),
                                 meta.destination.implement(address),
                                 meta.payload.implement(mid))
        if store_and_forward:
            self.store_and_forward([message])

        return message

    def check_identity_request(self, address, message):
        # we can not timeline.check this message because it uses the NoAuthentication policy
        pass

    def on_identity_request(self, address, message):
        """
        We received a dispersy-identity-request message.

        The message contains the mid of a member.  The sender would like to obtain one or more
        associated dispersy-identity messages.

        @see: create_identity_request

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-identity message.
        @type message: Message.Implementation
        """
        assert message.name == u"dispersy-identity-request"
        if __debug__: dprint(message)

        meta = message.community.get_meta_message(u"dispersy-identity")

        # todo: we are assuming here that no more than 10 members have the same sha1 digest.
        # sql = u"SELECT identity.packet FROM identity JOIN user ON user.id = identity.user WHERE identity.community = ? AND user.mid = ? LIMIT 10"
        sql = u"""SELECT sync.packet
                  FROM sync
                  JOIN reference_user_sync ON reference_user_sync.sync = sync.id
                  JOIN user ON user.id = reference_user_sync.user
                  WHERE sync.community = ? AND user.mid = ? AND sync.name = ?
                  LIMIT 10
                  """

        self._send([address], [str(packet) for packet, in self._database.execute(sql, (message.community.database_id, buffer(message.payload.mid), meta.database_id))])

    def create_subjective_set(self, community, cluster, members, reset=True, update_locally=True, store_and_forward=True):
        if __debug__:
            from community import Community
            from member import Member
        assert isinstance(community, Community)
        assert isinstance(cluster, int)
        assert isinstance(members, (tuple, list))
        assert not filter(lambda member: not isinstance(member, Member), members)
        assert isinstance(reset, bool)
        assert isinstance(update_locally, bool)
        assert isinstance(store_and_forward, bool)

        # modify the subjective set (bloom filter)
        try:
            subjective_set = community.get_subjective_set(community.my_member, cluster)
        except KeyError:
            subjective_set = BloomFilter(len(members), 0.1)
        if reset:
            subjective_set.clear()
        map(subjective_set.add, (member.public_key for member in members))

        # implement the message
        meta = community.get_meta_message(u"dispersy-subjective-set")
        message = meta.implement(meta.authentication.implement(community.my_member),
                                 meta.distribution.implement(community._timeline.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(cluster, subjective_set))

        if store_and_forward:
            self.store_and_forward([message])

        if update_locally:
            assert community._timeline.check(message)
            message.handle_callback(("", -1), message)

        return message

    def check_subjective_set(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

    def on_subjective_set(self, address, message):
        # we do not need to do anything here for now because we retrieve all information directly
        # from the database each time we need it.  Hence no in-memory actions needs to occur.  Note
        # that this data is immediately stored in the database when this method returns.
        pass

    def check_subjective_set_request(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

    def on_subjective_set_request(self, address, message):
        """
        We received a dispersy-subjective-set-request message.

        The dispersy-subjective-set-request message contains one member (20 byte sha1 digest) for
        which the subjective set is requested.  We will search our database for any maching
        subjective sets (there may be more, as the 20 byte sha1 digest may match more than one
        member) and sent them back.

        @see: create_subjective_set_request

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-subjective-set-request message.
        @type message: Message.Implementation
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message.Implementation), type(message)
        assert message.name == u"dispersy-subjective-set-request"

        subjective_set_message_id = message.community.get_meta_message(u"dispersy-subjective-set")
        packets = []
        for member in message.payload.members:
            # retrieve the packet from the database
            try:
                packet, = self._database.execute(u"SELECT packet FROM sync WHERE community = ? AND user = ? AND name = ? LIMIT",
                                                 (message.community.database.id, member.database_id, subjective_set_message_id)).next()
            except StopIteration:
                continue
            packet = str(packet)

            # check that this is the packet we are looking for, i.e. has the right cluster
            conversion = self.get_conversion(packet[:22])
            subjective_set_message = conversion.decode_message(packet)
            if subjective_set_message.destination.cluster == message.payload.clusters:
                packets.append(packet)
                if __debug__: log("dispersy.log", "dispersu-subjective-set-request - send back packet", length=len(packet), packet=packet)

        if packets:
            self._send([address], [packet])

    # def create_subjective_set_request(community, community, cluster, members, update_locally=True, store_and_forward=True):
    #     if __debug__:
    #         from community import Community
    #         from member import Member
    #     assert isinstance(community, Community)
    #     assert isinstance(cluster, int)
    #     assert isinstance(members, (tuple, list))
    #     assert not filter(lambda member: not isinstance(member, Member), members)
    #     assert isinstance(update_locally, bool)
    #     assert isinstance(store_and_forward, bool)

    #     # implement the message
    #     meta = community.get_meta_message(u"dispersy-subjective-set-request")
    #     message = meta.implement(meta.authentication.implement(),
    #                              meta.distribution.implement(community._timeline.global_time),
    #                              meta.destination.implement(),
    #                              meta.payload.implement(cluster, members))

    #     if update_locally:
    #         assert community._timeline.check(message)
    #         message.handle_callback(("", -1), message)

    #     if store_and_forward:
    #         self.store_and_forward([message])

    #     return message

    def create_similarity(self, community, meta_message, keywords, update_locally=True, store_and_forward=True):
        """
        Create a dispersy-similarity message.

        The SimilarityDestination policy allows messages to be disseminated between members that are
        deemed to be similar.  Calculating how similar members are is done using similarity data
        disseminated using dispersy-similarity messages.

        A dispersy-similarity message contains a bitstream, in the form of a one slice bloom filter,
        which is filled with items, in the form of keywords.  Each keyword sets one bit in the bloom
        filter to True, assuming that this bit was previously False.

        Each message that uses the SimilarityDestination policy can have its own similarity value
        associated to it, depending on the value of the meta_message.destination.cluster parameter.

        For example: we have a meta_message called 'forum-post' that uses the SimilarityDestination
        policy.  First we define that we are similar to peers with the words 'candy', 'chips', and
        'food' by calling create_similarity(meta_message, ['candy', 'chips', 'food']).  Now we can
        send a forum-post message using meta_message.implement(...) that will be disseminated based
        on our and their similarity.

        The create_similarity method can me called repeatedly.  Each time a new dispersy-similarity
        message will be generated and disseminated across the community.  Only the most recent value
        is propagated.

        @param community: The community for wich the dispersy-similarity message will be created.
        @type community: Community

        @param message: The meta message for which we are definding the similarity.
        @type message: Message

        @param keywords: The keywords that are used to populate the similarity bitstring.
        @type timeout: [string]

        @param update_locally: When True the community.on_authorize_message is called with each
         created message.  This parameter should (almost always) be True, its inclusion is mostly to
         allow certain debugging scenarios.
        @type update_locally: bool

        @param store_and_forward: When True the created messages are stored (as defined by the
         message distribution policy) in the local Dispersy database and the messages are forewarded
         to other peers (as defined by the message destination policy).  This parameter should
         (almost always) be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store_and_forward: bool

        @note: Multiple dispersy-similarity messages are not possible yet.  Hence using multiple
         messages with the SimilarityDestination and different cluster values will not work.
        """
        assert isinstance(community, Community)
        assert isinstance(meta_message, Message)
        assert isinstance(keywords, (tuple, list))
        assert not filter(lambda x: not isinstance(x, str), keywords)
        assert isinstance(update_locally, bool)
        assert isinstance(store_and_forward, bool)

        meta = community.get_meta_message(u"dispersy-similarity")

        # BloomFilter created with 1 slice and defined number of bits
        similarity = BloomFilter(1, meta_message.destination.size)
        map(similarity.add, keywords)

        # store into db
        self._database.execute(u"INSERT OR REPLACE INTO my_similarity(community, user, cluster, similarity) VALUES(?, ?, ?, ?)",
                               (community.database_id,
                                community.my_member.database_id,
                                meta_message.destination.cluster,
                                buffer(str(similarity))))

        similarity = self._regulate_similarity(community, meta_message.destination)

        # implement the message
        message = meta.implement(meta.authentication.implement(community.my_member),
                                 meta.distribution.implement(community._timeline.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(meta_message.destination.identifier, similarity))

        if store_and_forward:
            self.store_and_forward([message])

        if update_locally:
            assert community._timeline.check(message)
            message.handle_callback(("", -1), message)

        return message

    def check_similarity(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

    def on_similarity(self, address, message):
        """
        We received a dispersy-similarity message.

        The message contains a bloom-filter with only one slice that represents the sphere of
        influence of the creator of the message.

        We store this bloomfilter in our database and later use it, when we receive a dispersy-sync
        message, to check if we need to synchronize certain messages between members.

        @see create_similarity

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-similarity message.
        @type message: Message.Implementation
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message.Implementation)

        self._database.execute(u"INSERT OR REPLACE INTO similarity(community, user, cluster, similarity, packet) VALUES(?, ?, ?, ?, ?)",
                               (message.community.database_id,
                                message.authentication.member.database_id,
                                message.payload.cluster,
                                buffer(str(message.payload.similarity)),
                                buffer(message.packet)))

    def _regulate_similarity(self, community, similarity_destination):
        """
        Regulate the BloomFilter similarity by randomly inserting extra bits until the number of
        bits is at least the minumum amound of bits as defined in similarity_destination

        @todo: figure out this method... is a bit messy and doesn't do anything yet.  Randomness
         should be replaced by something usefull to promote semantic clustering.
        """
        # assert here
        if __debug__:
            from destination import SimilarityDestination
        assert isinstance(similarity_destination, SimilarityDestination)

        minimum_bits = similarity_destination.minimum_bits
        maximum_bits = similarity_destination.maximum_bits

        # fetch my_similarity from db
        try:
            my_similarity, = self._database.execute(u"SELECT similarity FROM my_similarity WHERE community == ? AND user == ? AND cluster == ? LIMIT 1",
                                                    (community.database_id, community.my_member.database_id, similarity_destination.cluster)).next()
        except StopIteration:
            raise ValueError(u"Similarity not found in database")

        # the database returns <buffer> types, we use the binary
        # <str> type internally
        similarity = BloomFilter(str(my_similarity), 0)

        # todo: make this into a bloomfilter method
        # count the 1's
        set_bits = 0
        for c in similarity._bytes.tostring():
            s = "{0:08d}".format(int(bin(ord(c))[2:]))
            for bit in s:
                if bit == '1':
                    set_bits += 1

        if set_bits > maximum_bits:
            raise ValueError("To many bits set in the similarity")

        # todo: make this into a bloomfilter method (the setting of specific bits)
        # add new bits
        new_bits = 0
        check = 0b1
        while new_bits < minimum_bits - set_bits:
            for b in range(len(similarity._bytes)):
                if not similarity._bytes[b] & check:
                    similarity._bytes[b] |= check
                    new_bits += 1
            check <<= 1

        return similarity

    # todo: implement a create_similarity_request method
    # def create_similarity_request(self,

    def check_similarity_request(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

    def on_similarity_request(self, address, message):
        """
        We received a dispersy-similarity-request message.

        The dispersy-similarity-request message contains a list of members for which the similarity
        is requested.  We will search out database for any similarity data that we can find and send
        them back.

        @see: create_similarity_request

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-signature-request message.
        @type message: Message.Implementation
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message.Implementation), type(message)
        assert message.name == u"dispersy-similarity-request"

        for member in message.payload.members:
            try:
                packet, = self._database.execute(u"SELECT packet FROM similarity WHERE community = ? AND user = ? AND cluster = ? LIMIT 1",
                                                 (message.community.database.id, member.database_id, message.payload.cluster)).next()
            except StopIteration:
                continue

            self._send([address], [packet])
            if __debug__: log("dispersy.log", "dispersy-missing-sequence - send back packet", length=len(packet), packet=packet, low=message.payload.missing_low, high=message.payload.missing_high)

    def create_signature_request(self, community, message, response_func, response_args=(), timeout=10.0, store_and_forward=True):
        """
        Create a dispersy-signature-request message.

        The dispersy-signature-request message contains a sub-message that is to be signed my
        multiple members.  The sub-message must use the MultiMemberAuthentication policy in order to
        store the multiple members and their signatures.

        Typically, each member that should add a signature will receive the
        dispersy-signature-request message.  If they choose to add their signature, a
        dispersy-signature-response message is send back.  This in turn will result in a call to
        response_func with the message that now has one additional signature.

        Each dispersy-signed-response message will result in one call to response_func.  The
        parameters for this call are the address where the response came from and the sub-message.
        When all signatures are available the property sub-message.authentication.is_signed will be
        True.

        If not all members sent a reply withing timeout seconds, one final call to response_func is
        made with parameters ('', -1) and None, for the address and message respectively.

        @param community: The community for wich the dispersy-signature-request message will be
         created.
        @type community: Community

        @param message: The message that is to receive multiple signatures.
        @type message: Message.Implementation

        @param response_func: The method that is called when a signature or a timeout is received.
        @type response_func: callable method

        @param response_args: Optional arguments added when calling response_func.
        @type response_args: tuple

        @param timeout: How long before a timeout is generated.
        @type timeout: float

        @param store_and_forward: When True the created messages are stored (as defined by the
         message distribution policy) in the local Dispersy database and the messages are forewarded
         to other peers (as defined by the message destination policy).  This parameter should
         (almost always) be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store_and_forward: bool
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(message, Message.Implementation)
        assert isinstance(message.authentication, MultiMemberAuthentication.Implementation)
        assert hasattr(response_func, "__call__")
        assert isinstance(response_args, tuple)
        assert isinstance(timeout, float)
        assert isinstance(store_and_forward, bool)

        # the members that need to sign
        members = [member for signature, member in message.authentication.signed_members if not (signature or isinstance(member, PrivateMember))]

        # the dispersy-signature-request message that will hold the
        # message that should obtain more signatures
        meta = community.get_meta_message(u"dispersy-signature-request")
        request = meta.implement(meta.authentication.implement(),
                                 meta.distribution.implement(community._timeline.global_time),
                                 meta.destination.implement(*members),
                                 meta.payload.implement(message))

        if store_and_forward:
            self.store_and_forward([request])

        # set callback and timeout
        identifier = sha1(request.packet).digest()
        footprint = community.get_meta_message(u"dispersy-signature-response").generate_footprint(payload=(identifier,))
        self.await_message(footprint, self._on_signature_response, (request, response_func, response_args), timeout, len(members))

        return request

    def check_similarity_request(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

        # submsg contains the message that should receive multiple signatures
        submsg = message.payload.message

        has_private_member = False
        for is_signed, member in submsg.authentication.signed_members:
            # Security: do NOT allow to accidentally sign with MasterMember.
            if isinstance(member, MasterMember):
                raise DropMessage("You may never ask for a MasterMember signature")

            # is this signature missing, and could we provide it
            if not is_signed and isinstance(member, PrivateMember):
                has_private_member = True
                break

        # we must be one of the members that needs to sign
        if not has_private_member:
            raise DropMessage("Nothing to sign")

        # the message must be valid
        if not submsg.community._timeline.check(submsg):
            raise DropMessage("Doesn't fit timeline")

        # the community must allow this signature
        if not submsg.authentication.allow_signature_func(submsg):
            raise DropMessage("We choose not to add our signature")

    def check_signature_request(self, address, message):
        # we can not timeline.check this message because it uses the NoAuthentication policy

        # submsg contains the message that should receive multiple signatures
        submsg = message.payload.message

        has_private_member = False
        for is_signed, member in submsg.authentication.signed_members:
            # Security: do NOT allow to accidentally sign with MasterMember.
            if isinstance(member, MasterMember):
                raise DropMessage("You may never ask for a MasterMember signature")

            # is this signature missing, and could we provide it
            if not is_signed and isinstance(member, PrivateMember):
                has_private_member = True
                break

        # we must be one of the members that needs to sign
        if not has_private_member:
            raise DropMessage("Nothing to sign")

        # we can not timeline.check the submessage because it uses the MultiMemberAuthentication policy
        # # the message that we are signing must be valid according to our timeline
        # # if not message.community._timeline.check(submsg):
        # #     raise DropMessage("Does not fit timeline")

        # the community must allow this signature
        if not submsg.authentication.allow_signature_func(submsg):
            raise DropMessage("We choose not to add our signature")

    def on_signature_request(self, address, message):
        """
        We received a dispersy-signature-request message.

        This message contains a sub-message (message.payload) that the message creator would like to
        have us sign.  The message may, or may not, have already been signed by some of the other
        members.  Furthermore, we can choose for ourselves if we want to add our signature to the
        sub-message or not.

        Once we have determined that we could provide a signature and that the sub-message is valid,
        from a timeline perspective, we will ask the community to say yes or no to adding our
        signature.  This question is done by calling the
        sub-message.authentication.allow_signature_func method.

        Only when the allow_signature_func method returns True will we add our signature.  In this
        case a dispersy-signature-response message is send to the creator of the message, the first
        one in the authentication list.

        Note that if for whatever reason we can add multiple signatures, i.e. we have the private
        key for more that one member signing the sub-message, we will send one
        dispersy-signature-response message for each signature that we can supply.

        @see: create_signature_request

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-signature-request message.
        @type message: Message.Implementation
        """
        if __debug__:
            from message import Message
            from authentication import MultiMemberAuthentication
        assert isinstance(message, Message.Implementation), type(message)
        assert isinstance(message.payload.message, Message.Implementation), type(message.payload.message)
        assert isinstance(message.payload.message.authentication, MultiMemberAuthentication.Implementation), type(message.payload.message.authentication)

        # submsg contains the message that should receive multiple signatures
        submsg = message.payload.message

        # create signature(s) and reply
        identifier = sha1(message.packet).digest()
        first_signature_offset = len(submsg.packet) - sum([member.signature_length for member in submsg.authentication.members])
        for member in submsg.authentication.members:
            if isinstance(member, PrivateMember):
                signature = member.sign(submsg.packet, 0, first_signature_offset)

                # send response
                meta = message.community.get_meta_message(u"dispersy-signature-response")
                message = meta.implement(meta.authentication.implement(),
                                         meta.distribution.implement(message.community._timeline.global_time),
                                         meta.destination.implement(address,),
                                         meta.payload.implement(identifier, signature))
                self.store_and_forward([message])

    def check_signature_response(self, address, message):
        # we can not timeline.check this message because it uses the NoAuthentication policy
        pass

    def on_signature_response(self, address, message):
        pass

    def _on_signature_response(self, address, response, request, response_func, response_args):
        """
        A Trigger matched a received dispersy-signature-response message.

        We sent out a dispersy-signature-request, though the create_signature_request method, and
        have now received a dispersy-signature-response in reply.  If the signature is valid, we
        will call response_func with address and sub-message, where sub-message is the message
        parameter given to the create_signature_request method.

        When a timeout occurs the response_func will also be called, although now the address and
        sub-message parameters will be set to ('', -1) and None, respectively.

        Note that response_func is also called when the sub-message does not yet contain all the
        signatures.  This can be checked using sub-message.authentication.is_signed.

        @see: create_signature_request

        @param address: The sender address.
        @type address: (string, int)

        @param response: The dispersy-signature-response message.
        @type response: Message.Implementation

        @param request: The dispersy-dispersy-request message.
        @type message: Message.Implementation

        @param response_func: The method that is called when a signature or a timeout is received.
        @type response_func: callable method

        @param response_args: Optional arguments added when calling response_func.
        @type response_args: tuple
        """
        assert isinstance(address, tuple)
        assert isinstance(address[0], str)
        assert isinstance(address[1], int)
        assert response is None or isinstance(response, Message.Implementation)
        assert response is None or response.name == u"dispersy-signature-response"
        assert isinstance(request, Message.Implementation)
        assert request.name == u"dispersy-signature-request"
        assert hasattr(response_func, "__call__")
        assert isinstance(response_args, tuple)

        # check for timeout
        if response is None:
            response_func(address, response, *response_args)

        else:
            # the multi signed message
            submsg = request.payload.message

            first_signature_offset = len(submsg.packet) - sum([member.signature_length for member in submsg.authentication.members])
            body = submsg.packet[:first_signature_offset]

            for signature, member in submsg.authentication.signed_members:
                if not signature and member.verify(body, response.payload.signature):
                    submsg.authentication.set_signature(member, response.payload.signature)
                    response_func(address, submsg, *response_args)

                    # assuming this signature only matches one member, we can break
                    break

    def check_missing_sequence(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

    def on_missing_sequence(self, address, message):
        """
        We received a dispersy-missing-sequence message.

        The message contains a member and a range of sequence numbers.  We will send the messages,
        up to a certain limit, in this range back to the sender.

        To limit the amount of bandwidth used we will not sent back more data after a certain amount
        has been sent.  This magic number is subject to change.

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-missing-sequence message.
        @type message: Message.Implementation

        @todo: we need to optimise this to include a bandwidth throttle.  Otherwise a node can
         easilly force us to send arbitrary large amounts of data.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message)
        assert message.name == u"dispersy-missing-sequence"

        # we limit the response by byte_limit bytes
        byte_limit = self._total_send + message.community.dispersy_missing_sequence_response_limit

        payload = message.payload
        for packet, in self._database.execute(u"SELECT packet FROM sync_full WHERE community = ? and sequence >= ? AND sequence <= ? ORDER BY sequence LIMIT ?",
                                              (payload.message.community.database_id, payload.missing_low, payload.missing_high, packet_limit)):
            if __debug__: dprint("Syncing ", len(packet), " bytes from sync_full to " , address[0], ":", address[1])
            self._socket.send(address, packet)

            self._total_send += len(packet)
            if self._total_send > byte_limit:
                if __debug__: dprint("Bandwidth throttle")
                break

    def check_sync(self, address, message):
        """
        We received a dispersy-sync message.

        The message contains a bloom-filter that needs to be checked.  If we find any messages that
        are not in the bloom-filter, we will sent those to the sender.

        To limit the amount of bandwidth used we will not sent back more data after a certain amount
        has been sent.  This magic number is subject to change.

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-sync message.
        @type message: Message.Implementation

        @todo: we should look into optimizing this method, currently it just sends back data.
         Therefore, if multiple nodes receive this dispersy-sync message they will probably all send
         the same messages back.  So we need to make things smarter!

        @todo: we need to optimise this to include a bandwidth throttle.  Otherwise a node can
         easilly force us to send arbitrary large amounts of data.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message.Implementation)
        assert message.name == u"dispersy-sync"

        # def get_similarity(cluster):
        #     try:
        #         similarity, = self._database.execute(u"SELECT similarity FROM similarity WHERE community = ? AND user = ? AND cluster = ?",
        #                                              (message.community.database_id, message.authentication.member.database_id, cluster)).next()
        #     except StopIteration:
        #         # this message should never have been stored in the database without a similarity.
        #         # Thus the Database is corrupted.
        #         raise DelayMessageBySimilarity(message, cluster)

        #     for msg in message.community.get_meta_messages():
        #         if isinstance(msg.destination, SimilarityDestination) and msg.destination.cluster == cluster:
        #             threshold = msg.destination.threshold
        #             break
        #     else:
        #         raise NotImplementedError("No messages are defined that use this cluster")

        #     return BloomFilter(str(similarity), 0), threshold

        def get_packets(community_id, time_low, time_high):
            # first priority is to return the 'in-order' packets
# sync.destination_cluster, similarity.similarity
# JOIN similarity ON sync.community = similarity.community AND user.id = similarity.user AND sync.destination_cluster = similarity.cluster
            sql = u"""SELECT sync.packet, sync.name, user.public_key
                      FROM sync
                      JOIN reference_user_sync ON reference_user_sync.sync = sync.id
                      JOIN user ON user.id = reference_user_sync.user
                      WHERE sync.community = ? AND synchronization_direction = 1 AND sync.global_time BETWEEN ? AND ?
                      ORDER BY sync.global_time ASC"""
            for tup in self._database.execute(sql, (community_id, time_low, time_high)):
                yield tup

            # second priority is to return the 'out-order' packets
# sync.destination_cluster, similarity.similarity
# JOIN similarity ON sync.community = similarity.community AND user.id = similarity.user AND sync.destination_cluster = similarity.cluster
            sql = u"""SELECT sync.packet, sync.name, user.public_key
                      FROM sync
                      JOIN reference_user_sync ON reference_user_sync.sync = sync.id
                      JOIN user ON user.id = reference_user_sync.user
                      WHERE sync.community = ? AND synchronization_direction = 2 AND sync.global_time BETWEEN ? AND ?
                      ORDER BY sync.global_time DESC"""
            for tup in self._database.execute(sql, (community_id, time_low, time_high)):
                yield tup

            # third priority is to return the 'random-order' packets
# sync.destination_cluster, similarity.similarity
# JOIN similarity ON sync.community = similarity.community AND user.id = similarity.user AND sync.destination_cluster = similarity.cluster
            sql = u"""SELECT sync.packet, sync.name, user.public_key
                      FROM sync
                      JOIN reference_user_sync ON reference_user_sync.sync = sync.id
                      JOIN user ON user.id = reference_user_sync.user
                      WHERE sync.community = ? AND synchronization_direction = 3 AND sync.global_time BETWEEN ? AND ?
                      ORDER BY RANDOM()"""
            for tup in self._database.execute(sql, (community_id, time_low, time_high)):
                yield tup

        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

        # we limit the response by byte_limit bytes
        byte_limit = self._total_send + message.community.dispersy_sync_response_limit

        # similarity_cache = {}

        # obtain all subjective sets for the sender of the dispersy-sync message
        subjective_sets = message.community.get_subjective_sets(message.authentication.member)

        # obtain all available messages
        meta_messages = dict((meta_message.database_id, meta_message) for meta_message in message.community.get_meta_messages())

        bloom_filter = message.payload.bloom_filter
        time_high = message.payload.time_high if message.payload.has_time_high else message.community._timeline.global_time
        packets = []

        for packet, meta_message_id, packet_public_key in get_packets(message.community.database_id, message.payload.time_low, time_high):
            packet = str(packet)
            packet_public_key = str(packet_public_key)

            if not packet in bloom_filter:
                # check if the packet uses the SubjectiveDestination policy
                packet_meta = meta_messages[meta_message_id]
                if isinstance(packet_meta.destination, SubjectiveDestination):
                    packet_cluster = packet_meta.destination.cluster

                    # we need the subjective set for this particular cluster
                    if not packet_cluster in subjective_sets:
                        if __debug__: dprint("Subjective set not available")
                        raise DelayMessageBySubjectiveSet(message, packet_cluster)

                    # is packet_public_key in the subjective set
                    if not packet_public_key in subjective_sets[packet_cluster]:
                        # do not send this packet: not in the requester's subjective set
                        continue

                # # check if the packet uses the SimilarityDestination policy
                # if similarity_cluster:
                #     similarity, threshold = similarity_cache.get(similarity_cluster, (None, None))
                #     if similarity is None:
                #         similarity, threshold = get_similarity(similarity_cluster)
                #         similarity_cache[similarity_cluster] = (similarity, threshold)

                #     if similarity.bic_occurrence(BloomFilter(str(packet_similarity), 0)) < threshold:
                #         if __debug__: dprint("do not send this packet: not similar")
                #         # do not send this packet: not similar
                #         continue

                if __debug__: dprint("syncing ", packet_meta.name, " (", len(packet), " bytes) to " , address[0], ":", address[1])
                packets.append(packet)

                byte_limit -= len(packet)
                if byte_limit <= 0:
                    if __debug__: dprint("bandwidth throttle")
                    break

        if packets:
            self._send([address], packets)

    def on_sync(self, address, message):
        # everything has already been done in check_sync.
        pass

    def create_authorize(self, community, permission_triplets, sign_with_master=False, update_locally=True, store_and_forward=True):
        """
        Grant permissions to members in a community.

        This method will generate a message that grants the permissions in permission_triplets.
        Each item in permission_triplets contains (Member, Message, permission) where permission is
        either u'permit', u'authorize', or u'revoke'.

        By default, community.my_member is doing the authorization.  This means, that
        community.my_member must have the authorize permission for each of the permissions that she
        is authorizing.

        >>> # Authorize Bob to use Permit payload for 'some-message'
        >>> from Payload import Permit
        >>> bob = Member.get_instance(bob_public_key)
        >>> msg = self.get_meta_message(u"some-message")
        >>> self.create_authorize(community, [(bob, msg, u'permit')])

        @param community: The community where the permissions must be applied.
        @type sign_with_master: Community

        @param permission_triplets: The permissions that are granted.  Must be a list or tuple
         containing (Member, Message, permission) tuples.
        @type permissions_pairs: [(Member, Message, string)]

        @param sign_with_master: When True community.master_member is used to sign the authorize
         message.  Otherwise community.my_member is used.
        @type sign_with_master: bool

        @param update_locally: When True the community.on_message is called with each created
         message.  This parameter should (almost always) be True, its inclusion is mostly to allow
         certain debugging scenarios.
        @type update_locally: bool

        @param store_and_forward: When True the created messages are stored (as defined by the
         message distribution policy) in the local Dispersy database and the messages are forewarded
         to other peers (as defined by the message destination policy).  This parameter should
         (almost always) be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store_and_forward: bool
        """
        if __debug__:
            from community import Community
            from member import Member
            from message import Message
            assert isinstance(community, Community)
            assert isinstance(permission_triplets, (tuple, list))
            for triplet in permission_triplets:
                assert isinstance(triplet, tuple)
                assert len(triplet) == 3
                assert isinstance(triplet[0], Member)
                assert isinstance(triplet[1], Message)
                assert isinstance(triplet[2], unicode)
                assert triplet[2] in (u'permit', u'authorize', u'revoke')

        meta = community.get_meta_message(u"dispersy-authorize")
        message = meta.implement(meta.authentication.implement(community.master_member if sign_with_master else community.my_member),
                                 meta.distribution.implement(community._timeline.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(permission_triplets))

        if store_and_forward:
            self.store_and_forward([message])

        if update_locally:
            assert community._timeline.check(message)
            message.handle_callback(("", -1), message)

        return message

    def check_authorize(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

    def on_authorize(self, address, message):
        """
        Process a dispersy-authorize message.

        This method is called to process a dispersy-authorize message.  This message is either
        received from an external source or locally generated.

        When the message is locally generated the address will be set to ('', -1).

        @param address: The address from where we received this message.
        @type address: (string, int)

        @param message: The received message.
        @type message: Message.Implementation
        @raise DropMessage: When unable to verify that this message is valid.
        @todo: We should raise a DelayMessageByProof to ensure that we request the proof for this
         message immediately.
        """

        message.community._timeline.authorize(message.authentication.member, message.distribution.global_time, message.payload.permission_triplets)

    def create_revoke(self, community, permission_triplets, sign_with_master=False, update_locally=True, store_and_forward=True):
        """
        Revoke permissions from a members in a community.

        This method will generate a message that revokes the permissions in permission_triplets.
        Each item in permission_triplets contains (Member, Message, permission) where permission is
        either u'permit', u'authorize', or u'revoke'.

        By default, community.my_member is doing the revoking.  This means, that community.my_member
        must have the revoke permission for each of the permissions that she is revoking.

        >>> # Revoke the right of Bob to use Permit payload for 'some-message'
        >>> from Payload import Permit
        >>> bob = Member.get_instance(bob_public_key)
        >>> msg = self.get_meta_message(u"some-message")
        >>> self.create_revoke(community, [(bob, msg, u'permit')])

        @param community: The community where the permissions must be applied.
        @type sign_with_master: Community

        @param permission_triplets: The permissions that are revoked.  Must be a list or tuple
         containing (Member, Message, permission) tuples.
        @type permissions_pairs: [(Member, Message, string)]

        @param sign_with_master: When True community.master_member is used to sign the revoke
         message.  Otherwise community.my_member is used.
        @type sign_with_master: bool

        @param update_locally: When True the community.on_message is called with each created
         message.  This parameter should (almost always) be True, its inclusion is mostly to allow
         certain debugging scenarios.
        @type update_locally: bool

        @param store_and_forward: When True the created messages are stored (as defined by the
         message distribution policy) in the local Dispersy database and the messages are forewarded
         to other peers (as defined by the message destination policy).  This parameter should
         (almost always) be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store_and_forward: bool
        """
        if __debug__:
            from community import Community
            from member import Member
            from message import Message
            assert isinstance(community, Community)
            assert isinstance(permission_triplets, (tuple, list))
            for triplet in permission_triplets:
                assert isinstance(triplet, tuple)
                assert len(triplet) == 3
                assert isinstance(triplet[0], Member)
                assert isinstance(triplet[1], Message)
                assert isinstance(triplet[2], unicode)
                assert triplet[2] in (u'permit', u'authorize', u'revoke')

        meta = community.get_meta_message(u"dispersy-revoke")
        message = meta.implement(meta.authentication.implement(community.master_member if sign_with_master else community.my_member),
                                 meta.distribution.implement(community._timeline.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(permission_triplets))

        if store_and_forward:
            self.store_and_forward([message])

        if update_locally:
            assert community._timeline.check(message)
            message.handle_callback(("", -1), message)

        return message

    def check_revoke(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

    def on_revoke(self, address, message):
        """
        Process a dispersy-revoke message.

        This method is called to process a dispersy-revoke message.  This message is either received
        from an external source or locally generated.

        When the message is locally generated the address will be set to ('', -1).

        @param address: The address from where we received this message.
        @type address: (string, int)

        @param message: The received message.
        @type message: Message.Implementation
        @raise DropMessage: When unable to verify that this message is valid.
        @todo: We should raise a DelayMessageByProof to ensure that we request the proof for this
         message immediately.
        """
        message.community._timeline.revoke(message.authentication.member, message.distribution.global_time, message.payload.permission_triplets)

    def create_destroy_community(self, community, degree, sign_with_master=False, update_locally=True, store_and_forward=True):
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(degree, unicode)
        assert degree in (u"soft-kill", u"hard-kill")

        meta = community.get_meta_message(u"dispersy-destroy-community")
        message = meta.implement(meta.authentication.implement(community.master_member if sign_with_master else community.my_member),
                                 meta.distribution.implement(community._timeline.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(degree))

        if store_and_forward:
            self.store_and_forward([message])

        if update_locally:
            assert community._timeline.check(message)
            message.handle_callback(("", -1), message)

        return message

    def check_destroy_community(self, address, message):
        if not message.community._timeline.check(message):
            raise DropMessage("TODO: implement delay of proof")

    def on_destroy_community(self, address, message):
        if __debug__:
            from message import Message
        assert isinstance(message, Message.Implementation)
        assert message.name == u"dispersy-destroy-community"
        if __debug__: dprint(message)

        community = message.community

        # let the community code cleanup first.  This may also cause a DropMessage exception.
        community.on_dispersy_destroy_community(address, message)

        # community cleanup is done.  Now we will cleanup the dispersy database.

        if message.payload.is_soft_kill:
            # soft-kill: The community is frozen.  Dispersy will retain the data it has obtained.
            # However, no messages beyond the global-time of the dispersy-destroy-community message
            # will be accepted.  Responses to dispersy-sync messages will be send like normal.
            raise NotImplementedError()

        elif message.payload.is_hard_kill:
            # hard-kill: The community is destroyed.  Dispersy will throw away everything except the
            # dispersy-destroy-community message and the authorize chain that is required to verify
            # this message.  The community should also remove all its data and cleanup as much as
            # possible.

            # delete everything except (a) all dispersy-destroy-community messages (these both
            # authorize and revoke the usage of this message) and (b) the associated
            # dispersy-identity messages to verify the dispersy-destroy-community messages.

            # todo: this should be made more efficient.  not all dispersy-destroy-community messages
            # need to be kept.  Just the ones in the chain to authorize the message that has just
            # been received.

            identity_message_id = community.get_meta_message(u"dispersy-identity").database_id

            with self._database as execute:
                # 1. remove all except the dispersy-destroy-community and dispersy-identity messages
                execute(u"DELETE FROM sync WHERE community = ? AND NOT (name = ? OR name = ?)", (community.database_id, message.database_id, identity_message_id))

                # 2. cleanup the reference_user_sync table.  however, we should keep the ones that are still referenced
                execute(u"DELETE FROM reference_user_sync WHERE NOT EXISTS (SELECT * FROM sync WHERE community = ? AND sync.id = reference_user_sync.sync)", (community.database_id,))

                # 3. cleanup the routing table.  we need nothing here anymore
                execute(u"DELETE FROM routing WHERE community = ?", (community.database_id,))

    def _periodically_create_sync(self, community):
        """
        Periodically disperse the latest bloom filters for this community.

        Every N seconds one or more dispersy-sync message will be send for community.  This may
        result in members detecting that we are missing messages and them sending them to us.

        Note that there are several magic numbers involved:

         1. The frequency of calling _periodically_create_sync.  This is determined by
            self.dispersy_sync_interval.  This defaults to 20.0 (currently).

         2. Each interval up to L bloom filters are selected and sent in seperate dispersy-sync
            messages.  This is determined by the self.dispersy_sync_bloom_count.  This defaults to 2
            (currently).

         3. Each interval each dispersy-sync message is sent to up to C different members.  This is
            determined by the self.dispersy_sync_member_count.  This defaults to 10 (currently).

         4. How many bytes -at most- are sent back in response to a received dispersy-sync message.
            This is determined by the self.dispersy_sync_response_limit.  This defaults to 5KB.
        """
        meta = community.get_meta_message(u"dispersy-sync")
        messages = [meta.implement(meta.authentication.implement(community.my_member),
                                   meta.distribution.implement(community._timeline.global_time),
                                   meta.destination.implement(),
                                   meta.payload.implement(time_low, time_high, bloom_filter))
                    for time_low, time_high, bloom_filter
                    in community.dispersy_sync_bloom_filters]
        self.store_and_forward(messages)
        if community.dispersy_sync_initial_delay > 0.0 and community.dispersy_sync_interval > 0.0:
            self._rawserver.add_task(lambda: self._periodically_create_sync(community), community.dispersy_sync_interval, "id:sync-" + community.cid)

    def _periodically_create_routing_request(self, community):
        minimal_age, maximal_age = community.dispersy_routing_age_range
        sql = u"""SELECT host, port, STRFTIME('%s', DATETIME()) - STRFTIME('%s', incoming_time) AS age
                  FROM routing
                  WHERE community = ? AND age BETWEEN ? AND ?
                  ORDER BY age
                  LIMIT 30"""
        routes = [((str(host), port), float(age)) for host, port, age in self._database.execute(sql, (community.database_id, minimal_age, maximal_age))]

        meta = community.get_meta_message(u"dispersy-routing-request")
        requests = []
        for address in self._select_routing_addresses(community.database_id,
                                                      community.dispersy_routing_request_member_count,
                                                      community.dispersy_routing_request_destination_diff_range,
                                                      community.dispersy_routing_request_destination_age_range):
            requests.append(meta.implement(meta.authentication.implement(community.my_member),
                                           meta.distribution.implement(community._timeline.global_time),
                                           meta.destination.implement(address),
                                           meta.payload.implement(self._my_external_address, address, community.get_conversion().version, routes)))
        if requests:
            self.store_and_forward(requests)

        if community.dispersy_routing_request_initial_delay > 0.0 and community.dispersy_routing_request_interval > 0.0:
            self._rawserver.add_task(lambda: self._periodically_create_routing_request(community), community.dispersy_routing_request_interval, "id:routing-" + community.cid)

    def _periodically_cleanup_database(self):
        # cleannup routing tables
        with self._database as execute:
            for community in self._communities.itervalues():
                execute(u"DELETE FROM routing WHERE community = ? AND STRFTIME('%s', DATETIME()) - STRFTIME('%s', incoming_time) > ?",
                        (community.database_id, community.dispersy_routing_cleanup_age_threshold))
        self._rawserver.add_task(self._periodically_cleanup_database, 120.0)

    def _periodically_stats(self):
        """
        Periodically write bandwidth statistics to a log file.
        """
        if __debug__: log("dispersy.log", "statistics", total_send=self._total_send, total_received=self._total_received)
        self._rawserver.add_task(self._periodically_stats, 1.0)
