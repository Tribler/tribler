# ============================================================
# Written by Lipu Fei
# optimizing the TrackerChecking module written by Niels Zeilemaker.
#
# The tracker session modules.
# ============================================================
from abc import ABCMeta, abstractmethod

import sys
import struct
import binascii
import random
import urllib
import time
import logging

import socket
from threading import RLock

from Tribler.Core.Utilities.bencode import bdecode
from traceback import print_exc
from Tribler.Core import NoDispersyRLock

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

# some settings

# ============================================================
# The abstract TrackerSession class. It represents a session with a tracker.
# ============================================================
class TrackerSession(object):

    __metaclass__ = ABCMeta

    # ----------------------------------------
    # Initializes a TrackerSession.
    # ----------------------------------------
    def __init__(self, tracker, tracker_type, tracker_address, announce_page, \
            update_result_callback):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._tracker = tracker
        self._tracker_type = tracker_type
        self._tracker_address = tracker_address
        self._announce_page = announce_page

        self._socket = None
        self._infohash_list = list()
        self._initiated = False
        self._action = None
        self._update_result_callback = update_result_callback

        self._finished = False
        self._failed = False
        self._retries = 0
        self._last_contact = 0

    # ----------------------------------------
    # Cleans up this tracker session.
    # ----------------------------------------
    def cleanup(self):
        if self._socket:
            self._socket.close()

    # ----------------------------------------
    # A factory method that creates a new session from a given tracker URL.
    # ----------------------------------------
    @staticmethod
    def createSession(tracker_url, update_result_callback):
        tracker_type, tracker_address, announce_page = \
           TrackerSession.parseTrackerUrl(tracker_url)

        if tracker_type == 'UDP':
            session = UdpTrackerSession(tracker_url, tracker_address, \
                announce_page, update_result_callback)
        else:
            session = HttpTrackerSession(tracker_url, tracker_address, \
                announce_page, update_result_callback)
        return session

    # ----------------------------------------
    # Parses a tracker URL to retrieve (1) the tracker type (HTTP or UDP),
    # (2) the tracker address which includes the IP address and the port
    # number, and (3) the tracker page which is something like '/announce',
    # '/announce.php', etc.
    # ----------------------------------------
    @staticmethod
    def parseTrackerUrl(tracker_url):
        # get tracker type
        if tracker_url.startswith('http'):
            tracker_type = 'HTTP'
        elif tracker_url.startswith('udp'):
            tracker_type = 'UDP'
        else:
            raise RuntimeError('Unexpected tracker type.')

        # get URL information
        url_fields = tracker_url.split('://')[1]
        # some UDP trackers may not have 'announce' at the end.
        if url_fields.find('/') == -1:
            if tracker_type == 'UDP':
                hostname_part = url_fields
                announce_page = None
            else:
                raise RuntimeError('Invalid tracker URL (%s).' % tracker_url)
        else:
            hostname_part, announce_page = url_fields.split('/', 1)

        # get port number if exists, otherwise, use HTTP default 80
        if hostname_part.find(':') != -1:
            hostname, port = hostname_part.split(':', 1)
            try:
                port = int(port)
            except:
                raise RuntimeError('Invalid port number.')
        elif tracker_type == 'HTTP':
            hostname = hostname_part
            port = 80
        else:
            raise RuntimeError('No port number for UDP tracker URL.')

        try:
            hostname = socket.gethostbyname(hostname)
        except:
            raise RuntimeError('Cannot resolve tracker URL.')

        return tracker_type, (hostname, port), announce_page

    # ----------------------------------------
    # (Public API) Handles the request, invoking the corresponding method.
    # ----------------------------------------
    def handleRequest(self):
        if self._action == TRACKER_ACTION_CONNECT:
            return self.handleConnection()
        else:
            return self.handleResponse()

    # ----------------------------------------
    # (Public API) Gets the tracker URL of this tracker session.
    # ----------------------------------------
    def getTracker(self):
        return self._tracker

    # ----------------------------------------
    # (Public API) Checks if this tracker session is of a specific
    # tracker type.
    # ----------------------------------------
    def isTrackerType(self, tracker_type):
        return self._tracker_type == tracker_type

    # ----------------------------------------
    # (Public API) Checks if this tracker session is in a specific
    # action.
    # ----------------------------------------
    def isAction(self, action):
        return self._action == action

    # ----------------------------------------
    # (Public API) Gets the socket of this tracker session.
    # ----------------------------------------
    def getSocket(self):
        return self._socket

    # ----------------------------------------
    # (Public API) Checks if this tracker session has initiated
    # (which means no more infohashes can be appended).
    # ----------------------------------------
    def hasInitiated(self):
        return self._initiated

    # ----------------------------------------
    # (Public API) Checks if this tracker session has finished.
    # ----------------------------------------
    def hasFinished(self):
        return self._finished

    # ----------------------------------------
    # (Public API) Sets the finished flag and closes the socket.
    # ----------------------------------------
    def setFinished(self):
        self._socket.close()
        self._finished = True

    # ----------------------------------------
    # (Public API) Checks if this tracker session has failed.
    # ----------------------------------------
    def hasFailed(self):
        return self._failed

    # ----------------------------------------
    # (Public API) Sets the failed flag.
    # ----------------------------------------
    def setFailed(self):
        self._socket.close()
        self._failed = True

    # ----------------------------------------
    # (Public API) Appends an infohash into the infohash list.
    # ----------------------------------------
    def addInfohash(self, infohash):
        return self._infohash_list.append(infohash)

    # ----------------------------------------
    # (Public API) Checks if an infohash is in the infohash list.
    # ----------------------------------------
    def hasInfohash(self, infohash):
        return infohash in self._infohash_list

    # ----------------------------------------
    # (Public API) Gets the infohash list.
    # ----------------------------------------
    def getInfohashList(self):
        return self._infohash_list

    # ----------------------------------------
    # (Public API) Gets the infohash list size.
    # ----------------------------------------
    def getInfohashListSize(self):
        return len(self._infohash_list)

    # ----------------------------------------
    # Gets the last time this session made a contact with the tracker.
    # ----------------------------------------
    def getLastContact(self):
        return self._last_contact

    # ----------------------------------------
    # Gets the retry count.
    # ----------------------------------------
    def getRetries(self):
        return self._retries

    # ----------------------------------------
    # Increases the retry count by 1.
    # ----------------------------------------
    def increaseRetries(self):
        self._retries += 1

    # ========================================
    # Abstract methods.
    # ========================================
    @abstractmethod
    def establishConnection(self):
        """Establishes a connection to the tracker."""
        pass

    @abstractmethod
    def reestablishConnection(self):
        """Re-Establishes a connection to the tracker."""
        pass

    @abstractmethod
    def handleConnection(self):
        """Handles a connection response."""
        pass

    @abstractmethod
    def handleResponse(self):
        """Does process when a response message is available."""
        pass

    @abstractmethod
    def getMaxRetries(self):
        """Nr of retries before a session is marked as failed"""
        pass

    @abstractmethod
    def getRetryInterval(self):
        """Interval between retries"""
        pass

