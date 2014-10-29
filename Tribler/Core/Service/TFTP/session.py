from time import time
from abc import ABCMeta, abstractmethod
import logging

from .packet import (decode_packet, OPCODE_ACK, OPCODE_WRQ, OPCODE_RRQ, OPCODE_DATA, OPCODE_ERROR, OPCODE_OACK,
                     ERROR_DICT)


# default packet data size
DEFAULT_BLOCK_SIZE = 512

# default timeout and maximum retries
DEFAULT_TIMEOUT = 3
DEFAULT_MAX_RETRIES = 2


class Session(object):

    def __init__(self, handler, address,
                 request_opcode=None, file_name=None, file_path=None,
                 mode="octet", block_size=DEFAULT_BLOCK_SIZE, timeout=DEFAULT_TIMEOUT,
                 success_callback=None, failure_callback=None):
        """ Constructor for a Session object.
        :param handler:  The TFTP handler.
        :param address:  The address of the other side,
        :param success_callback: The success user callback function. The arguments include:
                                 (1) file_data:  The file data.
        :param failure_callback: The failure user callback function. The arguments include:
                                 (1) error_code: error code if any.
                                 (2) error_msg:  error message.
        """
        self._logger = logging.getLogger(self.__class__.__name__)

        self.handler = handler
        self.address = address

        self.success_callback = success_callback
        self.failure_callback = failure_callback

        self.done = False
        self.failed = False

        self.last_contact_time = 0
        self.options = {}

        self.file_name = file_name
        self.file_path = file_path
        self.mode = mode
        self.block_size = block_size
        self.timeout = timeout

        self.block_number = 0
        self.last_read_count = None
        self.file_data = None

        self.request_opcode = request_opcode
        self.last_packet = None

        if self.block_size != DEFAULT_BLOCK_SIZE:
            self.options['blksize'] = self.block_size

        self.error_code = None
        self.error_msg = None

    def __str__(self):
        return "TFTP Session [%s:%s]" % self.address

    def __unicode__(self):
        return u"TFTP Session [%s:%s]" % self.address

    def _send_request_packet(self, request_opcode, file_name, mode, options):
        assert request_opcode in (OPCODE_RRQ, OPCODE_WRQ), u"Invalid request_opcode %s" % repr(request_opcode)

        packet = {'opcode': request_opcode,
                  'file_name': file_name,
                  'mode': mode,
                  'options': options}
        self.handler.send_packet(self.address, packet)

    def _send_data_packet(self, block_number, data):
        packet = {'opcode': OPCODE_DATA,
                  'block_number': block_number,
                  'data': data}
        self.handler.send_packet(self.address, packet)

    def _send_ack_packet(self, block_number):
        packet = {'opcode': OPCODE_ACK,
                  'block_number': block_number}
        self.handler.send_packet(self.address, packet)

    def _send_error_packet(self, error_code, error_msg):
        packet = {'opcode': OPCODE_ERROR,
                  'error_code': error_code,
                  'error_msg': error_msg
                  }
        self.handler.send_packet(self.address, packet)

    def _send_oack_packet(self, address, options):
        packet = {'opcode': OPCODE_OACK,
                  'options': options}
        self.handler.send_packet(self.address, packet)

    def process_packet_buff(self, packet_buff):
        """ Processes a raw packet just received.
        :param packet_buff: The packet buffer to process.
        """
        self.last_contact_time = time()
        try:
            packet = decode_packet(packet_buff)
        except Exception as ex:
            self._logger.error(u"Failed to decode packet[%s]: %s", repr(packet_buff), repr(ex))
            self.handle_error(4)
            return

        self.process_packet(packet)

    @abstractmethod
    def process_packet(self, packet):
        """ Processes a packet.
        :param packet: The packet dictionary to process.
        """
        pass

    def close(self):
        """ Releases the resources used by this session.
        """
        pass

    def handle_error(self, error_code):
        """ Handles an error during packet processing.
        :param error_code: The error code.
        """
        self.failed = True
        self.error_code = error_code
        self.error_msg = ERROR_DICT.get(error_code, "")
        self._send_error_packet(self.error_code, self.error_msg)

    def check_timeout(self):
        """ Checks if there is a timeout.
        :return: True or False indicating if there is a timeout.
        """
        # TODO
        return time() - self.last_contact_time > self.timeout

    def _get_next_data(self):
        """ Gets the next block of data to be uploaded. This method is only used for data uploading.
        :return The data to transfer.
        """
        start_idx = self.block_number * self.block_size
        end_idx = start_idx + self.block_size
        data = self.file_data[start_idx:end_idx]
        self.block_number += 1

        # check if we are done
        if self.last_read_count is None:
            self.last_read_count = len(data)

        if self.last_read_count < self.block_size:
            self.done = True
        self.last_read_count = len(data)

        return data

    def _handle_packet_as_receiver(self, packet):
        """ Processes an incoming packet as a receiver.
        :param packet: The incoming packet dictionary.
        """
        # expect a DATA
        if packet['opcode'] != OPCODE_DATA:
            self._logger.error(u"[WRQ] Got OPCODE %s while expecting %s", packet['opcode'], OPCODE_DATA)
            self.handle_error(4)  # illegal TFTP operation
            return

        # check block_number
        if packet['block_number'] != self.block_number + 1:
            self._logger.error(u"[WRQ] Got ACK with block# %s while expecting %s",
                               packet['block_number'], self.block_number + 1)
            self.handle_error(0)  # TODO: check error code
            return

        # save data
        self.file_data += packet['data']
        self.block_number += 1
        self._send_ack_packet(self.block_number)

        # check if it is the end
        if len(packet['data']) < self.block_size:
            self.done = True
            self._logger.info(u"[WRQ] [%s] [%s] transfer finished, saving to file", self, self.file_path)

    def _handle_packet_as_sender(self, packet):
        """ Processes an incoming packet as a sender.
        :param packet: The incoming packet dictionary.
        """
        # expect an ACK packet
        if packet['opcode'] != OPCODE_ACK:
            self._logger.error(u"[RRQ] got OPCODE(%s) while expecting %s", packet['opcode'], OPCODE_ACK)
            self.handle_error(4)  # illegal TFTP operation
            return

        # check block number
        if packet['block_number'] != self.block_number:
            self._logger.error(u"[RRQ] got ACK with block# %s while expecting %s",
                               packet['block_number'], self.block_number)
            self.handle_error(0)  # TODO: check error code
            return

        data = self._get_next_data()
        if self.done:
            self.close()

            self._logger.info(u"[RRQ] [%s] [%s] finished", self, self.file_path)
        else:
            # send DATA
            self._send_data_packet(self.block_number, data)


