import socket

from bloomfilter import BloomFilter
from candidate import Candidate, WalkCandidate
from crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from dprint import dprint
from member import Member
from message import Message
from time import time

class DebugOnlyMember(Member):
    pass

class Node(object):
    _socket_range = (8000, 8999)
    _socket_pool = {}
    _socket_counter = 0

    def __init__(self):
        self._socket = None
        self._my_member = None
        self._community = None
        self._dispersy = None

    @property
    def socket(self):
        return self._socket

    @property
    def lan_address(self):
        _, port = self._socket.getsockname()
        return ("127.0.0.1", port)

    @property
    def wan_address(self):
        if self._dispersy:
            host = self._dispersy.wan_address[0]

            if host == "0.0.0.0":
                host = self._dispersy.lan_address[0]

        else:
            host = "0.0.0.0"

        _, port = self._socket.getsockname()
        return (host, port)

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
        assert bits is None, "The parameter bits is deprecated and must be None"
        assert sync_with_database is None, "The parameter sync_with_database is deprecated and must be None"

        ec = ec_generate_key(u"low")
        self._my_member = DebugOnlyMember(ec_to_public_bin(ec), ec_to_private_bin(ec))

        if identity:
            # update identity information
            assert self._socket, "Socket needs to be set to candidate"
            assert self._community, "Community needs to be set to candidate"
            message = self.create_dispersy_identity_message(2)
            self.give_message(message)

        if candidate:
            # update candidate information
            assert self._socket, "Socket needs to be set to candidate"
            assert self._community, "Community needs to be set to candidate"
            message = self.create_dispersy_introduction_request_message(self._community.my_candidate, self.lan_address, self.wan_address, False, u"unknown", None, 1, 1)
            self.give_message(message)

    @property
    def community(self):
        return self._community

    def set_community(self, community):
        self._community = community
        if community:
            self._dispersy = community.dispersy

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
        assert isinstance(cache, bool)
        if verbose: dprint("giving ", len(packet), " bytes")
        self._dispersy.on_socket_endpoint([(self.lan_address, packet)], cache=cache, timestamp=time())
        return packet

    def give_packets(self, packets, verbose=False, cache=False):
        assert isinstance(packets, list)
        assert isinstance(verbose, bool)
        assert isinstance(cache, bool)
        if verbose: dprint("giving ", sum(len(packet) for packet in packets), " bytes")
        self._dispersy.on_socket_endpoint([(self.lan_address, packet) for packet in packets], cache=cache, timestamp=time())
        return packets

    def give_message(self, message, verbose=False, cache=False):
        assert isinstance(message, Message.Implementation)
        assert isinstance(verbose, bool)
        assert isinstance(cache, bool)
        self.encode_message(message)
        if verbose: dprint("giving ", message.name, " (", len(message.packet), " bytes)")
        self.give_packet(message.packet, verbose=verbose, cache=cache)
        return message

    def give_messages(self, messages, verbose=False, cache=False):
        assert isinstance(messages, list)
        assert isinstance(verbose, bool)
        assert isinstance(cache, bool)
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
        assert timeout is None, "The parameter TIMEOUT is deprecated and must be None"
        assert addresses is None or isinstance(addresses, list)
        assert addresses is None or all(isinstance(address, tuple) for address in addresses)
        assert packets is None or isinstance(packets, list)
        assert packets is None or all(isinstance(packet, str) for packet in packsts)

        while True:
            try:
                packet, address = self._socket.recvfrom(10240)
            except:
                raise

            if not (addresses is None or address in addresses or (address[0] == "127.0.0.1" and ("0.0.0.0", address[1]) in addresses)):
                continue

            if not (packets is None or packet in packets):
                continue

            candidate = WalkCandidate(address, address, address)
            dprint(len(packet), " bytes from ", candidate)
            return candidate, packet

    def receive_message(self, timeout=None, addresses=None, packets=None, message_names=None, payload_types=None, distributions=None, destinations=None):
        assert timeout is None, "The parameter TIMEOUT is deprecated and must be None"
        assert isinstance(message_names, (type(None), list))
        assert isinstance(payload_types, (type(None), list))
        assert isinstance(distributions, (type(None), list))
        assert isinstance(destinations, (type(None), list))

        while True:
            candidate, packet = self.receive_packet(timeout, addresses, packets)

            try:
                message = self._community.get_conversion(packet[:22]).decode_message(candidate, packet)
            except KeyError:
                # not for this community
                dprint("Ignored ", message.name, " (", len(packet), " bytes) from ", candidate)
                continue

            if not (message_names is None or message.name in message_names):
                dprint("Ignored ", message.name, " (", len(packet), " bytes) from ", candidate)
                continue

            if not (payload_types is None or message.payload.type in payload_types):
                dprint("Ignored ", message.name, " (", len(packet), " bytes) from ", candidate)
                continue

            if not (distributions is None or isinstance(message.distribution, distributions)):
                dprint("Ignored ", message.name, " (", len(packet), " bytes) from ", candidate)
                continue

            if not (destinations is None or isinstance(message.destination, destinations)):
                dprint("Ignored ", message.name, " (", len(packet), " bytes) from ", candidate)
                continue

            dprint(message.name, " (", len(packet), " bytes) from ", candidate)
            return candidate, message

    def create_dispersy_authorize(self, permission_triplets, sequence_number, global_time):
        meta = self._community.get_meta_message(u"dispersy-authorize")
        return meta.impl(authentication=(self._my_member,),
                         distribution=(global_time, sequence_number),
                         payload=(permission_triplets,))

    def create_dispersy_identity_message(self, global_time):
        assert isinstance(global_time, (int, long))
        meta = self._community.get_meta_message(u"dispersy-identity")
        return meta.impl(authentication=(self._my_member,), distribution=(global_time,))

    def create_dispersy_undo_own_message(self, message, global_time, sequence_number):
        assert message.authentication.member == self._my_member, "use create_dispersy_undo_other_message"
        meta = self._community.get_meta_message(u"dispersy-undo-own")
        return meta.impl(authentication=(self._my_member,),
                         distribution=(global_time, sequence_number),
                         payload=(message.authentication.member, message.distribution.global_time, message))

    def create_dispersy_undo_other_message(self, message, global_time, sequence_number):
        assert message.authentication.member != self._my_member, "use create_dispersy_undo_own_message"
        meta = self._community.get_meta_message(u"dispersy-undo-other")
        return meta.impl(authentication=(self._my_member,),
                         distribution=(global_time, sequence_number),
                         payload=(message.authentication.member, message.distribution.global_time, message))

    def create_dispersy_missing_sequence_message(self, missing_member, missing_message_meta, missing_low, missing_high, global_time, destination_candidate):
        assert isinstance(missing_member, Member)
        assert isinstance(missing_message_meta, Message)
        assert isinstance(missing_low, (int, long))
        assert isinstance(missing_high, (int, long))
        assert isinstance(global_time, (int, long))
        assert isinstance(destination_candidate, Candidate)
        meta = self._community.get_meta_message(u"dispersy-missing-sequence")
        return meta.impl(authentication=(self._my_member,),
                         distribution=(global_time,),
                         destination=(destination_candidate,),
                         payload=(missing_member, missing_message_meta, missing_low, missing_high))

    def create_dispersy_signature_request_message(self, message, global_time, destination_member):
        isinstance(message, Message.Implementation)
        isinstance(global_time, (int, long))
        isinstance(destination_member, Member)
        meta = self._community.get_meta_message(u"dispersy-signature-request")
        return meta.impl(distribution=(global_time,),
                         destination=(destination_member,),
                         payload=(message,))

    def create_dispersy_signature_response_message(self, request_id, signature, global_time, destination_candidate):
        assert isinstance(request_id, str)
        assert len(request_id) == 20
        assert isinstance(signature, str)
        assert isinstance(global_time, (int, long))
        assert isinstance(destination_candidate, Candidate)
        meta = self._community.get_meta_message(u"dispersy-signature-response")
        return meta.impl(distribution=(global_time,),
                         destination=(destination_candidate,),
                         payload=(request_id, signature))

    def create_dispersy_subjective_set_message(self, cluster, subjective_set, global_time):
        assert isinstance(cluster, int)
        assert 0 < cluster < 2^8
        assert isinstance(subjective_set, BloomFilter)
        assert isinstance(global_time, (int, long))
        assert global_time > 0
        meta = self._community.get_meta_message(u"dispersy-subjective-set")
        return meta.impl(authentication=(self._my_member,),
                         distribution=(global_time,),
                         payload=(cluster, subjective_set))

    def create_dispersy_missing_message_message(self, missing_member, missing_global_times, global_time, destination_candidate):
        assert isinstance(missing_member, Member)
        assert isinstance(missing_global_times, list)
        assert not filter(lambda x: not isinstance(x, (int, long)), missing_global_times)
        assert isinstance(global_time, (int, long))
        assert isinstance(destination_candidate, Candidate)
        meta = self._community.get_meta_message(u"dispersy-missing-message")
        return meta.impl(distribution=(global_time,),
                         destination=(destination_candidate,),
                         payload=(missing_member, missing_global_times))

    def create_dispersy_missing_proof_message(self, member, global_time):
        assert isinstance(member, Member)
        assert isinstance(global_time, (int, long))
        assert global_time > 0
        meta = self._community.get_meta_message(u"dispersy-missing-proof")
        return meta.impl(distribution=(global_time,), payload=(member, global_time))

    def create_dispersy_introduction_request_message(self, destination, source_lan, source_wan, advice, connection_type, sync, identifier, global_time):
        # TODO assert other arguments
        assert isinstance(destination, WalkCandidate), destination
        if sync:
            assert isinstance(sync, tuple)
            assert len(sync) == 5
            time_low, time_high, modulo, offset, bloom_packets = sync
            assert isinstance(time_low, (int, long))
            assert isinstance(time_high, (int, long))
            assert isinstance(modulo, int)
            assert isinstance(offset, int)
            assert isinstance(bloom_packets, list)
            assert not filter(lambda x: not isinstance(x, str), bloom_packets)
            bloom_filter = BloomFilter(512*8, 0.001, prefix="x")
            map(bloom_filter.add, bloom_packets)
            sync = (time_low, time_high, modulo, offset, bloom_filter)
        assert isinstance(global_time, (int, long))
        meta = self._community.get_meta_message(u"dispersy-introduction-request")
        return meta.impl(authentication=(self._my_member,),
                         destination=(destination,),
                         distribution=(global_time,),
                         payload=(destination.sock_addr, source_lan, source_wan, advice, connection_type, sync, identifier))

