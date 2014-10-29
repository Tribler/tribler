import os
import logging

from Tribler.dispersy.taskmanager import TaskManager, LoopingCall
from Tribler.dispersy.candidate import Candidate

from .session import TftpClientSession, TftpServerSession, DEFAULT_BLOCK_SIZE, DEFAULT_TIMEOUT
from .packet import encode_packet, OPCODE_RRQ, OPCODE_WRQ


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

        self.endpoint = endpoint
        self.prefix = prefix

        self.block_size = block_size
        self.timeout = timeout

        self._timeout_check_interval = 2

        self._session_id_list = []
        self._session_dict = {}

    def initialize(self):
        """ Initializes the TFTP service. We create a UDP socket and a server session.
        """
        self.endpoint.listen_to(self.prefix, self.data_came_in)
        # start a looping call that checks timeout
        self.register_task("tftp timeout check",
                           LoopingCall(self.check_timeout)).start(self._timeout_check_interval, now=True)

    def shutdown(self):
        """ Shuts down the TFTP service.
        """
        self.cancel_all_pending_tasks()

        self._session_dict = None

    def check_timeout(self):
        """ A scheduled task that checks for timeout.
        """
        # TODO: make a nicer way to check if we are shutting down
        if self._session_dict is None:
            return

        for key, session in self._session_dict.items():
            if session.check_timeout():
                # fail as timeout
                del self._session_dict[key]
                session.close()
                session.failure_callback(session.file_path, 0, "Timeout")

    def upload_file(self, file_name, file_path, ip, port, success_callback=None, failure_callback=None):
        """ Uploads a file to a remote host.
        :param file_name: The file name of the file to be uploaded.
        :param file_path: The file path of the file to be uploaded.
        :param ip:        The IP of the remote host.
        :param port:      The port of the remote host.
        """
        session = TftpClientSession(self, (ip, port),
                                    request_opcode=OPCODE_WRQ,
                                    file_name=file_name,
                                    file_path=file_path,
                                    block_size=self.block_size,
                                    success_callback=success_callback, failure_callback=failure_callback)
        session.start()
        self._session_dict[(ip, port)] = session

    def download_file(self, file_name, ip, port, success_callback=None, failure_callback=None):
        """ Downloads a file from a remote host.
        :param file_name: The file name of the file to be downloaded.
        :param ip:        The IP of the remote host.
        :param port:      The port of the remote host.
        :param success_callback: The success callback.
        :param failure_callback: The failure callback.
        """
        self._logger.debug(u"Start downloading %s from %s:%s", file_name, ip, port)
        session = Session(True, (ip, port), OPCODE_RRQ, file_name, '', None,
                          success_callback=success_callback, failure_callback=failure_callback)

        with self._session_lock:
            if (ip, port) not in self._session_dict:
                self._session_dict[(ip, port)] = deque()
            self._session_dict[(ip, port)].append(session)

            if session == self._session_dict[(ip, port)][0]:
                self._send_request_packet(session)
            else:
                session.next_func = lambda s = session: self._send_request_packet(s)

    def _check_timeout(self):
        """ A scheduled task that checks for timeout.
        """
        # TODO: make a nicer way to check if we are shutting down
        with self._session_lock:
            if self._session_dict is None:
                return

            for key, session_queue in self._session_dict.items():
                # only check the first session (the active one)
                session = session_queue[0]
                if session.last_contact_time + session.timeout > time():
                    # fail as timeout
                    session_queue.popleft()
                    self._session_dict[key] = session_queue
                    if session.failure_callback is not None:
                        session.failure_callback(session.file_name, 0, "Timeout")

                    # start next session in the queue
                    if not session_queue:
                        del self._session_dict[key]
                        return

                    session = session_queue[0]
                    session.next_func()

    def data_came_in(self, addr, data):
        """ The callback function that the RawServer will call when there is incoming data.
        :param addr: The (IP, port) address tuple of the sender.
        :param data: The data received.
        """
        ip, port = addr
        self._logger.debug(u"GOT packet [%s] from %s:%s", len(data), ip, port)

        # decode the packet
        try:
            packet = decode_packet(data)
        except InvalidPacketException as e:
            self._logger.error(u"Invalid packet from [%s:%s], packet=[%s], error=%s",
                               ip, port, hexlify(data), e)
            return

        # a new request
        if packet['opcode'] in (OPCODE_RRQ, OPCODE_WRQ):
            self._handle_new_request(ip, port, packet)

        # a response
        else:
            with self._session_lock:
                session_queue = self._session_dict.get(addr, None)
            if not session_queue:
                self._logger.error(u"Got empty session list for %s:%s", ip, port)
                return

            session = session_queue[0]
            self._process_packet(session, packet)

            if not session.is_done and not session.is_failed:
                return

            # remove this session from list and start the next one
            with self._session_lock:
                session_queue.popleft()
                self._session_dict[addr] = session_queue
                if session_queue:
                    self._logger.debug(u"Start the next session %s", session)
                    session_queue[0].next_func()
                else:
                    if session.failure_callback:
                        session.failure_callback(session.error_code, session.error_msg)

            # call callbacks
            if session.is_done:
                self._logger.debug(u"%s finished", session)
                if session.success_callback is not None:
                    session.success_callback(session.file_data)
            elif session.is_failed:
                self._logger.debug(u"%s failed", session)
                if session.failure_callback is not None:
                    session.failure_callback(session.file_data)

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
        file_path = os.path.join(self.root_dir, file_name)
        block_size = packet['options']['blksize']
        timeout = packet['options']['timeout']

        # check if file exists
        if not os.path.exists(file_path):
            self._logger.warn(u"[READ %s:%s] file doesn't exist: %s", ip, port, file_path)
            # TODO: send back error
            return
        elif not os.path.isfile(file_path):
            self._logger.warn(u"[READ %s:%s] not a file: %s", ip, port, file_path)
            # TODO: send back error
            return

        # read the file into memory
        f = None
        try:
            f = open(file_path, 'rb')
            file_data = f.read()
        except (OSError, IOError) as e:
            self._logger.error(u"[READ %s:%s] failed to read file [%s]: %s", ip, port, file_path, e)
            # TODO: send back error
            return
        finally:
            if f is not None:
                f.close()

        file_size = len(file_data)

        with self._session_lock:
            # create a session object
            session = Session(False, (ip, port), packet['opcode'], file_name, file_data, file_size,
                              block_size=block_size, timeout=timeout)

            if (ip, port) not in self._session_dict:
                self._session_dict[(ip, port)] = deque()
            self._session_dict[(ip, port)].append(session)

            # if this session is the first one, we handle it. Otherwise, we delay it.
            if session == self._session_dict[(ip, port)][0]:
                # send back OACK now
                self._send_oack_packet(session)
            else:
                # save the next function that this session should call so that we can do it later.
                self.next_func = lambda s = session: self._send_oack_packet(s)

    def _get_next_data(self, session):
        """ Gets the next block of data to be uploaded. This method is only used for data uploading.
        :return The data to transfer.
        """
        start_idx = session.block_number * session.block_size
        end_idx = start_idx + self.block_size
        data = session.file_data[start_idx:end_idx]
        session.block_number += 1

        # check if we are done
        if session.last_read_count is None:
            session.last_read_count = len(data)

        if session.last_read_count < session.block_size:
            session.is_done = True
        session.last_read_count = len(data)

        return data

    def _process_packet(self, session, packet):
        """ processes an incoming packet.
        :param packet: The incoming packet dictionary.
        """
        # check if it is an ERROR packet
        if packet['opcode'] == OPCODE_ERROR:
            self._logger.error(u"%s got ERROR message: code = %s, msg = %s",
                               session, packet['error_code'], packet['error_msg'])
            self._handle_error(session, 0)  # Error
            return

        # client is the receiver, server is the sender
        if session.is_client:
            self._handle_packet_as_receiver(session, packet)
        else:
            # create a new session for it
            session = TftpServerSession(self, (ip, port))
            session.process_packet_buff(data)

            if session.failed:
                pass
            else:
                self._session_dict[(ip, port)] = session