class TftpServerSession(TftpSession):
    """
    A TFTP server session.
    """

    def process_packet(self, packet):
        """ handles an incoming packet.
        :param packet: The incoming packet dictionary.
        """
        # check if it is an ERROR packet
        if packet['opcode'] == OPCODE_ERROR:
            self._logger.error(u"[%s] got ERROR message: code = %s, msg = %s",
                               self.request_opcode, packet['error_code'], packet['error_msg'])
            self.handle_error(0)  # Error
            return

        # check if this request is RRQ or WRQ,
        if self.request_opcode == OPCODE_RRQ:
            self._handle_packet_as_sender(packet)
        elif self.request_opcode == OPCODE_WRQ:
            self._handle_packet_as_receiver(packet)
        else:
            # this is the first packet we have received
            self._handle_first_packet(packet)

    def _handle_first_packet(self, packet):
        """ Handles the first packet.
        :param packet: The packet to handle.
        """
        if packet['opcode'] not in (OPCODE_RRQ, OPCODE_WRQ):
            self.handle_error(4)  # illegal TFTP operation
            return

        self.request_opcode = packet['opcode']
        self.last_packet = packet

        # check file_name and mode
        self.file_name = packet['file_name'].decode('utf8')
        self.file_path = os.path.join(self.handler.root_dir, self.file_name)

        if self.request_opcode == OPCODE_RRQ:
            # try to load the data
            try:
                self.file_data = read_file(self.file_path)
            except Exception as e:
                self._logger.error(u"Failed to load file %s: %s", self.file_path, e)
                self.failed = True
                return

        elif self.request_opcode == OPCODE_WRQ:
            if os.path.exists(self.file_path):
                if os.path.isfile(self.file_path):
                    # we do not overwrite files
                    self._logger.warn(u"[WRQ] File already exists, will be overwritten: %s", self.file_path)
                    self.handle_error(6)  # file already exists
                    return
                else:
                    self._logger.error(u"[WRQ] Not a file: %s", self.file_path)
                    self.handle_error(2)  # access violation (it is directory)
                    return
            self.file_data = ""

        self.mode = packet['mode']

        # check options
        self.options = packet['options']
        self.block_size = self.options.get('blksize', DEFAULT_BLOCK_SIZE)

        # if there are options, we need to send back OACK. Otherwise we send back ACK/DATA instead.
        if self.options:
            # send OACK
            self._send_oack_packet(self.options)
        else:
            if self.request_opcode == OPCODE_RRQ:
                # send DATA
                data = self._get_next_data()

                self._send_data_packet(self.block_number, data)

            elif self.request_opcode == OPCODE_WRQ:
                # send ACK
                self._send_ack_packet(0)


