from nose.tools import raises
from Tribler.Core.TFTP.exception import InvalidStringException, InvalidPacketException, InvalidOptionException
from Tribler.Core.TFTP.packet import _get_string, _decode_options, _decode_data, _decode_ack, _decode_error, \
    decode_packet, OPCODE_ERROR, encode_packet
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestTFTPPacket(TriblerCoreTest):
    """
    This class contains tests for the TFTP packet class.
    """

    @raises(InvalidStringException)
    def test_get_string_no_end(self):
        """
        Testing whether the get_string method raises InvalidStringException when no zero terminator is found
        """
        _get_string("", 0)

    @raises(InvalidPacketException)
    def test_decode_options_no_option(self):
        """
        Testing whether decoding the options raises InvalidPacketException if no options are found
        """
        _decode_options({}, "\0a\0", 0)

    @raises(InvalidPacketException)
    def test_decode_options_no_value(self):
        """
        Testing whether decoding the options raises InvalidPacketException if no value is found
        """
        _decode_options({}, "b\0\0", 0)

    @raises(InvalidOptionException)
    def test_decode_options_unknown(self):
        """
        Testing whether decoding the options raises InvalidOptionException if an invalid option is found
        """
        _decode_options({}, "b\0a\0", 0)

    @raises(InvalidOptionException)
    def test_decode_options_invalid(self):
        """
        Testing whether decoding the options raises InvalidOptionException if an invalid option is found
        """
        _decode_options({}, "blksize\0a\0", 0)

    @raises(InvalidPacketException)
    def test_decode_data(self):
        """
        Testing whether an InvalidPacketException is raised when our incoming data is too small
        """
        _decode_data(None, "aa", 42)

    @raises(InvalidPacketException)
    def test_decode_ack(self):
        """
        Testing whether an InvalidPacketException is raised when our incoming ack has an invalid size
        """
        _decode_ack(None, "aa", 42)

    @raises(InvalidPacketException)
    def test_decode_error_too_small(self):
        """
        Testing whether an InvalidPacketException is raised when our incoming error has an invalid size
        """
        _decode_error(None, "aa", 42)

    @raises(InvalidPacketException)
    def test_decode_error_no_message(self):
        """
        Testing whether an InvalidPacketException is raised when our incoming error has an empty message
        """
        _decode_error({}, "aa\0", 0)

    @raises(InvalidPacketException)
    def test_decode_error_invalid_pkg(self):
        """
        Testing whether an InvalidPacketException is raised when our incoming error has an invalid structure
        """
        _decode_error({}, "aaa\0\0", 0)

    @raises(InvalidPacketException)
    def test_decode_packet_too_small(self):
        """
        Testing whether an InvalidPacketException is raised when our incoming packet is too small
        """
        decode_packet("aaa")

    @raises(InvalidPacketException)
    def test_decode_packet_opcode(self):
        """
        Testing whether an InvalidPacketException is raised when our incoming packet contains an invalid opcode
        """
        decode_packet("aaaaaaaaaa")

    def test_encode_packet_error(self):
        """
        Testing whether the encoding of an error packet is correct
        """
        encoded = encode_packet({'opcode': OPCODE_ERROR, 'session_id': 123, 'error_code': 1, 'error_msg': 'hi'})
        self.assertEqual(encoded[-3], 'h')
        self.assertEqual(encoded[-2], 'i')
