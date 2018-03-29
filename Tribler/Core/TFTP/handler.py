import logging
from base64 import b64encode
from binascii import hexlify
from hashlib import sha1
from random import randint
from socket import inet_aton
from struct import unpack
from time import time

from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import (call_on_reactor_thread, blocking_call_on_reactor_thread, attach_runtime_statistics,
                                   is_valid_address)
from Tribler.pyipv8.ipv8.taskmanager import TaskManager

from .exception import InvalidPacketException, FileNotFound
from .packet import (encode_packet, decode_packet, OPCODE_RRQ, OPCODE_WRQ, OPCODE_ACK, OPCODE_DATA, OPCODE_OACK,
                     OPCODE_ERROR, ERROR_DICT)
from .session import Session, DEFAULT_BLOCK_SIZE, DEFAULT_TIMEOUT

MAX_INT16 = 2 ** 16 - 1

SEPARATOR = ":"
METADATA_PREFIX = "metadata" + SEPARATOR

DEFAULT_RETIES = 5


class TftpHandler(TaskManager):

    """
    This is the TFTP handler that should be registered at the thread pool to handle TFTP packets.
    """

    def __init__(self, session, endpoint, prefix, block_size=DEFAULT_BLOCK_SIZE, timeout=DEFAULT_TIMEOUT,
                 max_retries=DEFAULT_RETIES):
        """ The constructor.
        :param session:     The tribler session.
        :param endpoint:    The endpoint to use.
        :param prefix:      The prefix to use.
        :param block_size:  Transmission block size.
        :param timeout:     Transmission timeout.
        :param max_retries: Transmission maximum retries.
        """
        super(TftpHandler, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session = session

        self._endpoint = endpoint
        self._prefix = prefix

        self._block_size = block_size
        self._timeout = timeout
        self._max_retries = max_retries

        self._timeout_check_interval = 0.5

        self._session_id_dict = {}
        self._session_dict = {}

        self._callback_scheduled = False
        self._callbacks = []

        self._is_running = False

    def initialize(self):
        """ Initializes the TFTP service. We create a UDP socket and a server session.
        """
        self._endpoint.listen_to(self._prefix, self.data_came_in)
        # start a looping call that checks timeout
        self.register_task(u"tftp timeout check",
                           LoopingCall(self._task_check_timeout)).start(self._timeout_check_interval, now=True)
        self._is_running = True

    @blocking_call_on_reactor_thread
    def shutdown(self):
        """ Shuts down the TFTP service.
        """
        self.shutdown_task_manager()
        if self._endpoint:
            self._endpoint.stop_listen_to(self._prefix)
            self._endpoint = None

        self._session_id_dict = None
        self._session_dict = None

        self._is_running = False

    @call_on_reactor_thread
    def download_file(self, file_name, ip, port, extra_info=None, success_callback=None, failure_callback=None):
        """ Downloads a file from a remote host.
        :param file_name: The file name of the file to be downloaded.
        :param ip:        The IP of the remote host.
        :param port:      The port of the remote host.
        :param success_callback: The success callback.
        :param failure_callback: The failure callback.
        """
        # generate a unique session id
        # if the target address is higher than ours, we use even number. Otherwise, we use odd number.
        if not self._is_running:
            return

        target_ip = unpack('!L', inet_aton(ip))[0]
        target_port = port
        self_ip, self_port = self.session.lm.dispersy.wan_address
        self_ip = unpack('!L', inet_aton(self_ip))[0]
        if target_ip > self_ip:
            generate_session = lambda: randint(0, MAX_INT16) & 0xfff0
        elif target_ip < self_ip:
            generate_session = lambda: randint(0, MAX_INT16) | 1
        else:
            if target_port > self_port:
                generate_session = lambda: randint(0, MAX_INT16) & 0xfff0
            elif target_port < self_port:
                generate_session = lambda: randint(0, MAX_INT16) | 1
            else:
                self._logger.critical(u"communicating to myself %s:%s", ip, port)
                generate_session = lambda: randint(0, MAX_INT16)

        session_id = generate_session()
        while (ip, port, session_id) in self._session_dict:
            session_id = generate_session()

        # create session
        assert session_id is not None, u"session_id = %s" % session_id
        self._logger.debug(u"start downloading %s from %s:%s, sid = %s", file_name, ip, port, session_id)
        session = Session(True, session_id, (ip, port), OPCODE_RRQ, file_name, '', None, None,
                          extra_info=extra_info, block_size=self._block_size, timeout=self._timeout,
                          success_callback=success_callback, failure_callback=failure_callback)

        self._add_new_session(session)
        self._send_request_packet(session)

        self._logger.info(u"%s started", session)

    @attach_runtime_statistics(u"{0.__class__.__name__}.{function_name}")
    def _task_check_timeout(self):
        """ A scheduled task that checks for timeout.
        """
        if not self._is_running:
            return

        need_session_cleanup = False
        for key, session in self._session_dict.items():
            if self._check_session_timeout(session):
                need_session_cleanup = True

                # fail as timeout
                self._logger.info(u"%s timed out", session)
                if session.failure_callback:
                    callback = lambda cb = session.failure_callback, addr = session.address, fn = session.file_name,\
                        msg = "timeout", ei = session.extra_info: cb(addr, fn, msg, ei)
                    self._callbacks.append(callback)

                self._cleanup_session(key)

        if need_session_cleanup:
            self._schedule_callback_processing()

    def _check_session_timeout(self, session):
        """
        Checks if a session has timed out and tries to retransmit packet if allowed.
        :param session: The given session.
        :return: True or False indicating if the session has failed.
        """
        has_failed = False
        timeout = session.timeout * (2**session.retries)
        if session.last_contact_time + timeout < time():
            # we do NOT resend packets that are not data-related
            if session.retries < self._max_retries and session.last_sent_packet['opcode'] in (OPCODE_ACK, OPCODE_DATA):
                self._send_packet(session, session.last_sent_packet)
                session.retries += 1
            else:
                has_failed = True
        return has_failed

    def _schedule_callback_processing(self):
        """
        Schedules a task to process callbacks.
        """
        if not self._callback_scheduled:
            self.register_task(u"tftp_process_callback", reactor.callLater(0, self._process_callbacks))
            self._callback_scheduled = True

    @attach_runtime_statistics(u"{0.__class__.__name__}.{function_name}")
    def _process_callbacks(self):
        """
        Process the callbacks
        """
        for callback in self._callbacks:
            callback()
        self._callbacks = []
        self._callback_scheduled = False

    def _add_new_session(self, session):
        self._session_id_dict[session.session_id] = 1 + self._session_id_dict.get(session.session_id, 0)
        self._session_dict[(session.address[0], session.address[1], session.session_id)] = session

    def _cleanup_session(self, key):
        session_id = key[2]
        self._session_id_dict[session_id] -= 1
        if self._session_id_dict[session_id] == 0:
            del self._session_id_dict[session_id]
        del self._session_dict[key]

    @attach_runtime_statistics(u"{0.__class__.__name__}.{function_name}")
    @call_on_reactor_thread
    def data_came_in(self, addr, data):
        """ The callback function that the thread pool will call when there is incoming data.
        :param addr: The (IP, port) address tuple of the sender.
        :param data: The data received.
        """
        if not self._is_running or not is_valid_address(addr):
            return

        ip, port = addr

        # decode the packet
        try:
            packet = decode_packet(data)
        except InvalidPacketException as e:
            self._logger.error(u"Invalid packet from [%s:%s], packet=[%s], error=%s", ip, port, hexlify(data), e)
            return

        if packet['opcode'] == OPCODE_WRQ:
            self._logger.error(u"WRQ is not supported from [%s:%s], packet=[%s]", ip, port, repr(packet))
            return

        self._logger.debug(u"GOT packet opcode[%s] from %s:%s", packet['opcode'], ip, port)
        # a new request
        if packet['opcode'] == OPCODE_RRQ:
            self._logger.debug(u"start handling new request: %s", packet)
            self._handle_new_request(ip, port, packet)
            return

        if (ip, port, packet['session_id']) not in self._session_dict:
            self._logger.warn(u"got non-existing session from %s:%s, id = %s", ip, port, packet['session_id'])
            return

        # handle the response
        session = self._session_dict[(ip, port, packet['session_id'])]
        self._process_packet(session, packet)

        if not session.is_done and not session.is_failed:
            return

        self._cleanup_session((ip, port, packet['session_id']))

        # schedule callback
        if session.is_failed:
            self._logger.info(u"%s failed", session)
            if session.failure_callback:
                callback = lambda cb = session.failure_callback, a = session.address, fn = session.file_name,\
                    msg = "download failed", ei = session.extra_info: cb(a, fn, msg, ei)
                self._callbacks.append(callback)
        elif session.is_done:
            self._logger.info(u"%s finished", session)
            if session.success_callback:
                callback = lambda cb = session.success_callback, a = session.address, fn = session.file_name,\
                    fd = session.file_data, ei = session.extra_info: cb(a, fn, fd, ei)
                self._callbacks.append(callback)

        self._schedule_callback_processing()

    def _handle_new_request(self, ip, port, packet):
        """ Handles a new request.
        :param ip:      The IP of the client.
        :param port:    The port of the client.
        :param packet:  The packet.
        """
        if packet['opcode'] != OPCODE_RRQ:
            self._logger.error(u"Unexpected request from %s:%s, opcode=%s: packet=%s",
                               ip, port, packet['opcode'], repr(packet))
            return
        if 'options' not in packet:
            self._logger.error(u"No 'options' in request from %s:%s, opcode=%s, packet=%s",
                               ip, port, packet['opcode'], repr(packet))
            return
        if 'blksize' not in packet['options'] or 'timeout' not in packet['options']:
            self._logger.error(u"No 'blksize' or 'timeout' not in 'options' from %s:%s, opcode=%s, packet=%s",
                               ip, port, packet['opcode'], repr(packet))
            return

        file_name = packet['file_name'].decode('utf8')
        block_size = packet['options']['blksize']
        timeout = packet['options']['timeout']

        # check session_id
        if (ip, port, packet['session_id']) in self._session_dict:
            self._logger.warn(u"Existing session_id %s from %s:%s", packet['session_id'], ip, port)
            dummy_session = Session(False, packet['session_id'], (ip, port), packet['opcode'],
                                    file_name, None, None, None, block_size=block_size, timeout=timeout)
            self._handle_error(dummy_session, 50)
            return

        # read the file/directory into memory
        try:
            if file_name.startswith(METADATA_PREFIX):
                if not self.session.config.get_metadata_enabled():
                    return
                file_data, file_size = self._load_metadata(file_name[len(METADATA_PREFIX):])
            else:
                if not self.session.config.get_torrent_store_enabled():
                    return
                file_data, file_size = self._load_torrent(file_name)
            checksum = b64encode(sha1(file_data).digest())
        except FileNotFound as e:
            self._logger.warn(u"[READ %s:%s] file not found: %s", ip, port, e)
            dummy_session = Session(False, packet['session_id'], (ip, port), packet['opcode'],
                                    file_name, None, None, None, block_size=block_size, timeout=timeout)
            self._handle_error(dummy_session, 1)
            return
        except Exception as e:
            self._logger.error(u"[READ %s:%s] failed to load file: %s", ip, port, e)
            dummy_session = Session(False, packet['session_id'], (ip, port), packet['opcode'],
                                    file_name, None, None, None, block_size=block_size, timeout=timeout)
            self._handle_error(dummy_session, 2)
            raise

        # create a session object
        session = Session(False, packet['session_id'], (ip, port), packet['opcode'],
                          file_name, file_data, file_size, checksum, block_size=block_size, timeout=timeout)

        # insert session_id and session
        self._add_new_session(session)
        self._logger.debug(u"got new request: %s", session)

        # send back OACK now
        self._send_oack_packet(session)

    def _load_metadata(self, thumb_hash):
        """ Loads a thumbnail into memory.
        :param thumb_hash: The thumbnail hash.
        """
        file_data = self.session.lm.metadata_store.get(thumb_hash.encode('utf8'))
        # check if file exists
        if not file_data:
            msg = u"Metadata not in store: %s" % thumb_hash
            raise FileNotFound(msg)

        return file_data, len(file_data)

    def _load_torrent(self, file_name):
        """ Loads a file into memory.
        :param file_name: The file name.
        """
        infohash = (file_name[:-8]).encode('utf8')  # len('.torrent') = 8

        file_data = self.session.lm.torrent_store.get(infohash)
        # check if file exists
        if not file_data:
            msg = u"Torrent not in store: %s" % infohash
            raise FileNotFound(msg)

        return file_data, len(file_data)

    def _get_next_data(self, session):
        """ Gets the next block of data to be uploaded. This method is only used for data uploading.
        :return The data to transfer.
        """
        start_idx = session.block_number * session.block_size
        end_idx = start_idx + session.block_size
        data = session.file_data[start_idx:end_idx]
        session.block_number += 1

        # check if we are done
        if len(data) < session.block_size:
            session.is_waiting_for_last_ack = True

        return data

    def _process_packet(self, session, packet):
        """ processes an incoming packet.
        :param packet: The incoming packet dictionary.
        """
        session.last_contact_time = time()
        # check if it is an ERROR packet
        if packet['opcode'] == OPCODE_ERROR:
            self._logger.warning(u"%s got ERROR message: code = %s, msg = %s",
                                 session, packet['error_code'], packet['error_msg'])
            session.is_failed = True
            return

        # client is the receiver, server is the sender
        if session.is_client:
            self._handle_packet_as_receiver(session, packet)
        else:
            self._handle_packet_as_sender(session, packet)

    def _handle_packet_as_receiver(self, session, packet):
        """ Processes an incoming packet as a receiver.
        :param packet: The incoming packet dictionary.
        """
        # if this is the first packet, check OACK
        if packet['opcode'] == OPCODE_OACK:
            if session.last_received_packet is None:
                # check options
                if session.block_size != packet['options']['blksize']:
                    msg = "%s OACK blksize mismatch: %s != %s (expected)" %\
                          (session, session.block_size, packet['options']['blksize'])
                    self._logger.error(msg)
                    self._handle_error(session, 0, error_msg=msg)  # Error: blksize mismatch
                    return

                if session.timeout != packet['options']['timeout']:
                    msg = "%s OACK timeout mismatch: %s != %s (expected)" %\
                          (session, session.timeout, packet['options']['timeout'])
                    self._logger.error(msg)
                    self._handle_error(session, 0, error_msg=msg)  # Error: timeout mismatch
                    return

                session.file_size = packet['options']['tsize']
                session.checksum = packet['options']['checksum']

                if session.request == OPCODE_RRQ:
                    # send ACK
                    self._send_ack_packet(session, session.block_number)
                    session.block_number += 1
                    session.file_data = ""

            else:
                self._logger.error(u"%s Got OPCODE %s which is not expected", session, packet['opcode'])
                self._handle_error(session, 4)  # illegal TFTP operation
            return

        # expect a DATA
        if packet['opcode'] != OPCODE_DATA:
            self._logger.error(u"%s Got OPCODE %s while expecting %s", session, packet['opcode'], OPCODE_DATA)
            self._handle_error(session, 4)  # illegal TFTP operation
            return

        self._logger.debug(u"%s Got data, #block = %s size = %s", session, packet['block_number'], len(packet['data']))

        # check block_number
        # ignore old ones, they may be retransmissions
        if packet['block_number'] < session.block_number:
            self._logger.warn(u"%s ignore old block number DATA %s < %s",
                              session, packet['block_number'], session.block_number)
            return

        if packet['block_number'] != session.block_number:
            msg = "%s Got ACK with block# %s while expecting %s" %\
                  (session, packet['block_number'], session.block_number)
            self._logger.error(msg)
            self._handle_error(session, 0, error_msg=msg)  # Error: block_number mismatch
            return

        # save data
        session.file_data += packet['data']
        self._send_ack_packet(session, session.block_number)
        session.block_number += 1

        # check if it is the end
        if len(packet['data']) < session.block_size:
            self._logger.info(u"%s transfer finished. checking data integrity...", session)
            # check file size and checksum
            if session.file_size != len(session.file_data):
                self._logger.error(u"%s file size %s doesn't match expectation %s",
                                   session, len(session.file_data), session.file_size)
                session.is_failed = True
                return

            # compare checksum
            data_checksum = b64encode(sha1(session.file_data).digest())
            if session.checksum != data_checksum:
                self._logger.error(u"%s file checksum %s doesn't match expectation %s",
                                   session, data_checksum, session.checksum)
                session.is_failed = True
                return

            session.is_done = True

    def _handle_packet_as_sender(self, session, packet):
        """ Processes an incoming packet as a sender.
        :param packet: The incoming packet dictionary.
        """
        # expect an ACK packet
        if packet['opcode'] != OPCODE_ACK:
            self._logger.error(u"%s got OPCODE(%s) while expecting %s", session, packet['opcode'], OPCODE_ACK)
            self._handle_error(session, 4)  # illegal TFTP operation
            return

        # check block number
        # ignore old ones, they may be retransmissions
        if packet['block_number'] < session.block_number:
            self._logger.warn(u"%s ignore old block number ACK %s < %s",
                              session, packet['block_number'], session.block_number)
            return

        if packet['block_number'] != session.block_number:
            msg = "%s got ACK with block# %s while expecting %s" %\
                  (session, packet['block_number'], session.block_number)
            self._logger.error(msg)
            self._handle_error(session, 0, error_msg=msg)  # Error: block_number mismatch
            return

        if session.is_waiting_for_last_ack:
            session.is_done = True
            return

        data = self._get_next_data(session)
        # send DATA
        self._send_data_packet(session, session.block_number, data)

    def _handle_error(self, session, error_code, error_msg=""):
        """ Handles an error during packet processing.
        :param error_code: The error code.
        """
        session.is_failed = True
        msg = error_msg if error_msg else ERROR_DICT.get(error_code, error_msg)
        self._send_error_packet(session, error_code, msg)

    def _send_packet(self, session, packet):
        packet_buff = encode_packet(packet)
        extra_msg = u" block_number = %s" % packet['block_number'] if packet.get('block_number') is not None else ""
        extra_msg += u" block_size = %s" % len(packet['data']) if packet.get('data') is not None else ""

        self._logger.debug(u"SEND OP[%s] -> %s:%s %s",
                           packet['opcode'], session.address[0], session.address[1], extra_msg)
        self._endpoint.send_packet(Candidate(session.address, False), packet_buff, prefix=self._prefix)

        # update information
        session.last_contact_time = time()
        session.last_sent_packet = packet

    def _send_request_packet(self, session):
        assert session.request == OPCODE_RRQ, u"Invalid request_opcode %s" % repr(session.request)

        packet = {'opcode': session.request,
                  'session_id': session.session_id,
                  'file_name': session.file_name.encode('utf8'),
                  'options': {'blksize': session.block_size,
                              'timeout': session.timeout,
                              }}
        self._send_packet(session, packet)

    def _send_data_packet(self, session, block_number, data):
        packet = {'opcode': OPCODE_DATA,
                  'session_id': session.session_id,
                  'block_number': block_number,
                  'data': data}
        self._send_packet(session, packet)

    def _send_ack_packet(self, session, block_number):
        packet = {'opcode': OPCODE_ACK,
                  'session_id': session.session_id,
                  'block_number': block_number}
        self._send_packet(session, packet)

    def _send_error_packet(self, session, error_code, error_msg):
        packet = {'opcode': OPCODE_ERROR,
                  'session_id': session.session_id,
                  'error_code': error_code,
                  'error_msg': error_msg
                  }
        self._send_packet(session, packet)

    def _send_oack_packet(self, session):
        packet = {'opcode': OPCODE_OACK,
                  'session_id': session.session_id,
                  'block_number': session.block_number,
                  'options': {'blksize': session.block_size,
                              'timeout': session.timeout,
                              'tsize': session.file_size,
                              'checksum': session.checksum,
                              }}
        self._send_packet(session, packet)
