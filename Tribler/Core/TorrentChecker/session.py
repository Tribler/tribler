from abc import ABCMeta, abstractmethod, abstractproperty
import logging
import random
import socket
import struct
import time
import urllib

from libtorrent import bdecode

from Tribler.Core.Utilities.tracker_utils import parse_tracker_url


# Although these are the actions for UDP trackers, they can still be used as
# identifiers.
TRACKER_ACTION_CONNECT = 0
TRACKER_ACTION_ANNOUNCE = 1
TRACKER_ACTION_SCRAPE = 2

MAX_INT32 = 2 ** 16 - 1

UDP_TRACKER_INIT_CONNECTION_ID = 0x41727101980
UDP_TRACKER_RECHECK_INTERVAL = 15
UDP_TRACKER_MAX_RETRIES = 8

HTTP_TRACKER_RECHECK_INTERVAL = 60
HTTP_TRACKER_MAX_RETRIES = 0

MAX_TRACKER_MULTI_SCRAPE = 74


def create_tracker_session(tracker_url, on_result_callback):
    """
    Creates a tracker session with the given tracker URL.
    :param tracker_url: The given tracker URL.
    :param on_result_callback: The on_result callback.
    :return: The tracker session.
    """
    tracker_type, tracker_address, announce_page = parse_tracker_url(tracker_url)

    if tracker_type == u'UDP':
        session = UdpTrackerSession(tracker_url, tracker_address, announce_page, on_result_callback)
    else:
        session = HttpTrackerSession(tracker_url, tracker_address, announce_page, on_result_callback)
    return session


class TrackerSession(object):
    __meta__ = ABCMeta

    def __init__(self, tracker_type, tracker_url, tracker_address, announce_page, on_result_callback):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._tracker_type = tracker_type
        self._tracker_url = tracker_url
        self._tracker_address = tracker_address
        self._announce_page = announce_page

        self._infohash_list = []
        self._socket = None

        self._on_result_callback = on_result_callback

        self._retries = 0

        self._last_contact = None
        self._action = None

        # some flags
        self._is_initiated = False  # you cannot add requests to a session if it has been initiated
        self._is_finished = False
        self._is_failed = False

    def __str__(self):
        return "Tracker[%s, %s]" % (self._tracker_type, self._tracker_url)

    def __unicode__(self):
        return u"Tracker[%s, %s]" % (self._tracker_type, self._tracker_url)

    def cleanup(self):
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        _infohash_list = None

    def can_add_request(self):
        """
        Checks if we still can add requests to this session.
        :return: True or False.
        """
        return not self._is_initiated and len(self._infohash_list) < MAX_TRACKER_MULTI_SCRAPE

    def has_request(self, infohash):
        return infohash in self._infohash_list

    def add_request(self, infohash):
        """
        Adds a request into this session.
        :param infohash: The infohash to be added.
        """
        assert not self._is_initiated, u"Must not add request to an initiated session."
        assert not self.has_request(infohash), u"Must not add duplicate requests"
        self._infohash_list.append(infohash)

    def process_request(self):
        if self._action == TRACKER_ACTION_CONNECT:
            return self._handle_connection()
        else:
            return self._handle_response()

    @abstractmethod
    def create_connection(self):
        """Creates a connection to the tracker."""
        pass

    @abstractmethod
    def recreate_connection(self):
        """Re-creates a connection to the tracker."""
        pass

    @abstractmethod
    def _handle_connection(self):
        """Does some work when a connection has been established."""
        pass

    @abstractmethod
    def _handle_response(self):
        """Processes a response message."""
        pass

    @abstractproperty
    def max_retries(self):
        """Number of retries before a session is marked as failed."""
        pass

    @abstractproperty
    def retry_interval(self):
        """Interval between retries."""
        pass

    @property
    def tracker_type(self):
        return self._tracker_type

    @property
    def tracker_url(self):
        return self._tracker_url

    @property
    def infohash_list(self):
        return self._infohash_list

    @property
    def last_contact(self):
        return self._last_contact

    @property
    def socket(self):
        return self._socket

    @property
    def action(self):
        return self._action

    @property
    def retries(self):
        return self._retries

    def increase_retries(self):
        self._retries += 1

    @property
    def is_initiated(self):
        return self._is_initiated

    @property
    def is_finished(self):
        return self._is_finished

    @property
    def is_failed(self):
        return self._is_failed


