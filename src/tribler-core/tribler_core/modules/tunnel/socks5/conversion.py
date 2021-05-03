# Some constants used in the RFC 1928 specification
import logging
import socket
import struct

from ipv8.messaging.interfaces.udp.endpoint import DomainAddress, UDPv4Address
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.messaging.serialization import DefaultStruct, ListOf, Serializer

SOCKS_VERSION = 0x05

SOCKS_AUTH_ANON = 0x00
SOCKS_AUTH_PWD = 0x01

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


@vp_compile
class MethodsRequest(VariablePayload):
    names = ['version', 'methods']
    format_list = ['B', 'list_of_chars']


@vp_compile
class MethodsResponse(VariablePayload):
    names = ['version', 'method']
    format_list = ['B', 'B']


@vp_compile
class CommandRequest(VariablePayload):
    names = ['version', 'cmd', 'rsv', 'destination']
    format_list = ['B', 'B', 'B', 'socks5_address']


@vp_compile
class CommandResponse(VariablePayload):
    names = ['version', 'reply', 'rsv', 'bind']
    format_list = ['B', 'B', 'B', 'socks5_address']


@vp_compile
class UdpPacket(VariablePayload):
    names = ['rsv', 'frag', 'destination', 'data']
    format_list = ['H', 'B', 'socks5_address', 'raw']


class Socks5Address:

    def pack(self, data):
        if isinstance(data, DomainAddress):
            host = data[0].encode()
            return struct.pack('>BB', ADDRESS_TYPE_DOMAIN_NAME, len(host)) + host + struct.pack('>H', data[1])
        if isinstance(data, tuple):
            return struct.pack('>B4sH', ADDRESS_TYPE_IPV4, socket.inet_aton(data[0]), data[1])
        raise InvalidAddressException(f'Could not pack address {data}')

    def unpack(self, data, offset, unpack_list):
        address_type, = struct.unpack_from('>B', data, offset)
        offset += 1

        if address_type == ADDRESS_TYPE_IPV4:
            host = socket.inet_ntoa(data[offset:offset + 4])
            port, = struct.unpack_from('>H', data, offset + 4)
            offset += 6
            address = UDPv4Address(host, port)
        elif address_type == ADDRESS_TYPE_DOMAIN_NAME:
            domain_length, = struct.unpack_from('>B', data, offset)
            offset += 1
            try:
                host = data[offset:offset + domain_length]
                host = host.decode()
            except UnicodeDecodeError as e:
                raise InvalidAddressException(f'Could not decode host {host}') from e
            port, = struct.unpack_from('>H', data, offset + domain_length)
            offset += domain_length + 2
            address = DomainAddress(host, port)
        elif address_type == ADDRESS_TYPE_IPV6:
            raise IPv6AddressError()
        else:
            raise InvalidAddressException(f'Could not unpack address type {address_type}')

        unpack_list.append(address)
        return offset


class InvalidAddressException(Exception):
    pass


class IPv6AddressError(NotImplementedError):
    def __str__(self):
        return "IPV6 support not implemented"


socks5_serializer = Serializer()
socks5_serializer.add_packer('list_of_chars', ListOf(DefaultStruct('>B')))
socks5_serializer.add_packer('socks5_address', Socks5Address())