class TftpClientSession(TftpSession):
    """
    A TFTP client session.
    """

    def process_packet(self, packet):
        """ Processes an incoming packet.
        :param packet: The incoming packet dictionary.
        """
        # check if it is an ERROR packet
        if packet['opcode'] == OPCODE_ERROR:
            self._logger.error(u"[%s] Got ERROR message: code = %s, msg = %s",
                               self.request_opcode, packet['error_code'], packet['error_msg'])
            self.handle_error(0)  # Error
            return

        # if this is the first packet, check OACK
        if packet['opcode'] == OPCODE_OACK:
            if self.last_packet is None and self.options:
                # check options
                self.options = packet['options']
                self.block_size = self.options.get('blksize', DEFAULT_BLOCK_SIZE)

                if self.request_opcode == OPCODE_RRQ:
                    # send ACK
                    self._send_ack_packet(self.block_number)
                    self.block_number += 1
                    self.file_data = ""

                elif self.request_opcode == OPCODE_WRQ:
                    # send DATA
                    data = self._get_next_data()
                    if data is None:
                        self._logger.error(u"%s: Failed to load the next block of data", self)
                        self.handle_error(0)  # undefined

                    self._send_data_packet(self.block_number, data)

            else:
                self._logger.error(u"%s: Got OPCODE %s which is not expected",
                                   self.request_opcode, packet['opcode'])
                self.handle_error(4)  # illegal TFTP operation
            return

        # check if this request is RRQ or WRQ,
        if self.request_opcode == OPCODE_RRQ:
            self._handle_packet_as_receiver(packet)
        elif self.request_opcode == OPCODE_WRQ:
            self._handle_packet_as_sender(packet)
        else:
            self.failed = True
            msg = u"Unexpected, packet = %s" % binascii.hexlify(packet)
            self._logger.error(msg)
            raise Exception(msg)

    def start(self):
        if self.request_opcode == OPCODE_RRQ:
            # WARNING: we do not check if the file exists or not because the RemoteTorrentHandler will check it.
            self.file_data = ""
            pass
        elif self.request_opcode == OPCODE_WRQ:
            # uploading data, so make sure that the file exists
            self.file_data = read_file(self.file_path)
        else:
            raise Exception(u"Unexpected request code: %s" % self.request_opcode)

        file_name = self.file_name.encode('utf8')
        self._send_request_packet(self.request_opcode, file_name, self.mode, self.options)
