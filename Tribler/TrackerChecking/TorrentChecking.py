# ============================================================
# Written by Lipu Fei,
# optimizing the TrackerChecking module built by Niels Zeilemaker.
#
# see LICENSE.txt for license information
#
# TODO: add comments
# ============================================================
import sys
import binascii
import time

import select
import socket

import threading
from threading import Thread, Lock

from traceback import print_exc, print_stack

from Tribler.TrackerChecking.TrackerInfoCache import TrackerInfoCache

from Tribler.Core.Utilities.utilities import parse_magnetlink
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.Core.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker

from Tribler.Core.CacheDB.sqlitecachedb import str2bin


# some settings
DEBUG = True

# ============================================================
# This is the single-threaded tracker checking class.
# ============================================================
class TorrentChecking(Thread):

    __single = None

    # ------------------------------------------------------------
    # Intialization.
    # ------------------------------------------------------------
    def __init__(self):
        if TorrentChecking.__single:
            raise RuntimeError("Torrent Checking is singleton")
        TorrentChecking.__single = self

        Thread.__init__(self)

        self.setName('TorrentChecking' + self.getName())
        if DEBUG:
            print >> sys.stderr, \
            '[DEBUG] Starting TorrentChecking from %s.' % \
            threading.currentThread().getName()
        self.setDaemon(True)

        self._mldhtchecker = mainlineDHTChecker.getInstance()
        self._torrentdb = TorrentDBHandler.getInstance()

        # TODO: make these configurable
        self._select_timeout = 5

        self._lock = Lock()
        self._session_dict = dict()
        self._pending_response_dict = dict()

        # initialize a tracker status cache, TODO: add parameters
        self._tracker_info_cache = TrackerInfoCache()

        self._tracker_selection_idx = 0
        self._torrent_select_interval = 60
        self._torrent_check_interval = 30

        self._should_stop = False

        self.start()


    # ------------------------------------------------------------
    # (Public API)
    # The public interface to initialize and get the single instance.
    # ------------------------------------------------------------
    @staticmethod
    def getInstance(*args, **kw):
        if TorrentChecking.__single is None:
            TorrentChecking(*args, **kw)
        return TorrentChecking.__single


    # ------------------------------------------------------------
    # (Public API)
    # The public interface to delete the single instance.
    # ------------------------------------------------------------
    @staticmethod
    def delInstance():
        TorrentChecking.__single = None


    def shutdown(self):
        self._should_stop = True

    # ------------------------------------------------------------
    # (Public API)
    # The public API interface to add a torrent check request. Returns true
    # if successful, false otherwise.
    # Note that, the input argument "gui_torrent" is of class
    # "Tribler.Main.Utility.GuiDBTuples.Torrent", NOT "Core.TorrentDef"!
    # So you need to get the TorrentDef to access more information
    # ------------------------------------------------------------
    def addTorrentToQueue(self, gui_torrent):
        if gui_torrent._torrent_id == -1:
            return False

        infohash = gui_torrent.infohash

        # get torrent's tracker list
        self._lock.acquire()
        retries, last_check, tracker_list = \
            self._getTorrentInfo(infohash, gui_torrent)
        self._lock.release()
        if not tracker_list:
            # TODO: add method to handle torrents with no tracker
            return False

        # for each valid tracker, try to (1) append a request or
        # (2) create a new session.
        successful = False
        for tracker_url in tracker_list:
            self._lock.acquire()
            # check if this tracker is worth checking
            if not self._tracker_info_cache.toCheckTracker(tracker_url):
                self._lock.release()
                continue

            # >> Step 1: Try to append the request to an existing session
            # check there is any existing session that scrapes this torrent
            request_handled = False
            for _, session in self._session_dict.items():
                if session.tracker != tracker_url:
                    continue

                if session.failed:
                    continue

                if infohash in session.infohashList:
                    # a torrent check is already there, ignore this request
                    request_handled = True
                    break
                else:
                    if not session.initiated:
                        # only append when the request is less than 74
                        if len(session.infohashList) < 74:
                            session.infohashList.append(infohash)
                            self._updatePendingResponseDict(infohash, retries, last_check)
                            request_handled = True
                            break

            self._lock.release()
            if request_handled:
                successful = True
                continue

            # >> Step 2: No session to append to, create a new one
            # create a new session for this request
            self._lock.acquire()
            session = None
            try:
                session = TrackerSession.createSession(tracker_url)

                connectionEstablished = session.establishConnection()
                if not connectionEstablished:
                    raise RuntimeError('Cannot establish connection.')

                session.infohashList.append(infohash)
                self._session_dict[session.socket] = session
                # update the number of responses this torrent is expecting
                self._updatePendingResponseDict(infohash, retries, last_check)

                successful = True

            except Exception as e:
                if DEBUG:
                    print >> sys.stderr, \
                    '[WARN] Failed to create session for tracker[%s]: %s' % \
                    (tracker_url, e)
                if session:
                    del session
                self._tracker_info_cache.updateTrackerInfo(tracker_url, False)
                successful = False
            self._lock.release()

        return successful

    # ------------------------------------------------------------
    # Gets the information of a given torrent. This method first checks
    # the DB. If there is no tracker in the DB, it then retrieves trackers
    # from magnet links and gui_torrent's "trackers" field and update the
    # DB.
    # ------------------------------------------------------------
    def _getTorrentInfo(self, infohash, gui_torrent=None):
        # see if we can find anything from DB
        torrent = self._torrentdb.getTorrent(infohash)
        retries = torrent['tracker_check_retries']
        last_check = torrent['last_tracker_check']
        if torrent and 'tracker_list' in torrent and torrent['tracker_list']:
            return (retries, last_check, torrent['tracker_list'])

        # no tracker in DB, get torrent's trackers
        tracker_list = list()
        # check its magnet link
        source_list = self._torrentdb.getTorrentCollecting(gui_torrent._torrent_id)
        for source,  in source_list:
            if source.startswith('magnet'):
                dn, xt, trackers = parse_magnetlink(source)
                if len(trackers) > 0:
                    tracker_list.extend(trackers)
        # check its trackers
        if 'trackers' in gui_torrent:
            for tracker in gui_torrent.trackers:
                if not tracker in tracker_list:
                    tracker_list.append(tracker)

        # update the DB with torrent's trackers
        self._updateTorrentTrackerList(infohash, tracker_list)

        return (retries, last_check, tracker_list)

    # ------------------------------------------------------------
    # Updates the pending response dictionary.
    # ------------------------------------------------------------
    def _updatePendingResponseDict(self, infohash, retries=None, last_check=None):
        if infohash in self._pending_response_dict:
            self._pending_response_dict[infohash]['remainingResponses'] += 1
            self._pending_response_dict[infohash]['updated'] = False
        else:
            self._pending_response_dict[infohash] = dict()
            self._pending_response_dict[infohash]['infohash'] = infohash
            self._pending_response_dict[infohash]['remainingResponses'] = 1
            self._pending_response_dict[infohash]['seeders'] = -2
            self._pending_response_dict[infohash]['leechers'] = -2
            self._pending_response_dict[infohash]['updated'] = False
            self._pending_response_dict[infohash]['retries'] = retries

    # ------------------------------------------------------------
    # Updates the result of a pending request.
    # This method is only used by TrackerSession to update a retrieved result.
    # ------------------------------------------------------------
    def updateResultFromSession(self, infohash, seeders, leechers):
        response = self._pending_response_dict[infohash]
        response['last_check'] = int(time.time())
        if response['seeders'] < seeders or \
                (response['seeders'] == seeders and response['leechers'] < leechers):
            response['seeders'] = seeders
            response['leechers'] = leechers
            response['updated'] = True
            response['retries'] = 0 # a successful update


    # ------------------------------------------------------------
    # Updates a torrent's tracker into the database.
    # ------------------------------------------------------------
    @forceDBThread
    def _updateTorrentTrackerList(self, infohash, tracker_list):
        if not tracker_list:
            return

        trackers_data = ''
        for tracker in tracker_list:
            trackers_data += tracker
            trackers_data += '\n'
        trackers_data = trackers_data[:-1]

        kw = {'trackers': trackers_data }
        self._torrentdb.updateTorrent(infohash, **kw)

    # ------------------------------------------------------------
    # Updates result into the database.
    # ------------------------------------------------------------
    @forceDBThread
    def _updateTorrentResult(self, response):
        seeders  = response['seeders']
        leechers = response['leechers']
        retries  = response['retries']
        last_check = response['last_check']

        # the torrent status logic, TODO: do it in other way
        status = 'unknown'
        if seeders > 0:
            status = 'good'
        elif seeders == 0:
            status = 'dead'

        if status != 'good':
            retries += 1

        kw = {'seeder': seeders, 'leecher': leechers, 'status': status, \
            'retries': retries, 'last_tracker_check': last_check}
        self._torrentdb.updateTorrent(response['infohash'], **kw)

    # ------------------------------------------------------------
    # Updates the check result into the database
    # This is for the torrents whose checks have failed and the results
    # will be -2/-2 at last.
    # ------------------------------------------------------------
    @forceDBThread
    def _checkResponseFinal(self, response):
        seeders  = response['seeders']
        leechers = response['leechers']
        retries  = response['retries']

        if seeders >= 0 and leechers >= 0:
            return

        last_check = int(time.time())
        # the torrent status logic, TODO: do it in other way
        status = 'unknown'
        if seeders > 0:
            status = 'good'
        elif seeders == 0:
            status = 'dead'

        if status != 'good':
            retries += 1

        kw = {'seeder': seeders, 'leecher': leechers, 'status': status, \
              'retries': retries, 'last_tracker_check': last_check}
        self._torrentdb.updateTorrent(response['infohash'], **kw)

    # ------------------------------------------------------------
    # (Unit test method)
    # Adds an infohash and the tracker to check
    # ------------------------------------------------------------
    def _test_checkInfohash(self, infohash, tracker):
        self._lock.acquire()

        session = TrackerSession.createSession(tracker)
        session.establishConnection()
        session.infohashList.append(infohash)
        self._session_dict[session.socket] = session
        self._updatePendingResponseDict(infohash, retries=0, last_check=0)

        self._lock.release()

    # ------------------------------------------------------------
    # Selects torrents to check.
    # This method selects trackers in Round-Robin fashion.
    # ------------------------------------------------------------
    def _selectTorrentsToCheck(self):
        tracker = None
        check_torrent_list = list()

        current_time = int(time.time())
        while True:
            if self._tracker_selection_idx >= len(self._tracker_info_cache.trackerInfoDict):
                return None, None

            tracker, _ = \
                self._tracker_info_cache.trackerInfoDict.items()[self._tracker_selection_idx]
            # skip the dead trackers
            if not self._tracker_info_cache.toCheckTracker(tracker):
                self._tracker_selection_idx += 1
                if self._tracker_selection_idx >= len(self._tracker_info_cache.trackerInfoDict):
                    self._tracker_selection_idx = 0
                continue

            # get all the torrents on this tracker
            all_torrent_list = self._torrentdb.getTorrentsOnTracker(tracker)
            if not all_torrent_list:
                break

            # get the torrents that should be checked
            for torrent in all_torrent_list:
                # check interval
                retries = torrent[1]
                last_check = torrent[2]
                interval = current_time - last_check

                # recheck interval is: interval * 2^(retries)
                if interval < self._torrent_check_interval**retries:
                    continue

                check_torrent_list.append(torrent)

            # create sessions for the torrents that need to be checked
            for torrent in check_torrent_list:
                # TODO
                infohash = str2bin(torrent[0])
                retries = torrent[1]
                last_check = torrent[2]

                if DEBUG:
                    print >> sys.stderr, \
                    '[!!!] Adding torrent[%s].' % binascii.b2a_hex(infohash)
                self._addInfohashToQueue(infohash, retries, last_check, tracker)

            del check_torrent_list
            del all_torrent_list

            break

        # update the tracker index
        self._tracker_selection_idx += 1
        if self._tracker_selection_idx >= len(self._tracker_info_cache.trackerInfoDict):
            self._tracker_selection_idx = 0

    # ------------------------------------------------------------
    # Adds a request to the queue.
    # ------------------------------------------------------------
    def _addInfohashToQueue(self, infohash, retries, last_check, tracker):
        # check if this tracker is worth checking
        if not self._tracker_info_cache.toCheckTracker(tracker):
            return

        # >> Step 1: Try to append the request to an existing session
        # check there is any existing session that scrapes this torrent
        request_handled = False
        for _, session in self._session_dict.items():
            if session.tracker != tracker:
                continue

            if session.failed:
                continue

            if infohash in session.infohashList:
                # a torrent check is already there, ignore this request
                request_handled = True
                break
            else:
                if not session.initiated:
                    # only append when the request is less than 74
                    if len(session.infohashList) < 74:
                        session.infohashList.append(infohash)
                        self._updatePendingResponseDict(infohash, retries, last_check)
                        request_handled = True
                        break
        if request_handled:
            return

        # >> Step 2: No session to append to, create a new one
        # create a new session for this request
        session = None
        try:
            session = TrackerSession.createSession(tracker)

            connectionEstablished = session.establishConnection()
            if not connectionEstablished:
                raise RuntimeError('Cannot establish connection.')

            session.infohashList.append(infohash)
            self._session_dict[session.socket] = session
            # update the number of responses this torrent is expecting
            self._updatePendingResponseDict(infohash, retries, last_check)

        except Exception as e:
            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Failed to create session for tracker[%s]: %s' % \
                (tracker, e)
            if session:
                del session
            self._tracker_info_cache.updateTrackerInfo(tracker, False)

    # ------------------------------------------------------------
    # The thread function.
    # ------------------------------------------------------------
    def run(self):
        last_time_select_torrent = 0
        while not self._should_stop:
            # torrent selection
            this_time = int(time.time())
            if this_time - last_time_select_torrent > self._torrent_select_interval:
                self._lock.acquire()
                try:
                    self._selectTorrentsToCheck()
                except Exception as e:
                    print >> sys.stderr, \
                    '[WARN] Unexpected error during TorrentSelection: ', e
                    print_exc()
                    print_stack()
                self._lock.release()
                last_time_select_torrent = this_time

            # create read and write socket check list
            # check non-blocking connection TCP sockets if they are writable
            # check UDP and TCP response sockets if they are readable
            check_read_socket_list = []
            check_write_socket_list = []

            # all finished or failed sessions will be handled later
            completed_session_list = []

            self._lock.acquire()
            for sock, session in self._session_dict.items():
                if session.failed or session.finished:
                    completed_session_list.append(session)
                    continue

                if session.trackerType == 'UDP':
                    check_read_socket_list.append(sock)
                else:
                    if session.action == TRACKER_ACTION_CONNECT:
                        check_write_socket_list.append(sock)
                    else:
                        check_read_socket_list.append(sock)
            self._lock.release()

            # select
            try:
                read_socket_list, write_socket_list, error_socket_list = \
                    select.select( \
                    check_read_socket_list, check_write_socket_list, [], \
                    self._select_timeout)
            except Exception as e:
                if DEBUG:
                    print >> sys.stderr, \
                    '[WARN] Error while selecting: ', e

            current_time = int(time.time())
            self._lock.acquire()
            # we don't want any unexpected exception to break the loop
            try:
                # >> Step 1: Check the sockets
                # check writable sockets (TCP connections)
                for write_socket in write_socket_list:
                    session = self._session_dict[write_socket]
                    session.handleRequest()
                    if session.failed or session.finished:
                        completed_session_list.append(session)

                # check readable sockets
                for read_socket in read_socket_list:
                    session = self._session_dict[read_socket]
                    session.handleRequest()
                    if session.failed or session.finished:
                        completed_session_list.append(session)

                # >> Step 2: Handles the completed sessions
                for session in completed_session_list:
                    if session.failed:
                        success = False
                    elif session.finished:
                        success = True
                    else:
                        raise RuntimeError('This should not happen.', session)

                    # set torrent remaining responses
                    for infohash in session.infohashList:
                        self._pending_response_dict[infohash]['remainingResponses'] -= 1

                    # update the Tracker Status Cache
                    self._tracker_info_cache.updateTrackerInfo( \
                        session.tracker, success)

                    # cleanup
                    del self._session_dict[session.socket]
                    del session

                # >> Step 3. check and update new results
                for infohash, response in self._pending_response_dict.items():
                    if response['updated']:
                        self._updateTorrentResult(response)
                        response['updated'] = False

                # >> Step 4. check and clean up the finished requests
                obsolete_list = list()
                for infohash in self._pending_response_dict:
                    if self._pending_response_dict[infohash]['remainingResponses'] == 0:
                        obsolete_list.append(infohash)
                # can not do it in the previous loop because it will change the
                # dictionary and hence cause error in the iteration.
                for infohash in obsolete_list:
                    self._checkResponseFinal(self._pending_response_dict[infohash])
                    del self._pending_response_dict[infohash]
                del obsolete_list


                # >> Last Step. check and handle timed out UDP sessions
                for _, session in self._session_dict.items():
                    if session.trackerType != 'UDP':
                        continue

                    interval = UDP_TRACKER_RECHECK_INTERVAL * (2**session.retries)
                    if current_time - session.lastContact < interval:
                        continue

                    session.retries += 1
                    if session.retries > UDP_TRACKER_MAX_RETRIES:
                        session.failed = True
                        session.socket.close()
                        print >> sys.stderr, \
                        '[DEBUG] Tracker[%s] retried out.' % session.tracker
                    else:
                        # re-establish the message
                        session.reestablishConnection()
                        session.retries += 1
                        print >> sys.stderr, \
                        '[DEBUG] Tracker[%s] retry, %d.' % (session.tracker, session.retries)

            # All kinds of unexpected exceptions
            except Exception as err:
                print >> sys.stderr, \
                '[FATAL] Unexpected exception: ', err
                print_exc()
                print_stack()
                time.sleep(1000)

            self._lock.release()


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
    def __init__(self, tracker, tracker_type, tracker_address, announce_page):
        self._tracker         = tracker
        self._trackerType     = tracker_type
        self._tracker_address = tracker_address
        self._announce_page   = announce_page

        self._socket = None
        self._infohash_list = list()
        self._initiated = False
        self._action = None

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
    def createSession(tracker_url):
        tracker_type, tracker_address, announce_page = \
           TrackerSession.parseTrackerUrl(tracker_url)

        if tracker_type == 'UDP':
            session = UdpTrackerSession(tracker_url, \
                            tracker_address, announce_page)
        else:
            session = HttpTrackerSession(tracker_url, \
                            tracker_address, announce_page)
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
    def __init__(self, tracker, trackerAddress, announcePage):
        TrackerSession.__init__(self, tracker, \
            'HTTP', trackerAddress, announcePage)

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
            TorrentChecking.getInstance().updateResultFromSession(\
                infohash, seeders, leechers)

            # remove this infohash in the infohash list of this session
            if infohash in unprocessed_infohash_list:
                unprocessed_infohash_list.remove(infohash)

        # handle the infohashes with no result
        # (considers as the torrents with seeders/leechers=0/0)
        for infohash in unprocessed_infohash_list:
            seeders, leechers = 0, 0
            # handle the retrieved information
            TorrentChecking.getInstance().updateResultFromSession(\
                infohash, seeders, leechers)
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
    def __init__(self, tracker, trackerAddress, announcePage):
        TrackerSession.__init__(self, tracker, \
            'UDP', trackerAddress, announcePage)

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
            TorrentChecking.getInstance().updateResultFromSession(\
                infohash, seeders, leechers)

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
