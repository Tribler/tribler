from candidate import LoopbackCandidate
from meta import MetaObject

if __debug__:
    import re
    from dprint import dprint

#
# Exceptions
#
class DelayPacket(Exception):
    """
    Raised by Conversion.decode_message when the packet can not be
    converted into a Message yet.  Delaying for 'some time' or until
    'some event' occurs.
    """
    def __init__(self, msg, pattern, request_packet):
        assert isinstance(msg, str)
        assert isinstance(pattern, str)
        assert re.compile(pattern)
        assert isinstance(request_packet, str)
        super(DelayPacket, self).__init__(msg)
        self._pattern = pattern
        self._request_packet = request_packet

    @property
    def pattern(self):
        return self._pattern

    @property
    def request_packet(self):
        return self._request_packet

class DelayPacketByMissingMember(DelayPacket):
    """
    Raised during Conversion.decode_message when an unknown member id
    was received.  A member id is the sha1 hash over the member's
    public key, hence there is a small chance that members with
    different public keys will have the same member id.

    Raising this exception should result in a request for all public
    keys associated to the missing member id.
    """
    def __init__(self, community, missing_member_id):
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(missing_member_id, str)
        assert len(missing_member_id) == 20
         # the footprint that will trigger the delayed packet
        footprint = community.get_meta_message(u"dispersy-identity").generate_footprint(authentication=([missing_member_id],))

        # the request message that asks for the message that will
        # trigger the delayed packet
        meta = community.get_meta_message(u"dispersy-missing-identity")
        message = meta.impl(distribution=(community.global_time,), payload=(missing_member_id,))

        super(DelayPacketByMissingMember, self).__init__("Missing member", footprint, message.packet)

class DelayPacketByMissingMessage(DelayPacket):
    """
    Raised during Conversion.decode_message when an unknown message is required to process a packet.
    The missing message is identified using the unique (community, member, global_time) triplet.
    """
    def __init__(self, community, member, global_times):
        if __debug__:
            from community import Community
            from member import Member
        assert isinstance(community, Community)
        assert isinstance(member, Member)
        assert isinstance(global_times, list)
        assert len(global_times) > 0
        assert all(isinstance(x, (int, long)) for x in global_times)
        assert all(x > 0 for x in global_times)
        # the footprint that will trigger the delayed packet
        footprint = "".join(("Community:", community.cid.encode("HEX"),
                             "\s", "(MemberAuthentication:", member.mid.encode("HEX"), "|MultiMemberAuthentication:[^\s]*", member.mid.encode("HEX"), "[^\s]*)",
                             "\s", "Resolution",
                             "\s", "((Relay|Direct|)Distribution:(", "|,".join(str(global_time) for global_time in global_times), ")|FullSyncDistribution:(", "|,".join(str(global_time) for global_time in global_times), "),[0-9]+)"))

        # the request message that asks for the message that will trigger the delayed packet
        meta = community.get_meta_message(u"dispersy-missing-message")
        message = meta.impl(distribution=(community.global_time,), payload=(member, global_times))

        # TODO: currently we can ask for one or more missing messages len(global_times) > 1.
        # However, the TriggerPacket does not allow a value for min/max responses until it triggers.
        # Hence it may trigger the packet before all missing messages are received.
        assert len(global_times) == 1, "See comment above"

        super(DelayPacketByMissingMessage, self).__init__("Missing message", footprint, message.packet)

class DropPacket(Exception):
    """
    Raised by Conversion.decode_message when the packet is invalid.
    I.e. does not conform to valid syntax, contains malicious
    behaviour, etc.
    """
    pass

class DelayMessage(Exception):
    """
    Raised during Community.on_incoming_message or
    Community.on_incoming_message; delaying for 'some time' or until
    'some event' occurs.
    """
    def __init__(self, msg, pattern, request, delayed):
        assert isinstance(msg, str)
        assert isinstance(pattern, str)
        assert re.compile(pattern)
        assert isinstance(request, Message.Implementation)
        assert isinstance(delayed, Message.Implementation)
        super(DelayMessage, self).__init__(msg)
        self._pattern = pattern
        self._request = request
        self._delayed = delayed

    @property
    def pattern(self):
        return self._pattern

    @property
    def request(self):
        return self._request

    @property
    def delayed(self):
        return self._delayed

