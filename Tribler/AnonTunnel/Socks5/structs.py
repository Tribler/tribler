import struct
import socket

# Some constants used in the RFC 1928 specification
SOCKS_VERSION = 0x05

ATYP_IPV4 = 0x01
ATYP_DOMAINNAME = 0x03
ATYP_IPV6 = 0x04

REQ_CMD_CONNECT = 0x01
REQ_CMD_BIND = 0x02
REQ_CMD_UDP_ASSOCIATE = 0x03

REP_SUCCEEDED = 0x00
REP_GENERAL_SOCKS_SERVER_FAIL = 0x01
REP_CONNECTION_NOT_ALLOWED_BY_RULESET = 0x02
REP_NETWORK_UNREACHABLE = 0x03
REP_HOST_UNREACHABLE = 0x04
REP_CONNECTION_REFUSED = 0x05
REP_TTL_EXPIRED = 0x06
REP_COMMAND_NOT_SUPPORTED = 0x07
REP_ADDRESS_TYPE_NOT_SUPPORTED = 0x08

class MethodRequest:
    def __init__(self, version, methods):
        self.version = version
        self.methods = methods

class Request:
    def __init__(self,version, cmd, rsv, atyp, destination_address, destination_port):
        self.version = version
        self.cmd = cmd
        self.rsv = rsv
        self.atyp = atyp
        self.destination_address = destination_address
        self.destination_port = destination_port

class UdpRequest:
    def __init__(self,rsv, frag, atyp, destination_address, destination_port, payload ):
        self.rsv = rsv
        self.frag = frag
        self.atyp = atyp
        self.destination_address = destination_address
        self.destination_port = destination_port
        self.payload = payload 
        
def decode_methods_request(offset, data):
    # Check if we have enough bytes
    if len(data) - offset < 2:
        return offset, None 
    
    (version, number_of_methods) = struct.unpack_from("BB", data, offset)

    # We only know how to handle Socks5 protocol
    if not version == SOCKS_VERSION:
        return offset, None

    offset += 2
    
    methods = set([])
    for i in range(number_of_methods):
        methods.add(struct.unpack_from("B", data, offset))
        offset += 1
        
    return offset, MethodRequest(version, methods)
        
def encode_method_selection_message(version, method):
    return struct.pack("BB", version, method)

def encode_address(atyp, address):
    if atyp == ATYP_IPV4:
        data = socket.inet_aton(address)
    elif atyp == ATYP_IPV6:
        raise ValueError("IPv6 not implemented")
    elif atyp == ATYP_DOMAINNAME:
        data = struct.pack("B", len(address))
        data += address
    else:
        raise ValueError("ATYP must be either IPv4, IPv6 or domainname")

    return data

def decode_address(atyp, offset, data):
    if atyp == ATYP_IPV4:
        destination_address = socket.inet_ntoa(data[offset:offset + 4])
        offset += 4
    elif atyp == ATYP_DOMAINNAME:
        domain_length, = struct.unpack_from("B", data, offset)
        offset += 1
        destination_address = data[offset:offset + domain_length]
        offset += domain_length
    elif atyp == ATYP_IPV6:
        return offset, None
    
    return offset, destination_address

def decode_request(orig_offset, data):
    offset = orig_offset
    
    # Check if we have enough bytes
    if len(data) - offset < 4:
        return orig_offset, None 
    
    (version, cmd, rsv, atyp) = struct.unpack_from("BBBB", data, offset)
    offset += 4
    
    assert version == SOCKS_VERSION
    assert rsv == 0
    
    offset, destination_address = decode_address(atyp, offset, data)
    
    # Check if we could decode address, if not bail out
    if not destination_address:
        return orig_offset, None 
    
    # Check if we have enough bytes
    if len(data) - offset < 2:
        return orig_offset, None 
    
    destination_port, = struct.unpack_from("!H", data, offset)
    offset += 2
    
    return offset, Request(version, cmd, rsv, atyp, destination_address, destination_port)
    
def encode_reply(version, rep, rsv, atyp, bind_address, bind_port):
    data = struct.pack("BBBB", version, rep, rsv, atyp)
    
    data += encode_address(atyp, bind_address)
        
    data += struct.pack("!H", bind_port)
    return data

def decode_udp_packet(data):
    """:rtype : UdpRequest"""

    offset = 0
    (rsv, frag, atyp) = struct.unpack_from("!HBB", data, offset)
    offset += 4
    
    offset, destination_address = decode_address(atyp, offset, data)
    
    destination_port, = struct.unpack_from("!H", data, offset)
    offset += 2
    
    payload = data[offset:]
    
    return UdpRequest(rsv, frag, atyp, destination_address, destination_port, payload )


def encode_udp_packet(rsv, frag, atyp, address, port, payload):
    data = struct.pack("!HBB",rsv, frag, atyp)

    data += encode_address(atyp, address)
    data += struct.pack("!H", port)
    data += payload

    return data