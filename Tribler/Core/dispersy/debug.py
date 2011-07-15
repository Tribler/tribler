import socket

from authentication import NoAuthentication
from bloomfilter import BloomFilter
from crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from destination import CommunityDestination, AddressDestination
from distribution import DirectDistribution, LastSyncDistribution, FullSyncDistribution
from dprint import dprint
from member import MyMember, Member
from member import PrivateMember, MyMember
from message import Message
from payload import MissingSequencePayload, SyncPayload, SignatureResponsePayload, CandidateRequestPayload, IdentityPayload, SimilarityPayload
from resolution import PublicResolution, LinearResolution

class DebugOnlyMembers(object):
    _singleton_instances = {}

    @property
    def database_id(self):
        return Member(self.public_key).database_id

class DebugPrivateMember(DebugOnlyMembers, PrivateMember):
    pass

class DebugMyMember(DebugOnlyMembers, MyMember):
    pass

class Node(object):
    _socket_range = (8000, 8999)
    _socket_pool = {}
    _socket_counter = 0

    def __init__(self):
        self._socket = None
        self._my_member = None
        self._community = None

    @property
    def socket(self):
        return self._socket

    def init_socket(self):
        assert self._socket is None
        port = Node._socket_range[0] + Node._socket_counter % (Node._socket_range[1] - Node._socket_range[0])
        Node._socket_counter += 1

        if not port in Node._socket_pool:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 870400)
            s.setblocking(False)
            s.settimeout(0.0)
            while True:
                try:
                    s.bind(("localhost", port))
                except socket.error, error:
                    port = Node._socket_range[0] + Node._socket_counter % (Node._socket_range[1] - Node._socket_range[0])
                    Node._socket_counter += 1
                    continue
                break

            Node._socket_pool[port] = s
            if __debug__: dprint("create socket ", port)

        elif __debug__:
            dprint("reuse socket ", port, level="warning")

        self._socket = Node._socket_pool[port]

    @property
    def my_member(self):
        return self._my_member

    def init_my_member(self, bits=None, sync_with_database=None, candidate=True, identity=True):
        assert bits is None, "The parameter bits is depricated and must be None"
        assert sync_with_database is None, "The parameter sync_with_database is depricated and must be None"

        ec = ec_generate_key(u"low")
        self._my_member = DebugPrivateMember.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec), sync_with_database=False)

        if identity:
            # update identity information
            assert self._socket, "Socket needs to be set to candidate"
            assert self._community, "Community needs to be set to candidate"
            source_address = self._socket.getsockname()
            message = self.create_dispersy_identity_message(source_address, 2)
            self.give_message(message)

        if candidate:
            # update candidate information
            assert self._socket, "Socket needs to be set to candidate"
            assert self._community, "Community needs to be set to candidate"
            source_address = self._socket.getsockname()
            destination_address = self._community._dispersy.socket.get_address()
            message = self.create_dispersy_candidate_request_message(source_address, destination_address, self._community.get_conversion().version, [], 1)
            self.give_message(message)

    @property
    def community(self):
        return self._community

    def set_community(self, community):
        self._community = community

    def encode_message(self, message):
        assert isinstance(message, Message.Implementation)
        tmp_member = self._community._my_member
        self._community._my_member= self._my_member
        try:
            packet = self._community.get_conversion().encode_message(message)
        finally:
            self._community._my_member = tmp_member
        return packet

    def give_packet(self, packet, verbose=False, cache=False):
        assert isinstance(packet, str)
        assert isinstance(verbose, bool)
        if verbose: dprint("giving ", len(packet), " bytes")
        self._community.dispersy.on_incoming_packets([(self.socket.getsockname(), packet)], cache=cache)
        return packet

    def give_packets(self, packets, verbose=False, cache=False):
        assert isinstance(packets, list)
        assert isinstance(verbose, bool)
        if verbose: dprint("giving ", sum(len(packet) for packet in packets), " bytes")
        address = self.socket.getsockname()
        self._community.dispersy.on_incoming_packets([(address, packet) for packet in packets], cache=cache)
        return packets

    def give_message(self, message, verbose=False, cache=False):
        assert isinstance(message, Message.Implementation)
        assert isinstance(verbose, bool)
        self.encode_message(message)
        if verbose: dprint("giving ", message.name, " (", len(message.packet), " bytes)")
        self.give_packet(message.packet, verbose=verbose, cache=cache)
        return message

    def give_messages(self, messages, verbose=False, cache=False):
        assert isinstance(messages, list)
        assert isinstance(verbose, bool)
        map(self.encode_message, messages)
        if verbose: dprint("giving ", len(messages), " messages (", sum(len(message.packet) for message in messages), " bytes)")
        self.give_packets([message.packet for message in messages], verbose=verbose, cache=cache)
        return messages

    def send_packet(self, packet, address, verbose=False):
        assert isinstance(packet, str)
        assert isinstance(address, tuple)
        assert isinstance(verbose, bool)
        if verbose: dprint(len(packet), " bytes to ", address[0], ":", address[1])
        self._socket.sendto(packet, address)
        return packet

    def send_message(self, message, address, verbose=False):
        assert isinstance(message, Message.Implementation)
        assert isinstance(address, tuple)
        assert isinstance(verbose, bool)
        self.encode_message(message)
        if verbose: dprint(message.name, " (", len(message.packet), " bytes) to ", address[0], ":", address[1])
        self.send_packet(message.packet, address)
        return message

    def drop_packets(self):
        while True:
            try:
                packet, address = self._socket.recvfrom(10240)
            except:
                break

            dprint("droped ", len(packet), " bytes from ", address[0], ":", address[1])

    def receive_packet(self, timeout=None, addresses=None, packets=None):
        assert timeout is None, "The parameter TIMEOUT is depricated and must be None"
        assert isinstance(addresses, (type(None), list))
        assert isinstance(packets, (type(None), list))

        while True:
            try:
                packet, address = self._socket.recvfrom(10240)
            except:
                raise

            if not (addresses is None or address in addresses or (address[0] == "127.0.0.1" and ("0.0.0.0", address[1]) in addresses)):
                continue

            if not (packets is None or packet in packets):
                continue

            dprint(len(packet), " bytes from ", address[0], ":", address[1])
            return address, packet

    def receive_message(self, timeout=None, addresses=None, packets=None, message_names=None, payload_types=None, distributions=None, destinations=None):
        assert timeout is None, "The parameter TIMEOUT is depricated and must be None"
        assert isinstance(addresses, (type(None), list))
        assert isinstance(packets, (type(None), list))
        assert isinstance(message_names, (type(None), list))
        assert isinstance(payload_types, (type(None), list))
        assert isinstance(distributions, (type(None), list))
        assert isinstance(destinations, (type(None), list))

        while True:
            address, packet = self.receive_packet(timeout, addresses, packets)

            try:
                message = self._community.get_conversion(packet[:22]).decode_message(address, packet)
            except KeyError:
                # not for this community
                dprint("Ignored ", message.name, " (", len(packet), " bytes) from ", address[0], ":", address[1])
                continue

            if not (message_names is None or message.name in message_names):
                dprint("Ignored ", message.name, " (", len(packet), " bytes) from ", address[0], ":", address[1])
                continue

            if not (payload_types is None or message.payload.type in payload_types):
                dprint("Ignored ", message.name, " (", len(packet), " bytes) from ", address[0], ":", address[1])
                continue

            if not (distributions is None or isinstance(message.distribution, distributions)):
                dprint("Ignored ", message.name, " (", len(packet), " bytes) from ", address[0], ":", address[1])
                continue

            if not (destinations is None or isinstance(message.destination, destinations)):
                dprint("Ignored ", message.name, " (", len(packet), " bytes) from ", address[0], ":", address[1])
                continue

            dprint(message.name, " (", len(packet), " bytes) from ", address[0], ":", address[1])
            return address, message

    def create_dispersy_identity_message(self, address, global_time):
        assert isinstance(address, tuple)
        assert len(address) == 2
        assert isinstance(address[0], str)
        assert isinstance(address[1], int)
        assert isinstance(global_time, (int, long))
        meta = self._community.get_meta_message(u"dispersy-identity")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(address))

    def create_dispersy_undo_message(self, message, global_time):
        meta = self._community.get_meta_message(u"dispersy-undo")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(message.authentication.member, message.distribution.global_time, message))

    def create_dispersy_candidate_request_message(self, source_address, destination_address, source_default_conversion, routes, global_time):
        assert isinstance(source_address, tuple)
        assert len(source_address) == 2
        assert isinstance(source_address[0], str)
        assert isinstance(source_address[1], int)
        assert isinstance(destination_address, tuple)
        assert len(destination_address) == 2
        assert isinstance(destination_address[0], str)
        assert isinstance(destination_address[1], int)
        assert isinstance(source_default_conversion, tuple)
        assert len(source_default_conversion) == 2
        assert isinstance(source_default_conversion[0], str)
        assert len(source_default_conversion[0]) == 1
        assert isinstance(source_default_conversion[1], str)
        assert len(source_default_conversion[1]) == 1
        assert isinstance(routes, (tuple, list))
        assert not filter(lambda route: not isinstance(route, tuple), routes)
        assert not filter(lambda route: not len(route) == 2, routes)
        assert not filter(lambda route: not isinstance(route[0], tuple), routes)
        assert not filter(lambda route: not len(route[0]) == 2, routes)
        assert not filter(lambda route: not isinstance(route[0][0], str), routes)
        assert not filter(lambda route: not isinstance(route[0][1], (int, long)), routes)
        assert not filter(lambda route: not isinstance(route[1], float), routes)
        assert isinstance(global_time, (int, long))
        meta = self._community.get_meta_message(u"dispersy-candidate-request")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(destination_address),
                              meta.payload.implement(source_address, destination_address, source_default_conversion, routes))

    def create_dispersy_sync_message(self, time_low, time_high, bloom_packets, global_time):
        assert isinstance(time_low, (int, long))
        assert isinstance(time_high, (int, long))
        assert isinstance(bloom_packets, list)
        assert not filter(lambda x: not isinstance(x, str), bloom_packets)
        assert isinstance(global_time, (int, long))
        bloom_filter = BloomFilter(700, 0.001, prefix="x")
        map(bloom_filter.add, bloom_packets)
        meta = self._community.get_meta_message(u"dispersy-sync")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(time_low, time_high, bloom_filter))

    def create_dispersy_similarity_message(self, cluster, community, similarity, global_time):
        assert isinstance(cluster, int)
        assert 0 < cluster < 2^8, "CLUSTER must fit in one byte"
        assert isinstance(similarity, BloomFilter)
        meta = self._community.get_meta_message(u"dispersy-similarity")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(cluster, similarity))

    def create_dispersy_missing_sequence_message(self, missing_member, missing_message_meta, missing_low, missing_high, global_time, destination_address):
        assert isinstance(missing_member, Member)
        assert isinstance(missing_message_meta, Message)
        assert isinstance(missing_low, (int, long))
        assert isinstance(missing_high, (int, long))
        assert isinstance(global_time, (int, long))
        assert isinstance(destination_address, tuple)
        assert len(destination_address) == 2
        assert isinstance(destination_address[0], str)
        assert isinstance(destination_address[1], int)
        meta = self._community.get_meta_message(u"dispersy-missing-sequence")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(destination_address),
                              meta.payload.implement(missing_member, missing_message_meta, missing_low, missing_high))

    def create_dispersy_signature_request_message(self, message, global_time, destination_member):
        isinstance(message, Message.Implementation)
        isinstance(global_time, (int, long))
        isinstance(destination_member, Member)
        meta = self._community.get_meta_message(u"dispersy-signature-request")
        return meta.implement(meta.authentication.implement(),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(destination_member),
                              meta.payload.implement(message))

    def create_dispersy_signature_response_message(self, request_id, signature, global_time, destination_address):
        assert isinstance(request_id, str)
        assert len(request_id) == 20
        assert isinstance(signature, str)
        assert isinstance(global_time, (int, long))
        assert isinstance(destination_address, tuple)
        assert len(destination_address) == 2
        assert isinstance(destination_address[0], str)
        assert isinstance(destination_address[1], int)
        meta = self._community.get_meta_message(u"dispersy-signature-response")
        return meta.implement(meta.authentication.implement(),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(destination_address),
                              meta.payload.implement(request_id, signature))

    def create_dispersy_subjective_set_message(self, cluster, subjective_set, global_time):
        assert isinstance(cluster, int)
        assert 0 < cluster < 2^8
        assert isinstance(subjective_set, BloomFilter)
        assert isinstance(global_time, (int, long))
        assert global_time > 0
        meta = self._community.get_meta_message(u"dispersy-subjective-set")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(cluster, subjective_set))

    def create_dispersy_missing_message_message(self, missing_member, missing_global_times, global_time, destination_address):
        assert isinstance(missing_member, Member)
        assert isinstance(missing_global_times, list)
        assert not filter(lambda x: not isinstance(x, (int, long)), missing_global_times)
        assert isinstance(global_time, (int, long))
        assert isinstance(destination_address, tuple)
        assert len(destination_address) == 2
        assert isinstance(destination_address[0], str)
        assert isinstance(destination_address[1], int)
        meta = self._community.get_meta_message(u"dispersy-missing-message")
        return meta.implement(meta.authentication.implement(),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(destination_address),
                              meta.payload.implement(missing_member, missing_global_times))
