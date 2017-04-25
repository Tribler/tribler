import struct
from binascii import hexlify

from .exception import InvalidStringException, InvalidPacketException, InvalidOptionException

# OPCODE
OPCODE_RRQ = 1
OPCODE_WRQ = 2
OPCODE_DATA = 3
OPCODE_ACK = 4
OPCODE_ERROR = 5
OPCODE_OACK = 6

# supported options
OPTIONS = ("blksize", "timeout", "tsize", "checksum")

# error codes and messages
ERROR_DICT = {
    0: "Not defined, see error message (if any).",
    1: "File not found",
    2: "Access violation",
    3: "Disk full or allocation exceeded",
    4: "Illegal TFTP operation",
    5: "Unknown transfer ID",
    6: "File already exists",
    7: "No such user",
    8: "Failed to negotiate options",
    50: "Session ID already exists",
}


def _get_string(buff, start_idx):
    """ Gets a zero-terminated string from a given buffer.
    :param buff: The buffer.
    :param start_idx: The index to start from.
    :return: A (str, idx) tuple that has the zero-terminated string and the next index.
    """
    str_data = ""
    next_idx = start_idx + 1
    got_end = False
    for c in buff[start_idx:]:
        if ord(c) == 0:
            got_end = True
            break
        str_data += c
        next_idx += 1

    if not got_end:
        raise InvalidStringException()
    return str_data, next_idx


def _decode_options(packet, buff, start_idx):
    """ Decodes options from a given packet buffer.
    :param packet: The packet dictionary to use.
    :param buff: The packet buffer.
    :param start_idx: The index to start from.
    :return: None
    """
    packet['options'] = {}
    idx = start_idx
    while idx < len(buff):
        option, idx = _get_string(buff, idx)
        value, idx = _get_string(buff, idx)
        if option == "":
            raise InvalidPacketException(u"Empty option")
        if value == "":
            raise InvalidPacketException(u"Empty value for option[%s]" % repr(option))

        packet['options'][option] = value

    # validate options and convert them to proper format
    for k, v in packet['options'].items():
        if k not in OPTIONS:
            raise InvalidOptionException(u"Unknown option[%s]" % repr(k))

        # blksize, timeout, and tsize are all integers
        try:
            if k in ("blksize", "timeout", "tsize"):
                packet['options'][k] = int(v)
            else:
                packet['options'][k] = v
        except ValueError:
            raise InvalidOptionException(u"Invalid value for option %s: %s" % (repr(k), repr(v)))


def _decode_rrq_wrq(packet, packet_buff, offset):
    """ Decodes a RRQ/WRQ packet.
    :param packet: The packet dictionary.
    :param packet_buff: The packet buffer.
    :return: The decoded packet as a dictionary.
    """
    # get file_name and mode
    file_name, idx = _get_string(packet_buff, offset)

    packet['file_name'] = file_name

    # get options
    _decode_options(packet, packet_buff, idx)
    return packet


def _decode_data(packet, packet_buff, offset):
    """ Decodes a DATA packet.
    :param packet: The packet dictionary.
    :param packet_buff: The packet buffer.
    :return: The decoded packet as a dictionary.
    """
    # get block number and data
    if len(packet_buff) < offset + 2:
        raise InvalidPacketException(u"DATA packet too small (<4): %s" % repr(packet_buff))
    block_number, = struct.unpack_from("!H", packet_buff, offset)
    data = packet_buff[offset + 2:]

    packet['block_number'] = block_number
    packet['data'] = data

    return packet


def _decode_ack(packet, packet_buff, offset):
    """ Decodes a ACK packet.
    :param packet: The packet dictionary.
    :param packet_buff: The packet buffer.
    :return: The decoded packet as a dictionary.
    """
    # get block number
    if len(packet_buff) != offset + 2:
        raise InvalidPacketException(u"ACK packet has invalid size (!=%s): %s" % (offset + 2, hexlify(packet_buff)))
    block_number, = struct.unpack_from("!H", packet_buff, offset)

    packet['block_number'] = block_number

    return packet


def _decode_error(packet, packet_buff, offset):
    """ Decodes a ERROR packet.
    :param packet: The packet dictionary.
    :param packet_buff: The packet buffer.
    :return: The decoded packet as a dictionary.
    """
    if len(packet_buff) < offset + 3:
        raise InvalidPacketException(u"ERROR packet too small (<%s): %s" % (offset + 3, hexlify(packet_buff)))
    error_code, = struct.unpack_from("!H", packet_buff, offset)
    error_msg, idx = _get_string(packet_buff, offset + 2)

    if not error_msg:
        raise InvalidPacketException(u"ERROR packet has empty error message: %s" % hexlify(packet_buff))
    if idx != len(packet_buff):
        raise InvalidPacketException(u"Invalid ERROR packet: %s" % hexlify(packet_buff))

    packet['error_code'] = error_code
    packet['error_msg'] = error_msg

    return packet


def _decode_oack(packet, packet_buff, offset):
    """ Decodes a OACK packet.
    :param packet: The packet dictionary.
    :param packet_buff: The packet buffer.
    :return: The decoded packet as a dictionary.
    """
    # get block number and data
    _decode_options(packet, packet_buff, offset)

    return packet


PACKET_DECODE_DICT = {
    OPCODE_RRQ: _decode_rrq_wrq,
    OPCODE_WRQ: _decode_rrq_wrq,
    OPCODE_DATA: _decode_data,
    OPCODE_ACK: _decode_ack,
    OPCODE_ERROR: _decode_error,
    OPCODE_OACK: _decode_oack,
}


# ===================================================================================
# Public APIs for encoding and decoding
# ===================================================================================
def decode_packet(packet_buff):
    """ Decodes a packet binary string into a packet dictionary.
    :param packet_buff: The packet binary string.
    :return: The decoded packet dictionary.
    """
    # get the opcode
    if len(packet_buff) < 4:
        raise InvalidPacketException(u"Packet too small (<4): %s" % hexlify(packet_buff))
    opcode, session_id = struct.unpack_from("!HH", packet_buff, 0)

    if opcode not in PACKET_DECODE_DICT:
        raise InvalidPacketException(u"Invalid opcode: %s" % opcode)

    # decode the packet
    packet = {'opcode': opcode,
              'session_id': session_id}
    return PACKET_DECODE_DICT[opcode](packet, packet_buff, 4)


def encode_packet(packet):
    """ Encodes a packet dictionary into a binary string.
    :param packet: The packet dictionary.
    :return: The encoded packet buffer.
    """
    # get block number and data
    packet_buff = struct.pack("!HH", packet['opcode'], packet['session_id'])
    if packet['opcode'] in (OPCODE_RRQ, OPCODE_WRQ):
        packet_buff += packet['file_name'] + "\x00"

        for k, v in packet['options'].iteritems():
            packet_buff += "%s\x00%s\x00" % (k, v)

    elif packet['opcode'] == OPCODE_DATA:
        packet_buff += struct.pack("!H", packet['block_number'])
        packet_buff += packet['data']

    elif packet['opcode'] == OPCODE_ACK:
        packet_buff += struct.pack("!H", packet['block_number'])

    elif packet['opcode'] == OPCODE_ERROR:
        packet_buff += struct.pack("!H", packet['error_code'])
        packet_buff += packet['error_msg'] + "\x00"

    elif packet['opcode'] == OPCODE_OACK:
        for k, v in packet['options'].iteritems():
            packet_buff += "%s\x00%s\x00" % (k, v)

    return packet_buff
