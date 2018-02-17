# Some constants used in the RFC 1928 specification
import logging
import socket
import struct

SOCKS_VERSION = 0x05

ADDRESS_TYPE_IPV4 = 0x01
ADDRESS_TYPE_DOMAIN_NAME = 0x03
ADDRESS_TYPE_IPV6 = 0x04

REQ_CMD_CONNECT = 0x01
REQ_CMD_BIND = 0x02
REQ_CMD_UDP_ASSOCIATE = 0x03

REP_SUCCEEDED = 0x00
REP_GENERAL_SOCKS_SERVER_FAIL = 0x01
REP_CONNECTION_NOT_ALLOWED_BY_RULE_SET = 0x02
REP_NETWORK_UNREACHABLE = 0x03
REP_HOST_UNREACHABLE = 0x04
REP_CONNECTION_REFUSED = 0x05
REP_TTL_EXPIRED = 0x06
REP_COMMAND_NOT_SUPPORTED = 0x07
REP_ADDRESS_TYPE_NOT_SUPPORTED = 0x08


logger = logging.getLogger(__name__)


class MethodRequest(object):

    def __init__(self, version, methods):
        self.version = version
        self.methods = methods


class Request(object):

    def __init__(self, version, cmd, rsv, address_type, destination_address,
                 destination_port):
        self.version = version
        self.cmd = cmd
        self.rsv = rsv
        self.address_type = address_type
        self.destination_host = destination_address
        self.destination_port = destination_port

    @property
    def destination(self):
        """
        The destination address as a tuple
        @rtype: (str, int)
        """
        return self.destination_host, self.destination_port


class UdpRequest(object):

    """

    @param rsv: the reserved bits in the SOCKS protocol
    @param frag:
    @param address_type: whether we deal with an IPv4 or IPv6 address
    @param str destination_address: the destination host
    @param int destination_port: the destination port
    @param str payload: the payload
    """

    def __init__(self, rsv, frag, address_type, destination_address,
                 destination_port, payload):
        self.rsv = rsv
        self.frag = frag
        self.address_type = address_type
        self.destination_host = destination_address
        self.destination_port = destination_port
        self.payload = payload

    @property
    def destination(self):
        """
        The destination address as a tuple
        @rtype: (str, int)
        """
        return self.destination_host, self.destination_port


def decode_methods_request(offset, data):
    """
    Try to decodes a METHOD request
    @param int offset: the offset to start in the data
    @param str data: the serialised data to decode from
    @return: Tuple (offset, None) on failure, else (new_offset, MethodRequest)
    @rtype: (int, None|MethodRequest)
    """
    # Check if we have enough bytes
    if len(data) - offset < 2:
        return offset, None

    (version, number_of_methods) = struct.unpack_from("!BB", data, offset)

    offset += 2

    methods = set([])
    for i in range(number_of_methods):
        method, = struct.unpack_from("!B", data, offset)
        methods.add(method)
        offset += 1

    return offset, MethodRequest(version, methods)


def encode_method_selection_message(version, method):
    """
    Serialise a Method Selection message
    @param version: the SOCKS5 version
    @param method: the authentication method to select
    @return: the serialised format
    @rtype: str
    """
    return struct.pack("!BB", version, method)


def __encode_address(address_type, address):
    if address_type == ADDRESS_TYPE_IPV4:
        data = socket.inet_aton(address)
    elif address_type == ADDRESS_TYPE_IPV6:
        raise IPV6AddrError()
    elif address_type == ADDRESS_TYPE_DOMAIN_NAME:
        data = struct.pack("!B", len(address)) + address
    else:
        raise ValueError(
            "address_type must be either IPv4, IPv6 or a domain name")

    return data


def __decode_address(address_type, offset, data):
    if address_type == ADDRESS_TYPE_IPV4:
        destination_address = socket.inet_ntoa(data[offset:offset + 4])
        offset += 4
    elif address_type == ADDRESS_TYPE_DOMAIN_NAME:
        domain_length, = struct.unpack_from("!B", data, offset)
        offset += 1
        destination_address = data[offset:offset + domain_length]
        offset += domain_length
    elif address_type == ADDRESS_TYPE_IPV6:
        raise IPV6AddrError()
    else:
        logger.error("Unsupported address type %r", address_type)
        return offset, None

    return offset, destination_address


def decode_request(orig_offset, data):
    """
    Try to decode a SOCKS5 request
    @param int orig_offset: the offset to start decoding in the data
    @param str data: the raw data
    @return: tuple (new_offset, Request) or (original_offset, None) on failure
    @rtype: (int, Request|None)
    """
    offset = orig_offset

    # Check if we have enough bytes
    if len(data) - offset < 4:
        return orig_offset, None

    version, cmd, rsv, address_type = struct.unpack_from("!BBBB", data, offset)
    offset += 4

    assert version == SOCKS_VERSION, (version, SOCKS_VERSION)
    assert rsv == 0

    offset, destination_address = __decode_address(address_type, offset, data)

    # Check if we could decode address, if not bail out
    if not destination_address:
        return orig_offset, None

        # Check if we have enough bytes
    if len(data) - offset < 2:
        return orig_offset, None

    destination_port, = struct.unpack_from("!H", data, offset)
    offset += 2

    return offset, Request(version, cmd, rsv, address_type,
                           destination_address, destination_port)


def encode_reply(version, rep, rsv, address_type, bind_address, bind_port):
    """
    Encode a REPLY
    @param int version: SOCKS5 version
    @param int rep: the response
    @param int rsv: reserved bytes
    @param address_type: the address type of the bind address
    @param bind_address: the bind address host
    @param bind_port: the bind address port
    @return:
    """
    data = struct.pack("BBBB", version, rep, rsv, address_type)

    data += __encode_address(address_type, bind_address)

    data += struct.pack("!H", bind_port)
    return data


def decode_udp_packet(data):
    """
    Decodes a SOCKS5 UDP packet
    @param str data: the raw packet data
    @return: An UdpRequest object containing the parsed data
    @rtype: UdpRequest
    """
    offset = 0
    (rsv, frag, address_type) = struct.unpack_from("!HBB", data, offset)
    offset += 4

    offset, destination_address = __decode_address(address_type, offset, data)

    destination_port, = struct.unpack_from("!H", data, offset)
    offset += 2

    payload = data[offset:]

    return UdpRequest(rsv, frag, address_type, destination_address,
                      destination_port, payload)


def encode_udp_packet(rsv, frag, address_type, address, port, payload):
    """
    Encodes a SOCKS5 UDP packet
    @param rsv: reserved bytes
    @param frag: fragment
    @param address_type: the address's type
    @param address: address host
    @param port: address port
    @param payload: the original UDP payload
    @return: serialised byte string
    @rtype: str
    """
    strings = [
        struct.pack("!HBB", rsv, frag, address_type),
        __encode_address(address_type, address),
        struct.pack("!H", port),
        payload
    ]

    return ''.join(strings)


class IPV6AddrError(NotImplementedError):
    def __str__(self):
        return "IPV6 support not implemented"
