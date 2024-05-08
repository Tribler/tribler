from __future__ import annotations

import logging
import socket
import struct
from typing import Any, Union

from ipv8.messaging.interfaces.udp.endpoint import DomainAddress, UDPv4Address
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.messaging.serialization import DefaultStruct, ListOf, Packer, Serializer

# Some constants used in the RFC 1928 specification
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
    """
    A request for supported methods.
    """

    names = ["version", "methods"]
    format_list = ["B", "list_of_chars"]

    version: int
    methods: list[int]


@vp_compile
class MethodsResponse(VariablePayload):
    """
    A response for supported methods.
    """

    names = ["version", "method"]
    format_list = ["B", "B"]

    version: int
    method: int


@vp_compile
class CommandRequest(VariablePayload):
    """
    A request for commands to be executed.
    """

    names = ["version", "cmd", "rsv", "destination"]
    format_list = ["B", "B", "B", "socks5_address"]

    version: int
    cmd: int
    rsv: int
    destination: DomainAddress | UDPv4Address


@vp_compile
class CommandResponse(VariablePayload):
    """
    A reply to share the result of (an attempt at) executing a command.
    """

    names = ["version", "reply", "rsv", "bind"]
    format_list = ["B", "B", "B", "socks5_address"]

    version: int
    reply: int
    rsv: int
    destination: DomainAddress | UDPv4Address


@vp_compile
class UdpPacket(VariablePayload):
    """
    A general wrapper for UDP packets.
    """

    names = ["rsv", "frag", "destination", "data"]
    format_list = ["H", "B", "socks5_address", "raw"]

    rsv: int
    frag: int
    destination: DomainAddress | UDPv4Address
    data: bytes


class Socks5Address(Packer[Union[DomainAddress, tuple], Any]):
    """
    A socks5 address data packer.
    """

    def pack(self, data: DomainAddress | tuple) -> bytes:
        """
        Pack the given data.

        :raises InvalidAddressException: if the data could not be packed.
        """
        if isinstance(data, DomainAddress):
            host = data[0].encode()
            return struct.pack(">BB", ADDRESS_TYPE_DOMAIN_NAME, len(host)) + host + struct.pack(">H", data[1])
        if isinstance(data, tuple):
            return struct.pack(">B4sH", ADDRESS_TYPE_IPV4, socket.inet_aton(data[0]), data[1])
        msg = f"Could not pack address {data}"
        raise InvalidAddressException(msg)

    def unpack(self, data: bytes, offset: int, unpack_list: list, *args: Any) -> int:  # noqa: ANN401
        """
        Unpack the given bytes to an address.
        """
        address_type, = struct.unpack_from(">B", data, offset)
        offset += 1

        if address_type == ADDRESS_TYPE_IPV4:
            host = socket.inet_ntoa(data[offset:offset + 4])
            port, = struct.unpack_from(">H", data, offset + 4)
            offset += 6
            address = UDPv4Address(host, port)
        elif address_type == ADDRESS_TYPE_DOMAIN_NAME:
            domain_length, = struct.unpack_from(">B", data, offset)
            offset += 1
            host = ""
            try:
                host = data[offset:offset + domain_length].decode()
            except UnicodeDecodeError as e:
                msg = f"Could not decode host {host}"
                raise InvalidAddressException(msg) from e
            port, = struct.unpack_from(">H", data, offset + domain_length)
            offset += domain_length + 2
            address = DomainAddress(host, port)
        elif address_type == ADDRESS_TYPE_IPV6:
            raise IPv6AddressError
        else:
            msg = f"Could not unpack address type {address_type}"
            raise InvalidAddressException(msg)

        unpack_list.append(address)
        return offset


class InvalidAddressException(Exception):
    """
    An address could not be packed or unpacked.
    """


class IPv6AddressError(NotImplementedError):
    """
    An attempt was made to unpack an IPv6 address.
    """

    def __str__(self) -> str:
        """
        Get the textual representation of this error.
        """
        return "IPV6 support not implemented"


socks5_serializer = Serializer()
socks5_serializer.add_packer("list_of_chars", ListOf(DefaultStruct(">B")))
socks5_serializer.add_packer("socks5_address", Socks5Address())
