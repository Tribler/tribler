# ============================================================
# Written by Lipu Fei
#
# The tracker session modules.
# ============================================================
from abc import ABCMeta, abstractmethod

import sys
import struct
import binascii
import random
import urllib

import socket
from threading import Lock

from Tribler.Core.Utilities.bencode import bdecode

# Although these are the actions for UDP trackers, they can still be used as
# identifiers.
TRACKER_ACTION_CONNECT  = 0
TRACKER_ACTION_ANNOUNCE = 1
TRACKER_ACTION_SCRAPE   = 2

MAX_INT32 = 2**16-1

UDP_TRACKER_INIT_CONNECTION_ID = 0x41727101980
UDP_TRACKER_RECHECK_INTERVAL = 15
UDP_TRACKER_MAX_RETRIES = 8

# ============================================================
# The abstract TrackerSession class. It represents a session with a tracker.
# ============================================================
class TrackerSession(object):

    __metaclass__ = ABCMeta

    # ----------------------------------------
    # Initializes a TrackerSession.
    # ----------------------------------------
    def __init__(self, tracker, tracker_type, tracker_address, announce_page,\
            update_result_callback):
        self._tracker         = tracker
        self._trackerType     = tracker_type
        self._tracker_address = tracker_address
        self._announce_page   = announce_page

        self._socket = None
        self._infohash_list = list()
        self._initiated = False
        self._action = None
        self._update_result_callback = update_result_callback

        self._finished = False
        self._failed   = False

    # ----------------------------------------
    # Deconstructor.
    # ----------------------------------------
    def __del__(self):
        if self._socket:
            self._socket.close()
            del self._socket

        del self._infohash_list
        del self._initiated
        del self._action

        del self._finished
        del self._failed

        del self._tracker
        del self._trackerType
        del self._tracker_address
        del self._announce_page

    # ----------------------------------------
    # A factory method that creates a new session from a given tracker URL.
    # ----------------------------------------
    @staticmethod
    def createSession(tracker_url, update_result_callback):
        tracker_type, tracker_address, announce_page =\
           TrackerSession.parseTrackerUrl(tracker_url)

        if tracker_type == 'UDP':
            session = UdpTrackerSession(tracker_url, tracker_address,\
                announce_page, update_result_callback)
        else:
            session = HttpTrackerSession(tracker_url, tracker_address,\
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
                raise RuntimeError('Invalid tracker URL.')
        else:
            hostname_part, announce_page = url_fields.split('/', 1)

        # get port number if exists, otherwise, use HTTP default 80
        if hostname_part.find(':') != -1:
            hostname, port = hostname_part.split(':', 1)
        else:
            hostname = hostname_part
            port = 80

        try:
            hostname = socket.gethostbyname(hostname)
            port = int(port)
        except:
            raise RuntimeError('Cannot resolve tracker URL.')

        return tracker_type, (hostname, port), announce_page


    # ----------------------------------------
    # Handles the request, invoking the corresponding method.
    # ----------------------------------------
    def handleRequest(self):
        if self.action == TRACKER_ACTION_CONNECT:
            return self.handleConnection()
        else:
            return self.handleResponse()

    # ========================================
    # Abstract methods.
    # ========================================
    @abstractmethod
    def establishConnection(self):
        """Establishes a connection to the tracker."""
        pass

    @abstractmethod
    def handleConnection(self):
        """Handles a connection response."""
        pass

    @abstractmethod
    def handleResponse(self):
        """Does process when a response message is available."""
        pass

    # ========================================
    # Methods for properties.
    # ========================================
    # tracker
    @property
    def tracker(self):
        return self._tracker
    @tracker.setter
    def tracker(self, tracker):
        self._tracker = tracker
    @tracker.deleter
    def tracker(self):
        del self._tracker

    # trackerType
    @property
    def trackerType(self):
        return self._trackerType
    @trackerType.setter
    def trackerType(self, trackerType):
        self._trackerType = trackerType
    @trackerType.deleter
    def trackerType(self):
        del self._trackerType

    # trackerAddress
    @property
    def trackerAddress(self):
        return self._tracker_address
    @trackerAddress.setter
    def trackerAddress(self, tracker_address):
        self._tracker_address = tracker_address
    @trackerAddress.deleter
    def trackerAddress(self):
        del self._tracker_address

    # announcePage
    @property
    def announcePage(self):
        return self._announce_page
    @announcePage.setter
    def announcePage(self, announce_page):
        self._announce_page = announce_page
    @announcePage.deleter
    def announcePage(self):
        del self._announce_page

    # socket
    @property
    def socket(self):
        return self._socket
    @socket.setter
    def socket(self, socket):
        self._socket = socket
    @socket.deleter
    def socket(self):
        del self._socket

    # infohashList
    @property
    def infohashList(self):
        return self._infohash_list
    @infohashList.setter
    def infohashList(self, infohash_list):
        self._infohash_list = infohash_list
    @infohashList.deleter
    def infohashList(self):
        del self._infohash_list

    # initiated
    @property
    def initiated(self):
        return self._initiated
    @initiated.setter
    def initiated(self, initiated):
        self._initiated = initiated
    @initiated.deleter
    def initiated(self):
        del self._initiated

    # action
    @property
    def action(self):
        return self._action
    @action.setter
    def action(self, action):
        self._action = action
    @action.deleter
    def action(self):
        del self._action

    # finished
    @property
    def finished(self):
        return self._finished
    @finished.setter
    def finished(self, finished):
        self._finished = finished
    @finished.deleter
    def finished(self):
        del self._finished

    # failed
    @property
    def failed(self):
        return self._failed
    @failed.setter
    def failed(self, failed):
        self._failed = failed
    @failed.deleter
    def failed(self):
        del self._failed

    # Callback function to update result
    @property
    def updateResultCallback(self):
        return self._update_result_callback
    @updateResultCallback.setter
    def updateResultCallback(self, update_result_callback):
        self._update_result_callback = update_result_callback
    @updateResultCallback.deleter
    def updateResultCallback(self):
        del self._update_result_callback


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
    def __init__(self, tracker, tracker_address, announce_page,\
            update_result_callback):
        TrackerSession.__init__(self, tracker,\
            'HTTP', tracker_address, announce_page,\
            update_result_callback)

        self._header_buffer = None
        self._message_buffer = None
        self._content_encoding = None
        self._content_length = None
        self._received_length = None

    # ----------------------------------------
    # Deconstructor.
    # ----------------------------------------
    def __del__(self):
        del self._received_length
        del self._content_length
        del self._content_encoding
        del self._message_buffer
        del self._header_buffer

        TrackerSession.__del__(self)

    # ----------------------------------------
    # Establishes connection.
    # ----------------------------------------
    def establishConnection(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(0)

        # an exception may be raised if the socket is non-blocking
        try:
            self.socket.connect(self.trackerAddress)
        except Exception as e:
            # Error number 115 means the opertion is in progress.
            if e[0] != 115:
                if DEBUG:
                    print >> sys.stderr, \
                        '[WARN] Failed to connect to HTTP tracker [%s]: %s' % \
                        (self.tracker, str(e))
                self.failed = True
                return False

        self.action = TRACKER_ACTION_CONNECT
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
        message += '/' + self.announcePage.replace('announce', 'scrape')
        if message.find('?') == -1:
            message += '?'
        else:
            message += '&'

        # append the infohashes as parameters
        for infohash in self.infohashList:
            message += 'info_hash='
            message += urllib.quote(infohash)
            message += '&'
        message = message[:-1] # remove the last AND '&'
        message += ' HTTP/1.1\r\n\r\n'

        try:
            self.socket.send(message)
        except Exception as e:
            if DEBUG:
                print >> sys.stderr, \
                    '[WARN] Failed to send HTTP SCRAPE message: ', \
                    e
            self.failed = True

        # no more requests can be appended to this session
        self.action = TRACKER_ACTION_SCRAPE
        self.initiated = True

    # ----------------------------------------
    # Handles a scrape response.
    # ----------------------------------------
    def handleResponse(self):
        try:
            # TODO: this buffer size may be changed
            response = self.socket.recv(8192)
        except Exception as e:
            if DEBUG:
                print >> sys.stderr, \
                    '[WARN] Failed to receive HTTP SCRAPE response:', \
                    e
            self.failed = True
            return

        # for the header message, we need to parse the content length in case
        # if the HTTP packets are partial.
        if not self.messageBuffer:
            # append the header part
            if not self.headerBuffer:
                self.headerBuffer = response
            else:
                self.headerBuffer += response

            # check if the header part is over
            if self.headerBuffer.find('\r\n\r\n') != -1:
                self.headerBuffer, self.messageBuffer = \
                    self.headerBuffer.split('\r\n\r\n', 1)

                self.receivedLength = len(self.messageBuffer)
                self._processHeader()

        # the remaining part
        else:
            self.messageBuffer += response
            self.receivedLength += len(response)

            # check the read count
            if self.receivedLength >= self.contentLength:
                # process the retrieved information
                success = self._processScrapeResponse()
                if success:
                    self.finished = True
                else:
                    self.failed = True
                self.socket.close()

            # wait for more
            else:
                pass

    # ----------------------------------------
    # Processes the header of the received SCRAPE response message.
    # ----------------------------------------
    def _processHeader(self):
        # get and check HTTP response code
        protocol, code, msg = self.headerBuffer.split(' ', 2)
        if code != '200':
            # error response code
            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Error HTTP SCRAPE response code [%s, %s].' % \
                (code, msg)
            self.failed = True
            self.socket.close()
            return

        # check the content type
        idx = self.headerBuffer.find('Content-Encoding: ')
        if idx == -1:
            # assuming it is plain text or something similar
            self.contentEncoding = 'plain'
        else:
            encoding = (self.headerBuffer[idx:].split('\r\n')[0]).split(' ')[1]
            self.contentEncoding = encoding

        # get the content length
        idx = self.headerBuffer.find('Content-Length: ')
        if idx == -1:
            # assume that the content is small

            # process the retrieved information
            success = self._processScrapeResponse()
            if success:
                self.finished = True
            else:
                self.failed = True
            self.socket.close()

        else:
            idx = idx + len('Content-Length: ')
            self.contentLength = \
                int(self.headerBuffer[idx:].split('\r\n', 1)[0].strip())

    # ----------------------------------------
    # Processes the complete received SCRAPE response message.
    # ----------------------------------------
    def _processScrapeResponse(self):
        # parse the retrived results
        try:
            response_dict = bdecode(self.messageBuffer)
        except Exception as e:
            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Failed to decode bcode[%s].' % self.messageBuffer
            return False

        unprocessed_infohash_list = self.infohashList[:]
        for infohash in response_dict['files'].keys():
            downloaded = response_dict['files'][infohash]['downloaded']
            complete = response_dict['files'][infohash]['complete']
            incomplete = response_dict['files'][infohash]['incomplete']

            seeders = downloaded
            leechers = incomplete

            # handle the retrieved information
            self.updateResultCallback(infohash, seeders, leechers)

            # remove this infohash in the infohash list of this session
            if infohash in unprocessed_infohash_list:
                unprocessed_infohash_list.remove(infohash)

        # handle the infohashes with no result
        # (considers as the torrents with seeders/leechers=0/0)
        for infohash in unprocessed_infohash_list:
            seeders, leechers = 0, 0
            # handle the retrieved information
            self.updateResultCallback(infohash, seeders, leechers)
        return True

    # ========================================
    # Methods for properties.
    # ========================================
    # headerBuffer
    @property
    def headerBuffer(self):
        return self._header_buffer
    @headerBuffer.setter
    def headerBuffer(self, header_buffer):
        self._header_buffer = header_buffer
    @headerBuffer.deleter
    def headerBuffer(self):
        del self._header_buffer

    # messageBuffer
    @property
    def messageBuffer(self):
        return self._message_buffer
    @messageBuffer.setter
    def messageBuffer(self, message_buffer):
        self._message_buffer = message_buffer
    @messageBuffer.deleter
    def messageBuffer(self):
        del self._message_buffer

    # contentEncoding
    @property
    def contentEncoding(self):
        return self._content_encoding
    @contentEncoding.setter
    def contentEncoding(self, content_encoding):
        self._content_encoding = content_encoding
    @contentEncoding.deleter
    def contentEncoding(self):
        del self._content_encoding

    # contentLength
    @property
    def contentLength(self):
        return self._content_length
    @contentLength.setter
    def contentLength(self, content_length):
        self._content_length = content_length
    @contentLength.deleter
    def contentLength(self):
        del self._content_length

    # receivedLength
    @property
    def receivedLength(self):
        return self._received_length
    @receivedLength.setter
    def receivedLength(self, received_length):
        self._received_length = received_length
    @receivedLength.deleter
    def receivedLength(self):
        del self._received_length



# ============================================================
# The UDP tracker session class which is responsible to do scrape on a UDP
# tracker.
# ============================================================
class UdpTrackerSession(TrackerSession):

    # A list of transaction IDs that have been used
    # in order to avoid conflict.
    __active_session_dict = dict()
    __lock = Lock()

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
    def __init__(self, tracker, tracker_address, announce_page,\
            update_result_callback):
        TrackerSession.__init__(self, tracker,\
            'UDP', tracker_address, announce_page, update_result_callback)

        self._connection_id = 0
        self._transaction_id = 0

        self._last_contact = 0
        self._retries = 0

    # ----------------------------------------
    # Deconstructor.
    # ----------------------------------------
    def __del__(self):
        UdpTrackerSession.removeTransactionId(self)

        del self._retries
        del self._last_contact

        del self._connection_id
        del self._transaction_id

        TrackerSession.__del__(self)

    # ----------------------------------------
    # Establishes connection.
    # ----------------------------------------
    def establishConnection(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(0)
        self.socket.connect(self.trackerAddress)

        # prepare connection message
        self.connectionId = UDP_TRACKER_INIT_CONNECTION_ID
        self.action = TRACKER_ACTION_CONNECT
        UdpTrackerSession.generateTransactionId(self)

        message = struct.pack('!qii', \
            self.connectionId, self.action, self.transactionId)
        try:
            self.socket.send(message)
        except Exception as e:
            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Failed to send message to UDP tracker [%s]: %s' % \
                (self.tracker, str(e))
            self.failed = True
            return False

        self.lastContact = int(time.time())
        return True

    # ----------------------------------------
    # Re-establishes connection.
    # ----------------------------------------
    def reestablishConnection(self):
        # prepare connection message
        self.connectionId = UDP_TRACKER_INIT_CONNECTION_ID
        self.action = TRACKER_ACTION_CONNECT
        UdpTrackerSession.generateTransactionId(self)

        message = struct.pack('!qii', \
            self.connectionId, self.action, self.transactionId)
        try:
            self.socket.send(message)
        except Exception as e:
            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Failed to send message to UDP tracker [%s]: %s' % \
                (self.tracker, str(e))
            self.failed = True
            return False

        self.lastContact = int(time.time())
        return True

    # ----------------------------------------
    # Handles a connection response.
    # ----------------------------------------
    def handleConnection(self):
        try:
            # TODO: this number may be increased
            response = self.socket.recv(32)
        except Exception as e:
            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Failed to receive UDP CONNECT response:', e
            self.failed = True
            return

        # check message size
        if len(response) < 16:
            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Invalid response for UDP CONNECT [%s].' % response
            self.failed = True
            return

        # check the response
        action, transaction_id = \
            struct.unpack_from('!ii', response, 0)
        if action != self.action or transaction_id != self.transactionId:
            # get error message
            errmsg_length = len(response) - 8
            error_message = \
                struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)

            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Error response for UDP CONNECT [%s]: %s.' % \
                (response, error_message)
            self.failed = True
            return

        # update action and IDs
        self.connectionId = struct.unpack_from('!q', response, 8)[0]
        self.action = TRACKER_ACTION_SCRAPE
        UdpTrackerSession.generateTransactionId(self)

        # pack and send the message
        format = '!qii' + ('20s' * len(self.infohashList))
        message = struct.pack(format, \
            self.connectionId, self.action, self.transactionId, \
            *self.infohashList)

        try:
            self.socket.send(message)
        except Exception as e:
            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Failed to send UDP SCRAPE message:', e
            self.failed = True
            return

        # no more requests can be appended to this session
        self.initiated = True
        self.lastContact = int(time.time())

    # ----------------------------------------
    # Handles a scrape response.
    # ----------------------------------------
    def handleResponse(self):
        try:
            # 74 infohashes are roughly 896 bytes
            # TODO: the number may be changed
            response = self.socket.recv(1024)
        except Exception as e:
            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Failed to receive UDP SCRAPE response:', e
            self.failed = True
            return

        # check message size
        if len(response) < 8:
            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Invalid response for UDP SCRAPE [%s].' % response
            self.failed = True
            return

        # check response
        action, transaction_id = struct.unpack_from('!ii', response, 0)
        if action != self.action or transaction_id != self.transactionId:
            # get error message
            errmsg_length = len(response) - 8
            error_message = \
                struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)

            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Error response for UDP SCRAPE [%s]: [%s].' % \
                (response, error_message)
            self.failed = True
            return

        # get results
        offset = 8
        for infohash in self.infohashList:
            seeders, completed, leechers = \
                struct.unpack_from('!iii', response, offset)
            offset += 12

            # handle the retrieved information
            self.updateResultCallback(infohash, seeders, leechers)

        # close this socket and remove its transaction ID from the list
        UdpTrackerSession.removeTransactionId(self)
        self.finished = True
        self.socket.close()

    # ========================================
    # Methods for properties.
    # ========================================
    # connectionId
    @property
    def connectionId(self):
        return self._connection_id
    @connectionId.setter
    def connectionId(self, connectionId):
        self._connection_id = connectionId
    @connectionId.deleter
    def connectionId(self):
        del self._connection_id

    # transactionId
    @property
    def transactionId(self):
        return self._transaction_id
    @transactionId.setter
    def transactionId(self, transactionId):
        self._transaction_id = transactionId
    @transactionId.deleter
    def transactionId(self):
        del self._transaction_id

    # lastContact
    @property
    def lastContact(self):
        return self._last_contact
    @lastContact.setter
    def lastContact(self, last_contact):
        self._last_contact = last_contact
    @lastContact.deleter
    def lastContact(self):
        del self._last_contact

    # retries
    @property
    def retries(self):
        return self._retries
    @retries.setter
    def retries(self, retries):
        self._retries = retries
    @retries.deleter
    def retries(self):
        del self._retries