class DelayMessageByProof(DelayMessage):
    """
    Raised when a message can not be processed because of missing permissions.

    Delays a message until a dispersy-authorize message is received.  With luck this
    dispersy-authorize message will contain the missing permission.

    TODO: we could extend the footprint of the dispersy-authorize to include clues as to what
    permissions are in the message.  This would allow us to match incoming messages more accurately.
    """
    def __init__(self, delayed):
        if __debug__:
            from message import Message
        assert isinstance(delayed, Message.Implementation)

        # 01/11/11 Boudewijn: adding "(?MESSAGE-NAME)" too the pattern will ensure that we create
        # different trigger object for different meta messages, note that a 'missing-proof' message
        # is ONLY sent when a new trigger is created...

        # the footprint that will trigger the delayed packet
        footprint = "".join(("(dispersy-authorize|dispersy-dynamic-settings)",
                             " Community:", delayed.community.cid.encode("HEX"),
                             "(?#", delayed.name.encode("UTF-8"), ")"))

        # the request message that asks for the message that will trigger the delayed packet
        meta = delayed.community.get_meta_message(u"dispersy-missing-proof")
        request = meta.impl(distribution=(delayed.community.global_time,), payload=(delayed.authentication.member, delayed.distribution.global_time))

        super(DelayMessageByProof, self).__init__("Missing proof", footprint, request, delayed)

# class DelayMessageByMissingMember(DelayPacket):
#     """
#     A member id is the sha1 hash over the member's public key, hence
#     there is a small chance that members with different public keys
#     will have the same member id.

#     Raising this exception should result in a request for all public
#     keys associated to the missing member id.
#     """
#     def __init__(self, community, missing_member_id):
#         if __debug__:
#             from community import Community
#         assert isinstance(community, Community)
#         assert isinstance(missing_member_id, str)
#         assert len(missing_member_id) == 20
#         # the footprint that will trigger the delayed packet
#         footprint = community.get_meta_message(u"dispersy-identity").generate_footprint(authentication=([missing_member_id],))

#         # the request message that asks for the message that will
#         # trigger the delayed packet
#         meta = community.get_meta_message(u"dispersy-identity-request")
#         request = meta.implement(meta.authentication.implement(),
#                                  meta.distribution.implement(community.global_time),
#                                  meta.destination.implement(),
#                                  meta.payload.implement(missing_member_id))

#         super(DelayMessageByMissingMember, self).__init__("Missing member", footprint, request, delayed_message)

class DelayMessageBySequence(DelayMessage):
    """
    Raised during Community.on_incoming_message or Community.on_incoming_message.

    Delaying until all missing sequence numbers have been received.
    """
    def __init__(self, delayed, missing_low, missing_high):
        if __debug__:
            from message import Message
        assert isinstance(delayed, Message.Implementation)
        assert isinstance(missing_low, (int, long))
        assert isinstance(missing_high, (int, long))
        assert 0 < missing_low <= missing_high
        # the footprint that will trigger the delayed packet
        footprint = "".join((delayed.name.encode("UTF-8"),
                             " Community:", delayed.community.cid.encode("HEX"),
                             " MemberAuthentication:", delayed.authentication.member.mid.encode("HEX"),
                             " Resolution",
                             " SyncDistribution:", str(missing_high),
                             " CommunityDestination"))

        # the request message that asks for the message that will
        # trigger the delayed packet
        meta = delayed.community.get_meta_message(u"dispersy-missing-sequence")
        request = meta.impl(distribution=(delayed.community.global_time,), payload=(delayed.authentication.member, delayed.meta, missing_low, missing_high))

        super(DelayMessageBySequence, self).__init__("Missing sequence numbers", footprint, request, delayed)

