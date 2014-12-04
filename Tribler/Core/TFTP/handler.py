import os
import logging
from tempfile import mkstemp
from tarfile import TarFile
from collections import deque
from binascii import hexlify
from time import time
from hashlib import sha1
from base64 import b64encode
from twisted.internet import reactor

from Tribler.dispersy.taskmanager import TaskManager, LoopingCall
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import call_on_reactor_thread
from .session import Session, DEFAULT_BLOCK_SIZE, DEFAULT_TIMEOUT
from .packet import (encode_packet, decode_packet, OPCODE_RRQ, OPCODE_WRQ, OPCODE_ACK, OPCODE_DATA, OPCODE_OACK,
                     OPCODE_ERROR, ERROR_DICT)
from .exception import InvalidPacketException, FileNotFound


MAX_INT32 = 2 ** 16 - 1

DIR_SEPARATOR = u":"
DIR_PREFIX = u"dir" + DIR_SEPARATOR


class TftpHandler(TaskManager):
    """
    This is the TFTP handler that should be registered at the RawServer to handle TFTP packets.
    """

    def __init__(self, session, root_dir, endpoint, prefix, block_size=DEFAULT_BLOCK_SIZE, timeout=DEFAULT_TIMEOUT):
        """ The constructor.
        :param session:    The tribler session.
        :param root_dir:   The root directory to use.
        :param endpoint:   The endpoint to use.
        :param prefix:     The prefix to use.
        :param block_size: Transmission block size.
        :param timeout:    Transmission timeout.
        """
        super(TftpHandler, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session = session
        self.root_dir = root_dir
        # check the root directory if it is valid
        if not os.path.exists(root_dir):
            try:
                os.makedirs(self.root_dir)
            except OSError as ex:
                self._logger.critical(u"Could not create root_dir %s: %s", root_dir, ex)
                raise ex
        if os.path.exists(root_dir) and not os.path.isdir(root_dir):
            msg = u"root_dir is not a directory: %s" % root_dir
            self._logger.critical(msg)
            raise Exception(msg)

        self._endpoint = endpoint
        self._prefix = prefix

        self._block_size = block_size
        self._timeout = timeout

        self._timeout_check_interval = 0.5

        self._session_queue = deque()

    def initialize(self):
        """ Initializes the TFTP service. We create a UDP socket and a server session.
        """
        self._endpoint.listen_to(self._prefix, self.data_came_in)
        # start a looping call that checks timeout
        self.register_task(u"tftp timeout check",
                           LoopingCall(self._check_timeout)).start(self._timeout_check_interval, now=True)

    def shutdown(self):
        """ Shuts down the TFTP service.
        """
        self.cancel_all_pending_tasks()

        self._session_queue = None

    @call_on_reactor_thread
    def download_file(self, file_name, ip, port, extra_info=None, success_callback=None, failure_callback=None):
        """ Downloads a file from a remote host.
        :param file_name: The file name of the file to be downloaded.
        :param ip:        The IP of the remote host.
        :param port:      The port of the remote host.
        :param success_callback: The success callback.
        :param failure_callback: The failure callback.
        """
        self._logger.debug(u"start downloading %s from %s:%s", file_name, ip, port)
        session = Session(True, (ip, port), OPCODE_RRQ, file_name, '', None, None, extra_info=extra_info,
                          block_size=self._block_size, timeout=self._timeout,
                          success_callback=success_callback, failure_callback=failure_callback)

        self._session_queue.append(session)

        if session == self._session_queue[0]:
            self._logger.debug(u"directly start %s", session)
            self._send_request_packet(session)
        else:
            session.next_func = lambda s = session: self._send_request_packet(s)
            self._logger.debug(u"%s will be started later", session)

    def _check_timeout(self):
        """ A scheduled task that checks for timeout.
        """
        # TODO(lipu): find a nicer way to check if we are shutting down
        if not self._session_queue:
            return

        session = self._session_queue[0]
        # only check the first session (the active one)
        if self._check_session_timeout(session):
            self._session_queue.popleft()
        else:
            return

        # start next session in the queue
        while self._session_queue:
            session = self._session_queue[0]

            # check timeout for client sessions
            if not session.is_client and self._check_session_timeout(session):
                self._session_queue.popleft()
                continue

            self._logger.debug(u"starting next session: %s", session)
            self.register_task(u"tftp_next_task", reactor.callLater(0, session.next_func))
            break

    def _check_session_timeout(self, session):
        is_timeout = False
        # only check the first session (the active one)
        if session.last_contact_time + session.timeout < time():
            # fail as timeout
            is_timeout = True
            self._logger.info(u"%s timed out", session)
            if session.failure_callback:
                self.register_task(u"tftp_callback",
                                   reactor.callLater(0, session.failure_callback, session.address,
                                                     session.file_name, "timeout", session.extra_info))
        return is_timeout

    @call_on_reactor_thread
    def data_came_in(self, addr, data):
        """ The callback function that the RawServer will call when there is incoming data.
        :param addr: The (IP, port) address tuple of the sender.
        :param data: The data received.
        """
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

        # a response
        else:
            if not self._session_queue:
                self._logger.warn(u"empty session queue, dropping packet [%s] from %s:%s", packet, ip, port)
                return

            session = self._session_queue[0]
            if session.address != addr:
                self._logger.warn(u"sender (%s:%s) and current session address (%s:%s) mismatch, dropping packet.",
                                  ip, port, session.address[0], session.address[1])
                return
            self._process_packet(session, packet)

            if not session.is_done and not session.is_failed:
                return

            # remove this session from list
            self._session_queue.popleft()
            # remove the timed out client sessions
            while self._session_queue:
                next_session = self._session_queue[0]
                if not next_session.is_client and self._check_session_timeout(next_session):
                    self._session_queue.popleft()
                    continue
                break
            # start the next one if any
            if self._session_queue:
                self._logger.debug(u"Start the next session %s", self._session_queue[0])
                self._session_queue[0].next_func()

            # call callbacks
            if session.is_failed:
                self._logger.info(u"%s failed", session)
                if session.failure_callback:
                    self.register_task(u"tftp_callback",
                                       reactor.callLater(0, session.failure_callback, session.address,
                                                         session.file_name, "download failed", session.extra_info))
            elif session.is_done:
                self._logger.info(u"%s finished", session)
                if session.success_callback:
                    self.register_task(u"tftp_callback",
                                       reactor.callLater(0, session.success_callback, session.address,
                                                         session.file_name, session.file_data, session.extra_info))

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

        # read the file/directory into memory
        try:
            if file_name.startswith(DIR_PREFIX):
                file_data, file_size = self._load_directory(file_name)
            else:
                file_data, file_size = self._load_file(file_name)
            checksum = b64encode(sha1(file_data).digest())
        except FileNotFound as e:
            self._logger.error(u"[READ %s:%s] file/dir not found: %s", ip, port, e)
            dummy_session = Session(False, (ip, port), packet['opcode'], file_name, None, None, None,
                                    block_size=block_size, timeout=timeout)
            self._handle_error(dummy_session, 1)
            return
        except Exception as e:
            self._logger.error(u"[READ %s:%s] failed to load file/dir: %s", ip, port, e)
            dummy_session = Session(False, (ip, port), packet['opcode'], file_name, None, None, None,
                                    block_size=block_size, timeout=timeout)
            self._handle_error(dummy_session, 2)
            return

        # create a session object
        session = Session(False, (ip, port), packet['opcode'], file_name, file_data, file_size, checksum,
                          block_size=block_size, timeout=timeout)

        self._session_queue.append(session)
        self._logger.debug(u"got new request: %s", session)

        # if this session is the first one, we handle it. Otherwise, we delay it.
        if session == self._session_queue[0]:
            # send back OACK now
            self._send_oack_packet(session)
        else:
            # save the next function that this session should call so that we can do it later.
            session.next_func = lambda s = session: self._send_oack_packet(s)

    def _load_file(self, file_name, file_path=None):
        """ Loads a file into memory.
        :param file_name: The path of the file.
        """
        # the _load_directory also uses this method to load zip file.
        if file_path is None:
            file_path = os.path.join(self.root_dir, file_name)

        # check if file exists
        if not os.path.exists(file_path):
            msg = u"file doesn't exist: %s" % file_path
            raise FileNotFound(msg)
        elif not os.path.isfile(file_path):
            msg = u"not a file: %s" % file_path
            raise FileNotFound(msg)

        # read the file into memory
        f = None
        try:
            f = open(file_path, 'rb')
            file_data = f.read()
        except (OSError, IOError) as e:
            msg = u"failed to read file [%s]: %s" % (file_path, e)
            raise Exception(msg)
        finally:
            if f is not None:
                f.close()
        file_size = len(file_data)
        return file_data, file_size

    def _load_directory(self, file_name):
        """ Loads a directory and all files, and compress using gzip to transfer.
        :param file_name: The directory name.
        """
        dir_name = file_name.split(DIR_SEPARATOR, 1)[1]
        dir_path = os.path.join(self.root_dir, dir_name)

        # check if file exists
        if not os.path.exists(dir_path):
            msg = u"directory doesn't exist: %s" % dir_path
            raise FileNotFound(msg)
        elif not os.path.isdir(dir_path):
            msg = u"not a directory: %s" % dir_path
            raise FileNotFound(msg)

        # create a temporary gzip file and compress the whole directory
        tmpfile_no, tmpfile_path = mkstemp(suffix=u"_tribler_tftpdir", prefix=u"tmp_")
        os.close(tmpfile_no)

        tar_file = TarFile.open(tmpfile_path, "w")
        tar_file.add(dir_path, arcname=dir_name, recursive=True)
        tar_file.close()

        # load the zip file as binary
        return self._load_file(file_name, file_path=tmpfile_path)

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
            self._logger.error(u"%s got ERROR message: code = %s, msg = %s",
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
                  'file_name': session.file_name.encode('utf8'),
                  'options': {'blksize': session.block_size,
                              'timeout': session.timeout,
                              }}
        self._send_packet(session, packet)

    def _send_data_packet(self, session, block_number, data):
        packet = {'opcode': OPCODE_DATA,
                  'block_number': block_number,
                  'data': data}
        self._send_packet(session, packet)

    def _send_ack_packet(self, session, block_number):
        packet = {'opcode': OPCODE_ACK,
                  'block_number': block_number}
        self._send_packet(session, packet)

    def _send_error_packet(self, session, error_code, error_msg):
        packet = {'opcode': OPCODE_ERROR,
                  'error_code': error_code,
                  'error_msg': error_msg
                  }
        self._send_packet(session, packet)

    def _send_oack_packet(self, session):
        packet = {'opcode': OPCODE_OACK,
                  'block_number': session.block_number,
                  'options': {'blksize': session.block_size,
                              'timeout': session.timeout,
                              'tsize': session.file_size,
                              'checksum': session.checksum,
                              }}
        self._send_packet(session, packet)
