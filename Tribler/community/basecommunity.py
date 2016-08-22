import logging

from Tribler.community.serializer.serializer import Serializer
from Tribler.dispersy.authentication import NoAuthentication, MemberAuthentication, DoubleMemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion, BinaryConversion
from Tribler.dispersy.destination import CommunityDestination, CandidateDestination
from Tribler.dispersy.distribution import FullSyncDistribution, LastSyncDistribution, DirectDistribution
from Tribler.dispersy.message import BatchConfiguration, Message
from Tribler.dispersy.payload import Payload
from Tribler.dispersy.resolution import PublicResolution, LinearResolution, DynamicResolution
from Tribler.dispersy.timeline import Timeline


class MessageOptions(object):

    """Authentication, Resolution, Distribution and Destination object
        parameters to send a message with.
    """

    def __init__(self, auth_type, res_type, dist_type, dest_type,
                 auth=(), res=(), dist=(), dest=()):
        """Create a map of objects and initialization parameters.

            :param auth_type: Authentication object
            :param auth: intialization tuple for auth_type
            :param res_type: Resolution object
            :param res: intialization tuple for res_type
            :param dist_type: Distribution object
            :param dist: intialization tuple for dist_type
            :param dest_type: Destination object
            :param dest: intialization tuple for dest_type
        """
        self.auth_type = auth_type
        self.auth = auth
        self.res_type = res_type
        self.res = res
        self.dist_type = dist_type
        self.dist = dist
        self.dest_type = dest_type
        self.dest = dest

    def copy_types(self, auth=(), res=(), dist=(), dest=()):
        """Copy this message's types, clear (or overwrite) its
            parameters.

            :param auth: intialization tuple for auth_type
            :param res: intialization tuple for res_type
            :param dist: intialization tuple for dist_type
            :param dest: intialization tuple for dest_type
        """
        return MessageOptions(self.auth_type, self.res_type, self.dist_type,
                              self.dest_type, auth, res, dist, dest)


