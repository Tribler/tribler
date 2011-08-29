"""
This module provides the Authentication policy.

Each Dispersy message that is send has an Authentication policy associated to it.  This policy
dictates how the message is authenticated, i.e. how the message is associated to the sender or
creator of this message.

@author: Boudewijn Schoon
@organization: Technical University Delft
@contact: dispersy@frayja.com
"""

from meta import MetaObject

class Authentication(MetaObject):
    """
    The Authentication baseclass.
    """

    class Implementation(MetaObject.Implementation):
        """
        The implementation of an Authentication policy.
        """

        @property
        def is_signed(self):
            """
            True when the message is (correctly) signed, False otherwise.
            @rtype: bool
            """
            raise NotImplementedError()

        def setup(self, message_impl):
            if __debug__:
                from message import Message
            assert isinstance(message_impl, Message.Implementation)

        @property
        def footprint(self):
            """
            The Authentication footprint.
            @rtype: string
            """
            return "Authentication"

    def setup(self, message):
        """
        Setup the Authentication meta part.

        Setup is called after the meta message is initially created.  This allows us to initialize
        the authentication meta part with, if required, information available to the meta message
        itself.  This gives us access to, among other, the community instance and the other meta
        policies.

        @param message: The meta message.  Note that self is message.authentication.
        @type message: Message
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message)

    def generate_footprint(self):
        """
        Generate a Authentication footprint.
        @return The Authentication footprint.
        @rtype: string
        """
        return "Authentication"

class NoAuthentication(Authentication):
    """
    The NoAuthentication policy can be used when a message is not owned, i.e. signed, by anyone.

    A message that uses the no-authentication policy does not contain any identity information nor a
    signature.  This makes the message smaller --from a storage and bandwidth point of view-- and
    cheaper --from a CPU point of view-- to generate.  However, the message becomes less secure as
    everyone can generate and modify it as they please.  This makes this policy ill suited for
    gossiping purposes.
    """
    class Implementation(Authentication.Implementation):
        @property
        def is_signed(self):
            return True

        @property
        def footprint(self):
            return "NoAuthentication"

    def generate_footprint(self):
        return "NoAuthentication"

class MemberAuthentication(Authentication):
    """
    The MemberAuthentication policy can be used when a message is owned, i.e. signed, bye one
    member.

    A message that uses the member-authentication policy will add an identifier to the message that
    indicates the creator of the message.  This identifier can be either the public key or the sha1
    digest of the public key.  The former is relatively large but uniquely identifies the member,
    while the latter is relatively small but might not uniquely identify the member, although, this
    will uniquely identify the member when combined with the signature.

    Furthermore, a signature over the entire message is appended to ensure that no one else can
    modify the message or impersonate the creator.  Using the default curve, NID-sect233k1, each
    signature will be 58 bytes long.

    The member-authentication policy is used to sign a message, associating it to a specific member.
    This lies at the foundation of Dispersy where specific members are permitted specific actions.
    Furthermore, permissions can only be obtained by having another member, who is allowed to do so,
    give you this permission in the form of a signed message.
    """
    class Implementation(Authentication.Implementation):
        def __init__(self, meta, member, is_signed=False):
            """
            Initialize a new MemberAuthentication.Implementation instance.

            This method should only be called through the MemberAuthentication.implement(member,
            is_signed) method.

            @param meta: The MemberAuthentication instance
            @type meta: MemberAuthentication

            @param member: The member that will own, i.e. sign, this message.
            @type member: Member

            @param is_signed: Indicates if the message is signed or not.  Should only be given when
             decoding a message.
            @type is_signed: bool
            """
            if __debug__:
                from member import Member
            assert isinstance(member, Member)
            assert isinstance(is_signed, bool)
            super(MemberAuthentication.Implementation, self).__init__(meta)
            self._member = member
            self._is_signed = is_signed

        @property
        def encoding(self):
            """
            How the member identifier is encoded (public key or sha1-digest over public key).
            @rtype: string
            @note: This property is obtained from the meta object.
            """
            return self._meta._encoding

        @property
        def member(self):
            """
            The owner of the message.
            @rtype: Member
            """
            return self._member

        @property
        def is_signed(self):
            return self._is_signed

        def set_signature(self, signature):
            self._is_signed = True

        @property
        def footprint(self):
            return "MemberAuthentication:" + self._member.mid.encode("HEX")

    def __init__(self, encoding="sha1"):
        """
        Initialize a new MemberAuthentication instance.

        Depending on the encoding parameter the member is identified in a different way.  The
        options below are available:

         - sha1: where the public key of the member is made into a 20 byte sha1 digest and added to
           the message.

         - bin: where the public key of the member is added to the message, prefixed with its
           length.

        Obviously sha1 results in smaller messages with the disadvantage that the same sha1 digest
        could be mapped to multiple members.  Retrieving the correct member from the sha1 digest is
        handled by dispersy when an incoming message is decoded.

        @param encoding: How the member identifier is encoded (bin or sha1)
        @type encoding: string
        """
        assert isinstance(encoding, str)
        assert encoding in ("bin", "sha1")
        self._encoding = encoding

    @property
    def encoding(self):
        """
        How the member identifier is encoded (bin or sha1).
        @rtype: string
        """
        return self._encoding

    def generate_footprint(self, mids):
        assert isinstance(mids, (tuple, list))
        assert not filter(lambda x: not isinstance(x, str), mids)
        assert not filter(lambda x: not len(x) == 20, mids)
        return "MemberAuthentication:(" + "|".join([mid.encode("HEX") for mid in mids]) + ")"

class MultiMemberAuthentication(Authentication):
    """
    The MultiMemberAuthentication policy can be used when a message needs to be signed by more than
    one members.

    A message that uses the multi-member-authentication policy is signed by two or more member.
    Similar to the member-authentication policy the message contains two or more identifiers where
    the first indicates the creator and the following indicate the members that added their
    signature.

    Dispersy is responsible for obtaining the signatures of the different members and handles this
    using the messages dispersy-signature-request and dispersy-signature-response, defined below.
    Creating a double signed message is performed using the following steps: first Alice creates a
    message (M), note that this message must use the multi-member-authentication policy, and signs
    it herself.  At this point the message consists of the community identifier, the conversion
    identifier, the message identifier, the member identifier for both Alice and Bob, optional
    resolution information, optional distribution information, optional destination information, the
    message payload, and finally the signature for Alice and enough bytes --all set to zero-- to fit
    the signature for Bob.

    This message is consequently wrapped inside a dispersy-signature-request message (R) and send to
    Bob.  When Bob receives this request he is given the choice to add his signature, assuming that
    he does, both a signature and a request identifier will be generated.  The signature signs the
    entire message (M) excluding the two signatures, while the request identifier is a sha1 digest
    over the request message (R).

    Finally Bob sends a dispersy-signature-response message (E), containing the request identifier
    and his signature, back to Alice.  Alice is able to match this specific response to the original
    request and adds Bob's signature to message (M).  This message, which is now double signed, can
    now be disseminated according to its own distribution policy.

    The multi-member-authentication policy can be used to not only double sign, but also sign
    messages with even more members.  The double sign mechanism is, for instance, used by the barter
    community to ensure that two members agree on the amount of bandwidth uploaded by both parties
    before disseminating this information to the rest of the community.
    """
    class Implementation(Authentication.Implementation):
        def __init__(self, meta, members, signatures=[]):
            """
            Initialize a new MultiMemberAuthentication.Implementation instance.

            This methos should only be called through the MemberAuthentication.implement(members,
            signatures) method.

            @param members: The members that will need to sign this message, in this order.  The
             first member will considered the owner of the message.
            @type members: list containing Member instances

            @param signatures: The available, and verified, signatures for each member.  Should only
             be given when decoding a message.
            @type signatures: list containing strings
            """
            if __debug__:
                from member import Member
            assert isinstance(members, list), type(members)
            assert not filter(lambda x: not isinstance(x, Member), members)
            assert len(members) == meta._count
            assert isinstance(signatures, list)
            assert not filter(lambda x: not isinstance(x, str), signatures)
            assert not signatures or len(signatures) == meta._count
            super(MultiMemberAuthentication.Implementation, self).__init__(meta)
            self._members = members
            self._regenerate_packet_func = None

            # will contain the list of signatures as they are received
            # from dispersy-signature-response messages
            if signatures:
                self._signatures = signatures
            else:
                self._signatures = [""] * meta._count

        @property
        def count(self):
            """
            By how many members this message is, or should be, signed.
            @rtype: int or long
            @note: This property is obtained from the meta object.
            """
            return self._meta._count

        @property
        def allow_signature_func(self):
            """
            The function that is called whenever a dispersy-signature-request is received.
            @rtype: callable function
            @note: This property is obtained from the meta object.
            """
            return self._meta._allow_signature_func

        @property
        def member(self):
            """
            The message owner, i.e. the first member in self.members.
            @rtype: Member
            @note: This property is obtained from the meta object.
            """
            return self._members[0]

        @property
        def members(self):
            """
            The members that sign, of should sign, the message.
            @rtype: list or tuple containing Member instances
            """
            return self._members

        @property
        def signed_members(self):
            """
            The members and their signatures.

            The signed members can be used to see from what members we have a valid signature.  A
            list is given with (signature, Member) tuples, where the signature is either a verified
            signature or an empty string.

            @rtype: list containing (string, Member) tules
            """
            return zip(self._signatures, self._members)

        @property
        def is_signed(self):
            return all(self._signatures)

        def set_signature(self, member, signature):
            """
            Set a verified signature for a specific member.

            This method adds a new signature.  Note that the signature is assumed to be valid at
            this point.  When the message is encoded the new signature will be included.

            @param member: The Member that made the signature.
            @type member: Member

            @param signature: The signature for this message.
            @type signature: string
            """
            #todo: verify the signature
            assert member in self._members
            assert member.signature_length == len(signature)
            self._signatures[self._members.index(member)] = signature
            self._regenerate_packet_func()

        def setup(self, message_impl):
            if __debug__:
                from message import Message
            assert isinstance(message_impl, Message.Implementation)
            self._regenerate_packet_func = message_impl.regenerate_packet

        @property
        def footprint(self):
            return "MultiMemberAuthentication:" + ",".join([member.mid.encode("HEX") for member in self._members])

    def __init__(self, count, allow_signature_func):
        """
        Initialize a new MultiMemberAuthentication instance.

        A message that uses MultiMemberAuthentication is always signed by a fixed number of members,
        this is given by the count parameter.

        When someone wants to create a multi signed message, the Community.create_signature_request
        method can be used.  This will send dispersy-signature-request messages to all Members that
        have not yet signed and will wait until replies are received, or a timeout occurs.

        When a member receives a request to add her signature to a message, the allow_signature_func
        function is called.  When this function returns True a signature is generated and send back
        to the requester.

        @param count: The number of Members required to sign this message.
        @type count: int

        @param allow_signature_func: The function that is called when a signature request is
         received.  Must return True to add a signature, False not to.
        @type allow_signature_func: callable function
        """
        assert isinstance(count, int)
        assert hasattr(allow_signature_func, "__call__"), "ALLOW_SIGNATURE_FUNC must be callable"
        self._count = count
        self._allow_signature_func = allow_signature_func

    @property
    def count(self):
        """
        By how many members this message is, or should be, signed.
        @rtype: int or long
        """
        return self._count

    @property
    def allow_signature_func(self):
        """
        The function that is called whenever a dispersy-signature-request is received.
        @rtype: callable function
        """
        return self._allow_signature_func

    def generate_footprint(self, *midss):
        assert isinstance(midss, (tuple, list))
        assert len(midss) == self._count
        if __debug__:
            for mids in midss:
                assert not filter(lambda x: not isinstance(x, str), mids)
                assert not filter(lambda x: not len(x) == 20, mids)
        return "MultiMemberAuthentication:" + ",".join(["(" + "|".join([mid.encode("HEX") for mid in mids]) + ")" for mids in midss])