# ============================================================
# The HTTP tracker session class which is responsible to do scrape on an HTTP
# tracker.
#
# Note: This class is not thread-safe right now. If you want to make this a
# standalone thread-safe module, you can add a static lock for the transaction
# ID handling functions.
# ============================================================
class HttpTrackerSession(TrackerSession):

    # ----------------------------------------
    # Initializes a UDPTrackerSession.
    # ----------------------------------------
    def __init__(self, tracker, tracker_address, announce_page, \
            update_result_callback):
        TrackerSession.__init__(self, tracker, \
            'HTTP', tracker_address, announce_page, \
            update_result_callback)

        self._header_buffer = None
        self._message_buffer = None
        self._content_encoding = None
        self._content_length = None
        self._received_length = None

    # ----------------------------------------
    # Gets the max retry count.
    # ----------------------------------------
    def getMaxRetries(self):
        return HTTP_TRACKER_MAX_RETRIES

    # ----------------------------------------
    # Gets interval between retries, in seconds.
    # ----------------------------------------
    def getRetryInterval(self):
        return HTTP_TRACKER_RECHECK_INTERVAL

    # ----------------------------------------
    # Establishes connection.
    # ----------------------------------------
    def establishConnection(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setblocking(0)

        return self.reestablishConnection()

    # ----------------------------------------
    # Re-establishes connection.
    # ----------------------------------------
    def reestablishConnection(self):
        # an exception may be raised if the socket is non-blocking
        try:
            self._socket.connect(self._tracker_address)

        except Exception as e:
            # Error number 115 means the opertion is in progress.
            if e[0] not in [115, 10035]:
                self._logger.debug('TrackerSession: Failed to connect to HTTP tracker [%s,%s]: %s', self._tracker, self._tracker_address, str(e))
                self.setFailed()
                return False

        self._action = TRACKER_ACTION_CONNECT
        self._last_contact = int(time.time())
        return True

    # ----------------------------------------
    # Handles a connection response.
    # ----------------------------------------
    def handleConnection(self):
        # create the HTTP GET message
        # Note: some trackers have strange URLs, e.g.,
        #       http://moviezone.ws/announce.php?passkey=8ae51c4b47d3e7d0774a720fa511cc2a
        #       which has some sort of 'key' as parameter, so we need to check
        #       if there is already a parameter available
        message = 'GET '
        message += '/' + self._announce_page.replace('announce', 'scrape')
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
            self._logger.debug('TrackerSession: Failed to send HTTP SCRAPE message: %s', e)
            self.setFailed()

        self._logger.debug('TrackerSession: send %s', message)

        # no more requests can be appended to this session
        self._action = TRACKER_ACTION_SCRAPE
        self._initiated = True

    # ----------------------------------------
    # Handles a scrape response.
    # ----------------------------------------
    def handleResponse(self):
        try:
            # TODO: this buffer size may be changed
            response = self._socket.recv(8192)

        except Exception as e:
            self._logger.debug('TrackerSession: Failed to receive HTTP SCRAPE response: %s', e)
            self.setFailed()
            return

        self._logger.debug('TrackerSession: Got [%s] as a response', response)

        if not response:
            self.setFailed()
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
                self._header_buffer, self._message_buffer = \
                    self._header_buffer.split('\r\n\r\n', 1)

                self._received_length = len(self._message_buffer)
                self._processHeader()

        # the remaining part
        else:
            self._message_buffer += response
            self._received_length += len(response)


        # check the read count
        if self._received_length >= self._content_length:
            # process the retrieved information
            success = self._processScrapeResponse()
            if success:
                self.setFinished()
            else:
                self.setFailed()

        # wait for more
        else:
            pass

    # ----------------------------------------
    # Processes the header of the received SCRAPE response message.
    # ----------------------------------------
    def _processHeader(self):
        # get and check HTTP response code
        protocol, code, msg = self._header_buffer.split(' ', 2)
        if code == '301' or code == '302':
            idx = self._header_buffer.find('Location: ')
            if idx == -1:
                self.setFailed()
            else:
                new_location = (self._header_buffer[idx:].split('\r\n')[0]).split(' ')[1]
                try:
                    idx = new_location.find('info_hash=')
                    if idx != -1:
                        new_location = new_location[:idx]
                    if new_location[-1] != '/':
                        new_location += "/"
                    new_location += "announce"

                    tracker_type, tracker_address, announce_page = TrackerSession.parseTrackerUrl(new_location)
                    if tracker_type != self._tracker_type:
                        raise RuntimeError('cannot redirect to different trackertype')

                    else:
                        self._logger.debug('TrackerSession: we are being redirected %s', new_location)

                        self._tracker_address = tracker_address
                        self._announce_page = announce_page
                        self._socket.close()

                        self.reestablishConnection()

                except:
                    self._logger.debug('TrackerSession: cannot redirect trackertype changed %s', new_location)
                    print_exc()
                    self.setFailed()
            return

        if code != '200':
            # error response code
            self._logger.debug('TrackerSession: Error HTTP SCRAPE response code [%s, %s].', code, msg)
            self.setFailed()
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
            success = self._processScrapeResponse()
            if success:
                self.setFinished()
            else:
                self.setFailed()

        else:
            idx = idx + len('Content-Length: ')
            self._content_length = \
                int(self._header_buffer[idx:].split('\r\n', 1)[0].strip())

    # ----------------------------------------
    # Processes the complete received SCRAPE response message.
    # ----------------------------------------
    def _processScrapeResponse(self):
        # parse the retrived results
        try:
            response_dict = bdecode(self._message_buffer)
        except Exception as e:
            self._logger.debug('TrackerSession: Failed to decode bcode[%s].' % self._message_buffer)
            return False

        unprocessed_infohash_list = self._infohash_list[:]
        if 'files' in response_dict:
            for infohash in response_dict['files'].keys():
                downloaded = response_dict['files'][infohash].get('downloaded', 0)
                complete = response_dict['files'][infohash].get('complete', 0)
                incomplete = response_dict['files'][infohash].get('incomplete', 0)

                seeders = downloaded
                leechers = incomplete

                # handle the retrieved information
                self._update_result_callback(infohash, seeders, leechers)

                # remove this infohash in the infohash list of this session
                if infohash in unprocessed_infohash_list:
                    unprocessed_infohash_list.remove(infohash)

        elif 'failure reason' in response_dict:
            self._logger.debug('TrackerSession: Failure as reported by tracker [%s]', response_dict['failure reason'])

            return False

        # handle the infohashes with no result
        # (considers as the torrents with seeders/leechers=0/0)
        for infohash in unprocessed_infohash_list:
            seeders, leechers = 0, 0
            # handle the retrieved information
            self._update_result_callback(infohash, seeders, leechers)
        return True


# ============================================================
# The UDP tracker session class which is responsible to do scrape on a UDP
# tracker.
# ============================================================
class UdpTrackerSession(TrackerSession):

    # A list of transaction IDs that have been used
    # in order to avoid conflict.
    __active_session_dict = dict()
    __lock = NoDispersyRLock()

    # ----------------------------------------
    # Generates a new transaction ID for a given session.
    # ----------------------------------------
    @staticmethod
    def generateTransactionId(session):
        UdpTrackerSession.__lock.acquire()
        while True:
            # make sure there is no duplicated transaction IDs
            transaction_id = random.randint(0, MAX_INT32)
            if not transaction_id in UdpTrackerSession.__active_session_dict.items():
                UdpTrackerSession.__active_session_dict[session] = transaction_id
                session.transactionId = transaction_id
                break
        UdpTrackerSession.__lock.release()

    # ----------------------------------------
    # Removes the transaction ID of a given session from the list.
    # ----------------------------------------
    @staticmethod
    def removeTransactionId(session):
        UdpTrackerSession.__lock.acquire()
        if session in UdpTrackerSession.__active_session_dict:
            del UdpTrackerSession.__active_session_dict[session]
        UdpTrackerSession.__lock.release()

    # ----------------------------------------
    # Initializes a UdpTrackerSession.
    # ----------------------------------------
    def __init__(self, tracker, tracker_address, announce_page, \
            update_result_callback):
        TrackerSession.__init__(self, tracker, \
            'UDP', tracker_address, announce_page, update_result_callback)

        self._connection_id = 0
        self._transaction_id = 0

    # ----------------------------------------
    # Cleans up this UDP tracker session.
    # ----------------------------------------
    def cleanup(self):
        UdpTrackerSession.removeTransactionId(self)
        TrackerSession.cleanup(self)

    # ----------------------------------------
    # Gets the max retry count.
    # ----------------------------------------
    def getMaxRetries(self):
        return UDP_TRACKER_MAX_RETRIES

    # ----------------------------------------
    # Gets interval between retries, in seconds.
    # ----------------------------------------
    def getRetryInterval(self):
        return UDP_TRACKER_RECHECK_INTERVAL * (2 ** self.getRetries())

    # ----------------------------------------
    # Establishes connection.
    # ----------------------------------------
    def establishConnection(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(0)
        self._socket.connect(self._tracker_address)

        return self.reestablishConnection()

    # ----------------------------------------
    # Re-establishes connection.
    # ----------------------------------------
    def reestablishConnection(self):
        # prepare connection message
        self._connection_id = UDP_TRACKER_INIT_CONNECTION_ID
        self._action = TRACKER_ACTION_CONNECT
        UdpTrackerSession.generateTransactionId(self)

        message = struct.pack('!qii', \
            self._connection_id, self._action, self._transaction_id)
        try:
            self._socket.send(message)
        except Exception as e:
            self._logger.debug('TrackerSession: Failed to send message to UDP tracker [%s]: %s', self._tracker, str(e))
            self.setFailed()
            return False

        self._last_contact = int(time.time())
        return True

    # ----------------------------------------
    # Handles a connection response.
    # ----------------------------------------
    def handleConnection(self):
        try:
            # TODO: this number may be increased
            response = self._socket.recv(32)
        except Exception as e:
            self._logger.debug('TrackerSession: Failed to receive UDP CONNECT response: %s', e)
            self.setFailed()
            return

        # check message size
        if len(response) < 16:
            self._logger.debug('TrackerSession: Invalid response for UDP CONNECT [%s].', response)
            self.setFailed()
            return

        # check the response
        action, transaction_id = \
            struct.unpack_from('!ii', response, 0)
        if action != self._action or transaction_id != self._transaction_id:
            # get error message
            errmsg_length = len(response) - 8
            error_message = \
                struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)

            self._logger.debug('TrackerSession: Error response for UDP CONNECT [%s]: %s.', response, error_message)
            self.setFailed()
            return

        # update action and IDs
        self._connection_id = struct.unpack_from('!q', response, 8)[0]
        self._action = TRACKER_ACTION_SCRAPE
        UdpTrackerSession.generateTransactionId(self)

        # pack and send the message
        format = '!qii' + ('20s' * len(self._infohash_list))
        message = struct.pack(format, \
            self._connection_id, self._action, self._transaction_id, \
            *self._infohash_list)

        try:
            self._socket.send(message)
        except Exception as e:
            self._logger.debug('TrackerSession: Failed to send UDP SCRAPE message: %s', e)
            self.setFailed()
            return

        # no more requests can be appended to this session
        self._initiated = True
        self._last_contact = int(time.time())

    # ----------------------------------------
    # Handles a scrape response.
    # ----------------------------------------
    def handleResponse(self):
        try:
            # 74 infohashes are roughly 896 bytes
            # TODO: the number may be changed
            response = self._socket.recv(1024)
        except Exception as e:
            self._logger.debug('TrackerSession: Failed to receive UDP SCRAPE response: %s', e)
            self.setFailed()
            return

        # check message size
        if len(response) < 8:
            self._logger.debug('TrackerSession: Invalid response for UDP SCRAPE [%s].', response)
            self.setFailed()
            return

        # check response
        action, transaction_id = struct.unpack_from('!ii', response, 0)
        if action != self._action or transaction_id != self._transaction_id:
            # get error message
            errmsg_length = len(response) - 8
            error_message = \
                struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)

            self._logger.debug('TrackerSession: Error response for UDP SCRAPE [%s]: [%s].', response, error_message)
            self.setFailed()
            return

        # get results
        offset = 8
        for infohash in self._infohash_list:
            seeders, completed, leechers = \
                struct.unpack_from('!iii', response, offset)
            offset += 12

            # handle the retrieved information
            self._update_result_callback(infohash, seeders, leechers)

        # close this socket and remove its transaction ID from the list
        UdpTrackerSession.removeTransactionId(self)
        self.setFinished()