class BaseCommunity(Community):

    """Community relying on Protocol Buffers serialization
        instead of manual serialization. Automatically
        forwards incoming messages to 'on_<messagename>'
        handler functions, specified by this class' child.
    """

    def __init__(self, *args, **kwargs):
        super(BaseCommunity, self).__init__(*args, **kwargs)
        self.serializer = Serializer()
        self.message_traversals = {}
        self.delayed_messages = []

    def initialize(self):
        """Allow dynamic changing of meta messages.
        """
        super(BaseCommunity, self).initialize()
        self.meta_message_cache = {}

    def initiate_meta_messages(self):
        """Initialize our parent's meta messages.
            We only define one supermessage, delegating to
            our handlers on our own terms.
        """
        messages = super(BaseCommunity, self).initiate_meta_messages()
        ourmessages = [Message(self,
                               u"basemsg",
                               MemberAuthentication(),
                               DynamicResolution(LinearResolution(), PublicResolution()),
                               FullSyncDistribution(
                                   enable_sequence_number=True,
                                   synchronization_direction=u"ASC",
                                   priority=128),
                               CommunityDestination(node_count=10),
                               BasePayload(),
                               self.check_basemsg,
                               self.on_basemsg,
                               self.undo_basemsg,
                               batch=BatchConfiguration(0.0))]
        messages.extend(ourmessages)
        return messages

    def initiate_conversions(self):
        """Initialize conversions. Note that we still need
            the default conversion to utilize the Dispersy
            walker (etc.).
        """
        return [DefaultConversion(self), BaseConversion(self, "\x01")]

    def on_basemsg(self, messages):
        """Callback for when a supermessage comes in.
            Delegate it to the appropriate handlers.
            Note that we need to forward the message
            object to each handler to allow it to pull
            Dispersy header info. Doing this any other
            way would either break forward compatibility
            or result in really nasty client code.

            :param messages: Dispersy Message objects
        """
        for message in messages:
            for serialization in message.payload.unserialized:
                if not isinstance(serialization, tuple):
                    continue
                name = serialization[0]
                obj = serialization[1]
                hfunc_name = "on_" + name.lower()
                if hasattr(self, hfunc_name):
                    getattr(self, hfunc_name)(message, obj)

    def check_basemsg(self, messages):
        """Callback for when a supermessage comes in.
            Delegate it to the appropriate handlers.
            Note that we need to forward the message
            object to each handler to allow it to pull
            Dispersy header info. Doing this any other
            way would either break forward compatibility
            or result in really nasty client code.

            :param messages: Dispersy Message objects
        """
        assert len(messages) == 1

        message = messages[0]
        serialization = message.payload.unserialized[0]
        name = serialization[0]
        obj = serialization[1]
        hfunc_name = "check_" + name.lower()

        return getattr(self, hfunc_name)(message, obj) if hasattr(self, hfunc_name) else iter([message])

    def undo_basemsg(self, descriptors, redo=False):
        """Callback for when a supermessage is undone.
            Delegate it to the appropriate handlers.
            Note that we need to forward the message
            object to each handler to allow it to pull
            Dispersy header info. Doing this any other
            way would either break forward compatibility
            or result in really nasty client code.

            :param descriptors: Dispersy Descriptor objects
            :param redo: Redo instead of undo
        """
        for _, _, packet in descriptors:
            message = packet.load_message()
            for serialization in message.payload.unserialized:
                if not isinstance(serialization, tuple):
                    continue
                name = serialization[0]
                obj = serialization[1]
                hfunc_name = "undo_" + name.lower()
                if hasattr(self, hfunc_name):
                    getattr(self, hfunc_name)(message, obj, redo)

    def _produce_message(self, options, message, *args, **kwargs):
        """Generate a supermessage from a set of routing
            options and serialization arguments.

            :param options: MessageOptions for the message
            :param message: the message name to serialize
            :param args: arguments forwarded to the Serializer
            :param kwargs: arguments forwarded to the Serializer
        """
        # Generate a runtime meta definition
        meta = self.get_meta_message(u"basemsg")
        meta._authentication = options.auth_type
        meta._resolution = options.res_type
        meta._distribution = options.dist_type
        meta._destination = options.dest_type
        # Generate serialization
        serialization = self.serializer.serialize(message, *args, **kwargs)
        unserialized = self.serializer.unserialize(
            serialization, False, False, False)
        # Generate the actual message
        message = meta.impl(authentication=options.auth,
                            resolution=options.res,
                            distribution=options.dist,
                            destination=options.dest,
                            payload=(serialization, unserialized))
        return message

    def share(self, options, message, *args, **kwargs):
        """Share a message with the community. This will
            update your own record and forward it to the
            other members of the community.

            :param options: MessageOptions for the message
            :param message: the message name to serialize
            :param args: arguments forwarded to the Serializer
            :param kwargs: arguments forwarded to the Serializer
        """
        self.dispersy.store_update_forward(
            [self._produce_message(options, message, *args, **kwargs)],
            True, True, True)

    def forward(self, options, message, *args, **kwargs):
        """Forward a message to the community. This will
            NOT store the message locally, but only forward
            it to other members of the community.

            :param options: MessageOptions for the message
            :param message: the message name to serialize
            :param args: arguments forwarded to the Serializer
            :param kwargs: arguments forwarded to the Serializer
        """
        self.dispersy.store_update_forward(
            [self._produce_message(options, message, *args, **kwargs)],
            False, False, True)

    def store_update_forward(self, options, message, store, update, forward, *args, **kwargs):
        """
            Share a message with custom store, update and
            forwarding options.

            :param options: MessageOptions for the message
            :param message: the message name to serialize
            :param store: should the message be stored in database
            :param update: should the message be handled by communities
            :param forward: should the message be shared with the community
            :param args: arguments forwarded to the Serializer
            :param kwargs: arguments forwarded to the Serializer
        """
        self.dispersy.store_update_forward(
            [self._produce_message(options, message, *args, **kwargs)],
            store, update, forward)

    def register_traversal(self, message, auth, res, dist, dest):
        """Register a traversal tactic for a certain message
            type. Note that these are just the classes and
            not the implementations.

            :param message: the message name
            :param auth: Authentication object
            :param res: Resolution object
            :param dist: Distribution object
            :param dest: Destination object
        """
        self.message_traversals[
            message] = MessageOptions(auth, res, dist, dest)

    def get_traversal(self, message, auth=(), res=(), dist=(), dest=()):
        """Implement a traversal for a certain message type.
        """
        return self.message_traversals[message].copy_types(auth, res, dist, dest)

    def on_messages(self, messages):
        """Community.on_messages was not made to handle
            message mixing. Therefore we need to handle
            them one-by-one to avoid issues.
        """
        if messages[0].meta.name == u"basemsg":
            processed = 0
            self.delayed_messages.extend(messages)
            self.delayed_messages.sort(key=lambda msg: msg.distribution.global_time)
            remaining = len(self.delayed_messages)
            while remaining > 0:
                message = self.delayed_messages.pop(0)
                delayed_count = -len(self._delayed_key)
                try:
                    processed += super(
                        BaseCommunity, self).on_messages([message])
                except:
                    delayed_count += len(self._delayed_key)
                    if not delayed_count:
                        self.delayed_messages.append(message)
                remaining -= 1
            return processed
        else:
            return super(BaseCommunity, self).on_messages(messages)

    def _on_batch_cache(self, meta, batch):
        """Community._on_batch_cache was not made to handle
            message mixing. Therefore we need to handle
            them one-by-one to avoid issues.
        """
        if meta.name == u"basemsg":
            from Tribler.dispersy.message import DelayPacket, DropPacket
            for candidate, packet, conversion, source in batch:
                try:
                    message = conversion.decode_message(candidate, packet, source=source)
                    self.on_messages([message])
                except DropPacket as drop:
                    self._drop(drop, packet, candidate)
                except DelayPacket as delay:
                    self._dispersy._delay(delay, packet, candidate)
        else:
            super(BaseCommunity, self)._on_batch_cache(meta, batch)