class DelayMessageBySubjectiveSet(DelayMessage):
    """
    Raised when a message is received and a dispersy-subjective-set message is required to process
    it.

    Delaying until a dispersy-subjective-set message is received that contains the missing data or
    until a timeout occurs.
    """
    def __init__(self, delayed, cluster):
        if __debug__:
            from message import Message
        assert isinstance(delayed, Message.Implementation)
        assert isinstance(cluster, int)
        # the footprint that will trigger the delayed packet
        meta = delayed.community.get_meta_message(u"dispersy-subjective-set")
        footprint = meta.generate_footprint(authentication=([delayed.authentication.member.mid],))

        # the request message that asks for the message that will trigger the delayed packet
        meta = delayed.community.get_meta_message(u"dispersy-missing-subjective-set")
        request = meta.impl(distribution=(delayed.community.global_time,), payload=(cluster, [delayed.authentication.member]))

        super(DelayMessageBySubjectiveSet, self).__init__("Missing subjective set", footprint, request, delayed)

class DropMessage(Exception):
    """
    Raised during Community.on_message.

    Drops a message because it violates 'something'.  More specific
    reasons can be given with by raising a spectific subclass.
    """
    def __init__(self, dropped, msg):
        if __debug__:
            from message import Message
        assert isinstance(dropped, Message.Implementation)
        assert isinstance(msg, (str, unicode))
        self._dropped = dropped
        super(DropMessage, self).__init__(msg)

    @property
    def dropped(self):
        return self._dropped

#
# batch
#

class BatchConfiguration(object):
    def __init__(self, max_window=0.0, priority=128, max_size=1024, max_age=300.0):
        """
        Per meta message configuration on batch handling.

        MAX_WINDOW sets the maximum size, in seconds, of the window.  A larger window results in
        larger batches and a longer average delay for incoming messages.  Setting MAX_WINDOW to zero
        disables batching, in this case all other parameters are ignored.

        PRIORITY sets the Callback priority of the task that processes the batch.  A higher priority
        will result in earlier handling when there is CPU contention.

        MAX_SIZE sets the maximum size of the batch.  A new batch will be created when this size is
        reached, even when new messages would fall within MAX_WINDOW size.  A larger MAX_SIZE
        results in more processing time per batch and will reduce responsiveness as the processing
        thread is occupied.  Also, when a batch reaches MAX_SIZE it is processed immediately.

        MAX_AGE sets the maximum age of the batch.  This is useful for messages that require a
        response.  When the requests are delayed for to long they will time out, in this case a
        response no longer needs to be sent.  MAX_AGE for the request messages should hence be lower
        than the used timeout + max_window on the response messages.
        """
        assert isinstance(max_window, float)
        assert 0.0 <= max_window, max_window
        assert isinstance(priority, int)
        assert isinstance(max_size, int)
        assert 0 < max_size, max_size
        assert isinstance(max_age, float)
        assert 0.0 <= max_window < max_age, [max_window, max_age]
        self._max_window = max_window
        self._priority = priority
        self._max_size = max_size
        self._max_age = max_age

    @property
    def enabled(self):
        # enabled when max_window is positive
        return 0.0 < self._max_window

    @property
    def max_window(self):
        return self._max_window

    @property
    def priority(self):
        return self._priority

    @property
    def max_size(self):
        return self._max_size

    @property
    def max_age(self):
        return self._max_age

#
# packet
#

class Packet(MetaObject.Implementation):
    def __init__(self, meta, packet, packet_id):
        assert isinstance(packet, str)
        assert isinstance(packet_id, (int, long))
        super(Packet, self).__init__(meta)
        self._packet = packet
        self._packet_id = packet_id

    @property
    def community(self):
        return self._meta._community

    @property
    def name(self):
        return self._meta._name

    @property
    def database_id(self):
        return self._meta._database_id

    @property
    def resolution(self):
        return self._meta._resolution

    @property
    def check_callback(self):
        return self._meta._check_callback

    @property
    def handle_callback(self):
        return self._meta._handle_callback

    @property
    def undo_callback(self):
        return self._meta._undo_callback

    @property
    def priority(self):
        return self._meta._priority

    @property
    def delay(self):
        return self._meta._delay

    @property
    def packet(self):
        return self._packet

    # @property
    def __get_packet_id(self):
        return self._packet_id
    # @packet_id.setter
    def __set_packet_id(self, packet_id):
        assert isinstance(packet_id, (int, long))
        self._packet_id = packet_id
    # .setter was introduced in Python 2.6
    packet_id = property(__get_packet_id, __set_packet_id)

    def load_message(self):
        # find associated conversion
        try:
            conversion = self._meta.community.get_conversion(self._packet[:22])
        except KeyError:
            if __debug__: dprint("unable to convert a ", len(self._packet), " byte packet (unknown conversion)", level="warning")
            return None

        # attempt conversion
        try:
            message = conversion.decode_message(LoopbackCandidate(), self._packet)

        except (DropPacket, DelayPacket), exception:
            if __debug__: dprint("unable to convert a ", len(self._packet), " byte packet (", exception, ")", exception=True, level="warning")
            return None

        message.packet_id = self._packet_id
        return message

    def __str__(self):
        return "<%s.%s %s %dbytes>" % (self._meta.__class__.__name__, self.__class__.__name__, self._meta._name, len(self._packet))