class HttpTrackerSession(TrackerSession):

    def __init__(self, tracker_url, tracker_address, announce_page, on_result_callback):
        super(HttpTrackerSession, self).__init__(u'HTTP', tracker_url, tracker_address, announce_page,
                                                 on_result_callback)
        self._header_buffer = None
        self._message_buffer = None
        self._content_encoding = None
        self._content_length = None
        self._received_length = None

    def max_retries(self):
        return HTTP_TRACKER_MAX_RETRIES

    def retry_interval(self):
        return HTTP_TRACKER_RECHECK_INTERVAL

    def create_connection(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setblocking(0)

        return self.recreate_connection()

    def recreate_connection(self):
        # an exception may be raised if the socket is non-blocking
        try:
            self._socket.connect(self._tracker_address)
        except Exception as e:
            # Error 115 means the operation is in progress.
            # Error 10035 is WSAEWOULDBLOCK on Windows.
            if e[0] not in (115, 10035):
                self._logger.debug(u"%s Failed to connect to HTTP tracker [%s, %s]: %s",
                                   self, self._tracker_url, self._tracker_address, e)
                self._is_failed = True
                return False

        self._action = TRACKER_ACTION_CONNECT
        self._last_contact = int(time.time())
        return True

    def _handle_connection(self):
        # create the HTTP GET message
        # Note: some trackers have strange URLs, e.g.,
        #       http://moviezone.ws/announce.php?passkey=8ae51c4b47d3e7d0774a720fa511cc2a
        #       which has some sort of 'key' as parameter, so we need to check
        #       if there is already a parameter available
        message = 'GET '
        message += '/' + self._announce_page.replace(u'announce', u'scrape')
        if message.find('?') == -1:
            message += '?'
        else:
            message += '&'

        # append the infohashes as parameters
        for infohash in self._infohash_list:
            message += 'info_hash='
            message += urllib.quote(infohash)
            message += '&'
        message = message[:-1]  # remove the last AND '&'
        message += ' HTTP/1.1\r\n'
        message += '\r\n'

        try:
            self._socket.sendall(message)
        except Exception as e:
            self._logger.error(u"%s Failed to send HTTP SCRAPE message: %s", self, e)
            self._is_failed = True
            return

        self._logger.debug(u"%s HTTP SCRAPE message sent", self)

        # no more requests can be appended to this session
        self._action = TRACKER_ACTION_SCRAPE
        self._is_initiated = True

    def _handle_response(self):
        try:
            # TODO: this buffer size may be changed
            response = self._socket.recv(8192)
        except Exception as e:
            self._logger.error(u"%s Failed to receive HTTP SCRAPE response: %s", self, e)
            self._is_failed = True
            return

        self._logger.debug(u"%s Got response", self)

        if not response:
            self._is_failed = True
            return

        # for the header message, we need to parse the content length in case
        # if the HTTP packets are partial.
        if not self._message_buffer:
            # append the header part
            if not self._header_buffer:
                self._header_buffer = response
            else:
                self._header_buffer += response

            # check if the header part is over
            if self._header_buffer.find('\r\n\r\n') != -1:
                self._header_buffer, self._message_buffer = self._header_buffer.split('\r\n\r\n', 1)

                self._received_length = len(self._message_buffer)
                self._process_header()

        # the remaining part
        else:
            self._message_buffer += response
            self._received_length += len(response)

        # check the read count
        if self._received_length >= self._content_length:
            # process the retrieved information
            success = self._process_scrape_response()
            if success:
                self._is_finished = True
            else:
                self._is_failed = True

        # wait for more
        else:
            pass

    def _process_header(self):
        # get and check HTTP response code
        protocol, code, msg = self._header_buffer.split(' ', 2)
        if code == '301' or code == '302':
            idx = self._header_buffer.find('Location: ')
            if idx == -1:
                self._is_failed = True
            else:
                new_location = (self._header_buffer[idx:].split('\r\n')[0]).split(' ')[1]
                try:
                    idx = new_location.find('info_hash=')
                    if idx != -1:
                        new_location = new_location[:idx]
                    if new_location[-1] != '/':
                        new_location += "/"
                    new_location += "announce"

                    tracker_type, tracker_address, announce_page = parse_tracker_url(new_location)
                    if tracker_type != self._tracker_type:
                        raise RuntimeError(u"cannot redirect to a different tracker type: %s", new_location)

                    else:
                        self._logger.debug(u"%s being redirected to %s", self, new_location)

                        self._tracker_address = tracker_address
                        self._announce_page = announce_page
                        self._socket.close()
                        self._socket = None

                        self.recreate_connection()

                except RuntimeError as run_err:
                    self._logger.error(u"%s: Runtime Error: %s, address: %s, announce: %s",
                                       self, run_err, self._tracker_address, self._announce_page)
                    self._is_failed = True

                except Exception as err:
                    self._logger.exception(u"Failed to process HTTP tracker header: [%s], Tracker: %s,"
                                           u" Tracker Address: %s, Tracker Announce: %s",
                                           err, self._tracker_url, self._tracker_address, self._announce_page)
                    self._logger.debug(u"Header: %s", self._header_buffer)
                    self._is_failed = True
            return

        if code != '200':
            # error response code
            self._logger.debug(u"%s HTTP SCRAPE error response code [%s, %s]", self, code, msg)
            self._is_failed = True
            return

        # check the content type
        idx = self._header_buffer.find('Content-Encoding: ')
        if idx == -1:
            # assuming it is plain text or something similar
            self._content_encoding = 'plain'
        else:
            encoding = (self._header_buffer[idx:].split('\r\n')[0]).split(' ')[1]
            self._content_encoding = encoding

        # get the content length
        idx = self._header_buffer.find('Content-Length: ')
        if idx == -1:
            # assume that the content is small

            # process the retrieved information
            success = self._process_scrape_response()
            if success:
                self._is_finished = True
            else:
                self._is_failed = True

        else:
            idx += len('Content-Length: ')
            self._content_length = int(self._header_buffer[idx:].split('\r\n', 1)[0].strip())

    def _process_scrape_response(self):
        # parse the retrieved results
        if self._message_buffer is None:
            return False
        response_dict = bdecode(self._message_buffer)
        if response_dict is None:
            return False

        unprocessed_infohash_list = self._infohash_list[:]
        if 'files' in response_dict and isinstance(response_dict['files'], dict):
            for infohash in response_dict['files']:
                downloaded = response_dict['files'][infohash].get('downloaded', 0)
                complete = response_dict['files'][infohash].get('complete', 0)
                incomplete = response_dict['files'][infohash].get('incomplete', 0)

                seeders = downloaded
                leechers = incomplete

                # handle the retrieved information
                self._on_result_callback(infohash, seeders, leechers)

                # remove this infohash in the infohash list of this session
                if infohash in unprocessed_infohash_list:
                    unprocessed_infohash_list.remove(infohash)

        elif 'failure reason' in response_dict:
            self._logger.debug(u"%s Failure as reported by tracker [%s]", self, repr(response_dict['failure reason']))

            return False

        # handle the infohashes with no result (seeders/leechers = 0/0)
        for infohash in unprocessed_infohash_list:
            seeders, leechers = 0, 0
            # handle the retrieved information
            self._on_result_callback(infohash, seeders, leechers)
        return True


class UdpTrackerSession(TrackerSession):

    # A list of transaction IDs that have been used in order to avoid conflict.
    _active_session_dict = dict()

    def __init__(self, tracker_url, tracker_address, announce_page, on_result_callback):
        super(UdpTrackerSession, self).__init__(u'UDP', tracker_url, tracker_address, announce_page, on_result_callback)
        self._connection_id = 0
        self._transaction_id = 0

    @staticmethod
    def generate_transaction_id(session):
        while True:
            # make sure there is no duplicated transaction IDs
            transaction_id = random.randint(0, MAX_INT32)
            if transaction_id not in UdpTrackerSession._active_session_dict.items():
                UdpTrackerSession._active_session_dict[session] = transaction_id
                session.transactionId = transaction_id
                break

    @staticmethod
    def remove_transaction_id(session):
        if session in UdpTrackerSession._active_session_dict:
            del UdpTrackerSession._active_session_dict[session]

    def cleanup(self):
        UdpTrackerSession.remove_transaction_id(self)
        super(UdpTrackerSession, self).cleanup()

    def max_retries(self):
        return UDP_TRACKER_MAX_RETRIES

    def retry_interval(self):
        return UDP_TRACKER_RECHECK_INTERVAL * (2 ** self._retries)

    def create_connection(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(0)
        self._socket.connect(self._tracker_address)

        return self.recreate_connection()

    def recreate_connection(self):
        # prepare connection message
        self._connection_id = UDP_TRACKER_INIT_CONNECTION_ID
        self._action = TRACKER_ACTION_CONNECT
        UdpTrackerSession.generate_transaction_id(self)

        message = struct.pack('!qii', self._connection_id, self._action, self._transaction_id)
        try:
            self._socket.send(message)
        except Exception as e:
            self._logger.debug(u"%s Failed to send message: %s", self, e)
            self._is_failed = True
            return False

        self._last_contact = int(time.time())
        return True

    def _handle_connection(self):
        try:
            # TODO: this number may be increased
            response = self._socket.recv(32)
        except Exception as e:
            self._logger.error(u"%s Failed to receive UDP CONNECT response: %s", self, e)
            self._is_failed = True
            return

        # check message size
        if len(response) < 16:
            self._logger.error(u"%s Invalid response for UDP CONNECT: %s", self, repr(response))
            self._is_failed = True
            return

        # check the response
        action, transaction_id = struct.unpack_from('!ii', response, 0)
        if action != self._action or transaction_id != self._transaction_id:
            # get error message
            errmsg_length = len(response) - 8
            error_message = struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)

            self._logger.error(u"%s Error response for UDP CONNECT [%s]: %s",
                               self, repr(response), repr(error_message))
            self._is_failed = True
            return

        # update action and IDs
        self._connection_id = struct.unpack_from('!q', response, 8)[0]
        self._action = TRACKER_ACTION_SCRAPE
        UdpTrackerSession.generate_transaction_id(self)

        # pack and send the message
        fmt = '!qii' + ('20s' * len(self._infohash_list))
        message = struct.pack(fmt, self._connection_id, self._action, self._transaction_id, *self._infohash_list)

        try:
            self._socket.send(message)
        except Exception as e:
            self._logger.debug(u"%s Failed to send UDP SCRAPE message: %s", self, e)
            self._is_failed = True
            return

        # no more requests can be appended to this session
        self._is_initiated = True
        self._last_contact = int(time.time())

    def _handle_response(self):
        try:
            # 74 infohashes are roughly 896 bytes
            # TODO: the receive number may be changed
            response = self._socket.recv(1024)
        except Exception as e:
            self._logger.error(u"%s Failed to receive UDP SCRAPE response: %s", self, e)
            self._is_failed = True
            return

        # check message size
        if len(response) < 8:
            self._logger.error(u"%s Invalid response for UDP SCRAPE: %s", self, repr(response))
            self._is_failed = True
            return

        # check response
        action, transaction_id = struct.unpack_from('!ii', response, 0)
        if action != self._action or transaction_id != self._transaction_id:
            # get error message
            errmsg_length = len(response) - 8
            error_message = \
                struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)

            self._logger.error(u"%s Error response for UDP SCRAPE: [%s] [%s]",
                               self, repr(response), repr(error_message))
            self._is_failed = True
            return

        # get results
        if len(response) - 8 != len(self._infohash_list) * 12:
            self._logger.error(u"%s UDP SCRAPE response mismatch: %s", self, repr(response))
            self._is_failed = True
            return

        offset = 8
        for infohash in self._infohash_list:
            seeders, completed, leechers = struct.unpack_from('!iii', response, offset)
            offset += 12

            # handle the retrieved information
            self._on_result_callback(infohash, seeders, leechers)

        # close this socket and remove its transaction ID from the list
        UdpTrackerSession.remove_transaction_id(self)
        self._is_finished = True