class BasePayload(Payload):

    """ This stores the serialization of data.
        This exists mainly because message.py asserts its
        class' type existence.
    """

    class Implementation(Payload.Implementation):

        def __init__(self, meta, serialized, unserialized):
            super(BasePayload.Implementation, self).__init__(meta)
            self.serialized = serialized
            self.unserialized = unserialized


class BaseConversion(BinaryConversion):

    """Trivial conversion for supermessages.
        Simply consumes all available data for unserialization.
        This could be a Conversion instead of a NoDefBinary-
        Conversion if communities were not dependent on Dispersy
        routing information (Authentication, Distribution, etc.)
    """

    def __init__(self, community, community_version):
        """Register our supermessage and its trivial conversions.

            :param community: the BaseCommunity
        """
        super(BaseConversion, self).__init__(community, community_version)
        self.define_meta_message(
            chr(ord('Q')),
            community.get_meta_message(u"basemsg"),
            self._encode_base,
            self._decode_base)

        self._std_enc_mapping = {
            MemberAuthentication: self._encode_member_authentication,
            DoubleMemberAuthentication: self._encode_double_member_authentication,
            NoAuthentication: self._encode_no_authentication,

            PublicResolution: self._encode_public_resolution,
            LinearResolution: self._encode_linear_resolution,
            DynamicResolution: self._encode_dynamic_resolution,

            FullSyncDistribution: self._encode_full_sync_distribution,
            LastSyncDistribution: self._encode_last_sync_distribution,
            DirectDistribution: self._encode_direct_distribution}

        self._std_dec_mapping = {
            MemberAuthentication: self._decode_member_authentication,
            DoubleMemberAuthentication: self._decode_double_member_authentication,
            NoAuthentication: self._decode_no_authentication,

            DynamicResolution: self._decode_dynamic_resolution,
            LinearResolution: self._decode_linear_resolution,
            PublicResolution: self._decode_public_resolution,

            DirectDistribution: self._decode_direct_distribution,
            FullSyncDistribution: self._decode_full_sync_distribution,
            LastSyncDistribution: self._decode_last_sync_distribution,

            CandidateDestination: self._decode_empty_destination,
            CommunityDestination: self._decode_empty_destination}

    def _encode_base(self, message):
        """The data has already been serialized.
            So yeah, not much going on here.

            :param message: the Message to encode
        """
        return [message.payload.serialized]

    def _decode_base(self, placeholder, offset, data):
        """Consume all available data for unserialization.

            :param placeholder: the Placeholder object
            :param offset: the offset in the data buffer
            :param data: the raw data buffer
        """
        remainder = data[offset:]
        unserialized = self._community.serializer.unserialize(
            remainder, False, False, False)
        # There will only be 1 unserialized message in this
        # implementation, but you never know what the future
        # may hold.
        if not unserialized:
            from binascii import hexlify
            logging.getLogger(self.__class__.__name__)
            self._logger.error(
                "Could not decode any valid messages from incoming data: '%s'",
                hexlify(remainder))
            return offset, None
        else:
            if self._logger.isEnabledFor(logging.DEBUG):
                self._logger.debug("Incoming basemsg identified as " + unserialized[0][0] +
                                   "\n\t" + str(unserialized[0][1]).replace('\n', '\n\t')[:-2])
            return offset + len(remainder), placeholder.meta.payload.implement(remainder, unserialized)

    def define_meta_message(self, byte, meta, encode_payload_func, decode_payload_func):
        """Overwrite method. Allows for dynamic decoding.
            See NoDefBinaryConversion.define_meta_message.
        """
        if meta.name == u"basemsg":
            assert isinstance(byte, str)
            assert len(byte) == 1
            assert isinstance(meta, Message)
            assert 0 < ord(byte) < 255
            assert meta.name not in self._encode_message_map
            assert byte not in self._decode_message_map, "This byte has already been defined (%d)" % ord(
                byte)
            assert callable(encode_payload_func)
            assert callable(decode_payload_func)

            self._encode_message_map[meta.name] = self.EncodeFunctions(byte,
                                                                       self.encode_header,
                                                                       lambda x, y: None,
                                                                       lambda x, y: None,
                                                                       encode_payload_func)
            self._decode_message_map[byte] = self.DecodeFunctions(meta,
                                                                  self.decode_header,
                                                                  lambda x: None,
                                                                  lambda x: None,
                                                                  lambda x: None,
                                                                  decode_payload_func)
        else:
            super(BaseConversion, self).define_meta_message(
                byte, meta, encode_payload_func, decode_payload_func)

    def _get_message_traversal(self, message):
        """Retrieve traversal information from serialized data.
            Can be stored in a message or a placeholder.
        """
        if hasattr(message.payload, "unserialized"):
            return self._community.message_traversals[message.payload.unserialized[0][0]]
        else:
            serializations = self._community.serializer.unserialize(
                message.data, True, True, False)
            try:
                serializations[0][0]
            except TypeError:
                from binascii import hexlify
                logging.getLogger(self.__class__.__name__)
                self._logger.error(
                    "Could not decode a valid message (u\"basemsg\") from incoming data: '%s'",
                    hexlify(message.data))
                return None
            return self._community.message_traversals[serializations[0][0]]

    def encode_header(self, container, message):
        """Given a message, encode its header fields:
            - Authentication
            - Resolution
            - Distribution
           This produces .Implementations.
        """
        traversal = self._get_message_traversal(message)
        if not traversal:
            return
        self._std_enc_mapping[type(traversal.auth_type)](container, message)
        self._std_enc_mapping[type(traversal.res_type)](container, message)
        self._std_enc_mapping[type(traversal.dist_type)](container, message)

    def decode_header(self, placeholder):
        """Given a meta message, initiate a full message,
            by initiating:
            - Authentication
            - Resolution
            - Distribution
            - Destination
        """
        traversal = self._get_message_traversal(placeholder)
        if not traversal:
            return
        basemeta = placeholder.meta
        placeholder.meta = Message(basemeta.community,
                                   basemeta.name,
                                   traversal.auth_type,
                                   traversal.res_type,
                                   traversal.dist_type,
                                   traversal.dest_type,
                                   basemeta.payload,
                                   basemeta.check_callback,
                                   basemeta.handle_callback,
                                   basemeta.undo_callback,
                                   basemeta.batch)
        placeholder.meta._database_id = basemeta.database_id
        self._std_dec_mapping[type(traversal.auth_type)](placeholder)
        self._std_dec_mapping[type(traversal.res_type)](placeholder)
        self._std_dec_mapping[type(traversal.dist_type)](placeholder)
        self._std_dec_mapping[type(traversal.dest_type)](placeholder)