#
# message
#
class Message(MetaObject):
    class Implementation(Packet):
        def __init__(self, meta, authentication, resolution, distribution, destination, payload, conversion=None, candidate=None, packet="", packet_id=0):
            if __debug__:
                from payload import Payload
                from conversion import Conversion
                from candidate import Candidate
            assert isinstance(meta, Message), "META has invalid type '%s'" % type(meta)
            assert isinstance(authentication, meta._authentication.Implementation), "AUTHENTICATION has invalid type '%s'" % type(authentication)
            assert isinstance(resolution, meta._resolution.Implementation), "RESOLUTION has invalid type '%s'" % type(resolution)
            assert isinstance(distribution, meta._distribution.Implementation), "DISTRIBUTION has invalid type '%s'" % type(distribution)
            assert isinstance(destination, meta._destination.Implementation), "DESTINATION has invalid type '%s'" % type(destination)
            assert isinstance(payload, meta._payload.Implementation), "PAYLOAD has invalid type '%s'" % type(payload)
            assert conversion is None or isinstance(conversion, Conversion), "CONVERSION has invalid type '%s'" % type(conversion)
            assert candidate is None or isinstance(candidate, Candidate)
            assert isinstance(packet, str)
            assert isinstance(packet_id, (int, long))
            super(Message.Implementation, self).__init__(meta, packet, packet_id)
            self._authentication = authentication
            self._resolution = resolution
            self._distribution = distribution
            self._destination = destination
            self._payload = payload
            self._candidate = candidate
            self._footprint = None

            # allow setup parts.  used to setup callback when something changes that requires the
            # self._packet to be generated again
            self._authentication.setup(self)
            # self._resolution.setup(self)
            # self._distribution.setup(self)
            # self._destination.setup(self)
            # self._payload.setup(self)

            if conversion:
                self._conversion = conversion
            elif packet:
                self._conversion = meta._community.get_conversion(packet[:22])
            else:
                self._conversion = meta._community.get_conversion()

            if not packet:
                self._packet = self._conversion.encode_message(self)

        @property
        def conversion(self):
            return self._conversion

        @property
        def authentication(self):
            return self._authentication

        @property
        def resolution(self):
            return self._resolution

        @property
        def distribution(self):
            return self._distribution

        @property
        def destination(self):
            return self._destination

        @property
        def payload(self):
            return self._payload

        @property
        def candidate(self):
            return self._candidate

        @property
        def footprint(self):
            if self._footprint is None:
                self._footprint = " ".join((self._meta.name.encode("UTF-8"),
                                            "Community:%s" % self._meta.community.cid.encode("HEX"),
                                            self._authentication.footprint,
                                            self._resolution.footprint,
                                            self._distribution.footprint,
                                            self._destination.footprint,
                                            self._payload.footprint))
            return self._footprint

        def load_message(self):
            return self

        def regenerate_packet(self, packet=""):
            if packet:
                self._packet = packet
            else:
                self._packet = self._conversion.encode_message(self)

        def __str__(self):
            return "<%s.%s %s %d>" % (self._meta.__class__.__name__, self.__class__.__name__, self._meta._name, len(self._packet))

    def __init__(self, community, name, authentication, resolution, distribution, destination, payload, check_callback, handle_callback, undo_callback=None, batch=None):
        if __debug__:
            from community import Community
            from authentication import Authentication
            from resolution import Resolution, DynamicResolution
            from destination import Destination
            from distribution import Distribution
            from payload import Payload
        assert isinstance(community, Community), "COMMUNITY has invalid type '%s'" % type(community)
        assert isinstance(name, unicode), "NAME has invalid type '%s'" % type(name)
        assert isinstance(authentication, Authentication), "AUTHENTICATION has invalid type '%s'" % type(authentication)
        assert isinstance(resolution, Resolution), "RESOLUTION has invalid type '%s'" % type(resolution)
        assert isinstance(distribution, Distribution), "DISTRIBUTION has invalid type '%s'" % type(distribution)
        assert isinstance(destination, Destination), "DESTINATION has invalid type '%s'" % type(destination)
        assert isinstance(payload, Payload), "PAYLOAD has invalid type '%s'" % type(payload)
        assert callable(check_callback)
        assert callable(handle_callback)
        assert undo_callback is None or callable(undo_callback), undo_callback
        if __debug__:
            if isinstance(resolution, DynamicResolution):
                assert callable(undo_callback), "UNDO_CALLBACK must be specified when using the DynamicResolution policy"
        assert batch is None or isinstance(batch, BatchConfiguration)
        assert self.check_policy_combination(authentication, resolution, distribution, destination)
        self._community = community
        self._name = name
        self._authentication = authentication
        self._resolution = resolution
        self._distribution = distribution
        self._destination = destination
        self._payload = payload
        self._check_callback = check_callback
        self._handle_callback = handle_callback
        self._undo_callback = undo_callback
        self._batch = BatchConfiguration() if batch is None else batch

        # setup
        database = community.dispersy.database

        # ensure that there is a database id associated to this
        # meta message name
        try:
            self._database_id, = database.execute(u"SELECT id FROM meta_message WHERE community = ? AND name = ?", (community.database_id, name)).next()
        except StopIteration:
            database.execute(u"INSERT INTO meta_message (community, name) VALUES (?, ?)", (community.database_id, name))
            self._database_id = database.last_insert_rowid

        # allow optional setup methods to initialize the specific
        # parts of the meta message
        self._authentication.setup(self)
        self._resolution.setup(self)
        self._distribution.setup(self)
        self._destination.setup(self)
        self._payload.setup(self)

    @property
    def community(self):
        return self._community

    @property
    def name(self):
        return self._name

    @property
    def database_id(self):
        return self._database_id

    @property
    def authentication(self):
        return self._authentication

    @property
    def resolution(self):
        return self._resolution

    @property
    def distribution(self):
        return self._distribution

    @property
    def destination(self):
        return self._destination

    @property
    def payload(self):
        return self._payload

    @property
    def check_callback(self):
        return self._check_callback

    @property
    def handle_callback(self):
        return self._handle_callback

    @property
    def undo_callback(self):
        return self._undo_callback

    @property
    def batch(self):
        return self._batch

    def generate_footprint(self, authentication=(), resolution=(), distribution=(), destination=(), payload=()):
        if __debug__:
            assert isinstance(authentication, tuple), type(authentication)
            assert isinstance(resolution, tuple), type(resolution)
            assert isinstance(distribution, tuple), type(distribution)
            assert isinstance(destination, tuple), type(destination)
            assert isinstance(payload, tuple), type(payload)
            try:
                authentication_footprint = self._authentication.generate_footprint(*authentication)
                resolution_footprint = self._resolution.generate_footprint(*resolution)
                distribution_footprint = self._distribution.generate_footprint(*distribution)
                destination_footprint = self._destination.generate_footprint(*destination)
                payload_footprint = self._payload.generate_footprint(*payload)
            except TypeError:
                dprint("message name:   ", self._name, level="error")
                dprint("authentication: ", self._authentication.__class__.__name__, level="error")
                dprint("resolution:     ", self._resolution.__class__.__name__, level="error")
                dprint("distribution:   ", self._distribution.__class__.__name__, level="error")
                dprint("destination:    ", self._destination.__class__.__name__, level="error")
                dprint("payload:        ", self._payload.__class__.__name__, level="error")
                raise
            else:
                return " ".join((self._name.encode("UTF-8"), "Community:%s" % self._community.cid.encode("HEX"), authentication_footprint, resolution_footprint, distribution_footprint, destination_footprint, payload_footprint))

        return " ".join((self._name.encode("UTF-8"),
                         "Community:%s" % self._community.cid.encode("HEX"),
                         self._authentication.generate_footprint(*authentication),
                         self._resolution.generate_footprint(*resolution),
                         self._distribution.generate_footprint(*distribution),
                         self._destination.generate_footprint(*destination),
                         self._payload.generate_footprint(*payload)))

    def impl(self, authentication=(), resolution=(), distribution=(), destination=(), payload=(), *args, **kargs):
        if __debug__:
            assert isinstance(authentication, tuple), type(authentication)
            assert isinstance(resolution, tuple), type(resolution)
            assert isinstance(distribution, tuple), type(distribution)
            assert isinstance(destination, tuple), type(destination)
            assert isinstance(payload, tuple), type(payload)
            try:
                authentication_impl = self._authentication.Implementation(self._authentication, *authentication)
                resolution_impl = self._resolution.Implementation(self._resolution, *resolution)
                distribution_impl = self._distribution.Implementation(self._distribution, *distribution)
                destination_impl = self._destination.Implementation(self._destination, *destination)
                payload_impl = self._payload.Implementation(self._payload, *payload)
            except TypeError:
                dprint("message name:   ", self._name, level="error")
                dprint("authentication: ", self._authentication.__class__.__name__, ".Implementation", level="error")
                dprint("resolution:     ", self._resolution.__class__.__name__, ".Implementation", level="error")
                dprint("distribution:   ", self._distribution.__class__.__name__, ".Implementation", level="error")
                dprint("destination:    ", self._destination.__class__.__name__, ".Implementation", level="error")
                dprint("payload:        ", self._payload.__class__.__name__, ".Implementation", level="error")
                raise
            else:
                return self.Implementation(self, authentication_impl, resolution_impl, distribution_impl, destination_impl, payload_impl, *args, **kargs)

        return self.Implementation(self,
                                   self._authentication.Implementation(self._authentication, *authentication),
                                   self._resolution.Implementation(self._resolution, *resolution),
                                   self._distribution.Implementation(self._distribution, *distribution),
                                   self._destination.Implementation(self._destination, *destination),
                                   self._payload.Implementation(self._payload, *payload),
                                   *args, **kargs)


    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, self._name)

    @staticmethod
    def check_policy_combination(authentication, resolution, distribution, destination):
        from authentication import Authentication, NoAuthentication, MemberAuthentication, MultiMemberAuthentication
        from resolution import Resolution, PublicResolution, LinearResolution, DynamicResolution
        from distribution import Distribution, RelayDistribution, DirectDistribution, FullSyncDistribution, LastSyncDistribution
        from destination import Destination, CandidateDestination, MemberDestination, CommunityDestination, SubjectiveDestination

        assert isinstance(authentication, Authentication)
        assert isinstance(resolution, Resolution)
        assert isinstance(distribution, Distribution)
        assert isinstance(destination, Destination)

        def require(a, b, c):
            if not isinstance(b, c):
                raise ValueError("%s does not support %s.  Allowed options are: %s" % (a.__class__.__name__, b.__class__.__name__, ", ".join([x.__name__ for x in c])))

        if isinstance(authentication, NoAuthentication):
            require(authentication, resolution, PublicResolution)
            require(authentication, distribution, (RelayDistribution, DirectDistribution))
            require(authentication, destination, (CandidateDestination, MemberDestination, CommunityDestination))
        elif isinstance(authentication, MemberAuthentication):
            require(authentication, resolution, (PublicResolution, LinearResolution, DynamicResolution))
            require(authentication, distribution, (RelayDistribution, DirectDistribution, FullSyncDistribution, LastSyncDistribution))
            require(authentication, destination, (CandidateDestination, MemberDestination, CommunityDestination, SubjectiveDestination))
        elif isinstance(authentication, MultiMemberAuthentication):
            require(authentication, resolution, (PublicResolution, LinearResolution, DynamicResolution))
            require(authentication, distribution, (RelayDistribution, DirectDistribution, FullSyncDistribution, LastSyncDistribution))
            require(authentication, destination, (CandidateDestination, MemberDestination, CommunityDestination, SubjectiveDestination))
        else:
            raise ValueError("%s is not supported" % authentication.__class_.__name__)

        if isinstance(resolution, PublicResolution):
            require(resolution, authentication, (NoAuthentication, MemberAuthentication, MultiMemberAuthentication))
            require(resolution, distribution, (RelayDistribution, DirectDistribution, FullSyncDistribution, LastSyncDistribution))
            require(resolution, destination, (CandidateDestination, MemberDestination, CommunityDestination, SubjectiveDestination))
        elif isinstance(resolution, LinearResolution):
            require(resolution, authentication, (MemberAuthentication, MultiMemberAuthentication))
            require(resolution, distribution, (RelayDistribution, DirectDistribution, FullSyncDistribution, LastSyncDistribution))
            require(resolution, destination, (CandidateDestination, MemberDestination, CommunityDestination, SubjectiveDestination))
        elif isinstance(resolution, DynamicResolution):
            pass
        else:
            raise ValueError("%s is not supported" % resolution.__class_.__name__)

        if isinstance(distribution, RelayDistribution):
            require(distribution, authentication, (NoAuthentication, MemberAuthentication, MultiMemberAuthentication))
            require(distribution, resolution, (PublicResolution, LinearResolution, DynamicResolution))
            require(distribution, destination, (CandidateDestination, MemberDestination))
        elif isinstance(distribution, DirectDistribution):
            require(distribution, authentication, (NoAuthentication, MemberAuthentication, MultiMemberAuthentication))
            require(distribution, resolution, (PublicResolution, LinearResolution, DynamicResolution))
            require(distribution, destination, (CandidateDestination, MemberDestination, CommunityDestination))
        elif isinstance(distribution, FullSyncDistribution):
            require(distribution, authentication, (MemberAuthentication, MultiMemberAuthentication))
            require(distribution, resolution, (PublicResolution, LinearResolution, DynamicResolution))
            require(distribution, destination, (CommunityDestination, SubjectiveDestination))
            if isinstance(authentication, MultiMemberAuthentication) and distribution.enable_sequence_number:
                raise ValueError("%s may not be used with %s when sequence numbers are enabled" % (distribution.__class__.__name__, authentication.__class__.__name__))
        elif isinstance(distribution, LastSyncDistribution):
            require(distribution, authentication, (MemberAuthentication, MultiMemberAuthentication))
            require(distribution, resolution, (PublicResolution, LinearResolution, DynamicResolution))
            require(distribution, destination, (CommunityDestination, SubjectiveDestination))
        else:
            raise ValueError("%s is not supported" % distribution.__class_.__name__)

        if isinstance(destination, CandidateDestination):
            require(destination, authentication, (NoAuthentication, MemberAuthentication, MultiMemberAuthentication))
            require(destination, resolution, (PublicResolution, LinearResolution, DynamicResolution))
            require(destination, distribution, (RelayDistribution, DirectDistribution))
        elif isinstance(destination, MemberDestination):
            require(destination, authentication, (NoAuthentication, MemberAuthentication, MultiMemberAuthentication))
            require(destination, resolution, (PublicResolution, LinearResolution, DynamicResolution))
            require(destination, distribution, (RelayDistribution, DirectDistribution))
        elif isinstance(destination, CommunityDestination):
            require(destination, authentication, (NoAuthentication, MemberAuthentication, MultiMemberAuthentication))
            require(destination, resolution, (PublicResolution, LinearResolution, DynamicResolution))
            require(destination, distribution, (DirectDistribution, FullSyncDistribution, LastSyncDistribution))
        elif isinstance(destination, SubjectiveDestination):
            require(destination, authentication, (MemberAuthentication, MultiMemberAuthentication))
            require(destination, resolution, (PublicResolution, LinearResolution, DynamicResolution))
            require(destination, distribution, (FullSyncDistribution, LastSyncDistribution))
        else:
            raise ValueError("%s is not supported" % destination.__class_.__name__)

        return True
