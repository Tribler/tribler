# ============================================================
# Written by Lipu Fei,
# optimizing the TrackerChecking module written by Niels Zeilemaker.
#
# see LICENSE.txt for license information
#
# TODO: add comments
# ============================================================
import sys
import os
import binascii
import time

import select
import socket

import threading
from threading import Thread, RLock, Event
import Queue

from traceback import print_exc, print_stack

from Tribler.Core.Session import Session
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core import NoDispersyRLock
from Tribler.Main.Utility.GuiDBHandler import startWorker

try:
    prctlimported = True
    import prctl
except ImportError as e:
    prctlimported = False

from Tribler.TrackerChecking.TrackerUtility import getUniformedURL
from Tribler.TrackerChecking.TrackerInfoCache import TrackerInfoCache
from Tribler.TrackerChecking.TrackerSession import TrackerSession
from Tribler.TrackerChecking.TrackerSession import\
    TRACKER_ACTION_CONNECT, TRACKER_ACTION_ANNOUNCE, TRACKER_ACTION_SCRAPE
from Tribler.TrackerChecking.TrackerSession import\
    UDP_TRACKER_RECHECK_INTERVAL, UDP_TRACKER_MAX_RETRIES
from Tribler.TrackerChecking.TrackerSession import\
    MAX_TRACKER_MULTI_SCRAPE

from Tribler.Core.Utilities.utilities import parse_magnetlink
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread, bin2str
from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.Core.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker


# some settings
DEBUG = False

DEFAULT_MAX_GUI_REQUESTS = 5000

DEFAULT_TORRENT_SELECTION_INTERVAL = 20  # every 20 seconds, the thread will select torrents to check
DEFAULT_TORRENT_CHECK_INTERVAL = 60  # a torrent will only be checked every 60 seconds

DEFAULT_MAX_TORRENT_CHECK_RETRIES = 8
DEFAULT_TORRENT_CHECK_RETRY_INTERVAL = 30

# ============================================================
# This is the single-threaded tracker checking class.
# ============================================================
class TorrentChecking(Thread):

    __single = None

    # ------------------------------------------------------------
    # Intialization.
    # ------------------------------------------------------------
    def __init__(self, \
            torrent_select_interval=DEFAULT_TORRENT_SELECTION_INTERVAL,
            torrent_check_interval=DEFAULT_TORRENT_CHECK_INTERVAL,
            max_torrrent_check_retries=DEFAULT_MAX_TORRENT_CHECK_RETRIES,
            torrrent_check_retry_interval=DEFAULT_TORRENT_CHECK_RETRY_INTERVAL):
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
        self._interrupt_socket = InterruptSocket()

        self._lock = NoDispersyRLock()
        self._session_list = []
        self._pending_response_dict = dict()

        # initialize a tracker status cache, TODO: add parameters
        self._tracker_info_cache = TrackerInfoCache()

        self._tracker_selection_idx = 0
        self._torrent_select_interval = torrent_select_interval
        self._torrent_check_interval = torrent_check_interval

        self._max_torrrent_check_retries = max_torrrent_check_retries
        self._torrrent_check_retry_interval = torrrent_check_retry_interval

        # self._max_gui_requests = DEFAULT_MAX_GUI_REQUESTS
        self._gui_request_queue = Queue.Queue()
        self._processed_gui_request_queue = Queue.Queue()

        self._should_stop = False

        self._tor_col_dir = Session.get_instance().get_torrent_collecting_dir()

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
        TorrentChecking.__single.shutdown()
        TorrentChecking.__single = None

    # ------------------------------------------------------------
    # (Public API)
    # Sets the automatic torrent selection interval.
    # ------------------------------------------------------------
    def setTorrentSelectionInterval(self, interval):
        self._torrent_select_interval = interval

    # ------------------------------------------------------------
    # (Public API)
    # The public interface to shutdown the thread.
    # ------------------------------------------------------------
    def shutdown(self):
        if not self._should_stop:
            self._should_stop = True
            self._interrupt_socket.interrupt()

    # ------------------------------------------------------------
    # (Public API)
    # The public API interface to add a torrent check request. Returns true
    # if successful, false otherwise.
    # Note that, the input argument "gui_torrent" is of class
    # "Tribler.Main.Utility.GuiDBTuples.Torrent", NOT "Core.TorrentDef"!
    # So you need to get the TorrentDef to access more information
    # ------------------------------------------------------------
    def addGuiRequest(self, gui_torrent):
        # enqueue a new GUI request
        successful = True
        try:
            gui_request = dict()
            if gui_torrent.torrent_id > 0:
                gui_request['torrent_id'] = gui_torrent.torrent_id
            gui_request['infohash'] = gui_torrent.infohash
            gui_request['trackers'] = set()
            if 'trackers' in gui_torrent:
                for tracker in gui_torrent.trackers:
                    gui_request['trackers'].add(tracker)

            self._gui_request_queue.put_nowait(gui_request)
            self._interrupt_socket.interrupt()

        except Queue.Full:
            if DEBUG:
                print >> sys.stderr, 'TorrentChecking: GUI request queue is full.'
            successful = False

        except Exception as e:
            print >> sys.stderr, 'TorrentChecking: Unexpected error while adding GUI request:', e
            successful = False

        return successful

    # ------------------------------------------------------------
    # Processes a GUI request.
    # ------------------------------------------------------------
    @forceDBThread
    def _processGuiRequests(self, gui_requests):
        for gui_request in gui_requests:
            infohash = gui_request['infohash']
            tracker_set = gui_request['trackers']
            if 'torrent_id' in gui_request:
                torrent_id = gui_request['torrent_id']
            else:
                torrent_id = self._torrentdb.getTorrentID(infohash)

            if torrent_id <= 0:
                if DEBUG:
                    print >> sys.stderr, "TorrentChecking: ignoring gui request, no torrent_id"
                continue

            if not tracker_set:
                # get torrent's tracker list from DB
                db_tracker_list = self._getTrackerList(torrent_id, infohash)
                for tracker in db_tracker_list:
                    tracker_set.add(tracker)

            if not tracker_set:
                if DEBUG:
                    print >> sys.stderr, "TorrentChecking: ignoring gui request, no trackers"
                # TODO: add method to handle torrents with no tracker
                continue

            self._processed_gui_request_queue.put((torrent_id, infohash, tracker_set))
            self._interrupt_socket.interrupt()

    def _onProcessedGuiRequests(self, gui_requests):
        # for each valid tracker, try to create new session or append
        # the request to an existing session
        for torrent_id, infohash, tracker_set in gui_requests:
            for tracker_url in tracker_set:
                self._updateTorrentTrackerMapping(torrent_id, tracker_url)
                self._createSessionForRequest(infohash, tracker_url)

    # ------------------------------------------------------------
    # Gets a list of all known trackers of a given torrent.
    # It checks the TorrentTrackerMapping table and magnet links.
    # ------------------------------------------------------------
    def _getTrackerList(self, torrent_id, infohash):
        tracker_set = set()

        # get trackers from DB (TorrentTrackerMapping table)
        db_tracker_list = self._torrentdb.getTrackerListByTorrentID(torrent_id)
        for tracker in db_tracker_list:
            tracker_set.add(tracker)

        # get trackers from its magnet link
        source_list = self._torrentdb.getTorrentCollecting(torrent_id)
        for source, in source_list:
            if not source.startswith('magnet'):
                continue

            dn, xt, trackers = parse_magnetlink(source)
            if not trackers:
                continue
            for tracker in trackers:
                tracker_set.add(tracker)

        # get trackers from its .torrent file
        result = None
        torrent = self._torrentdb.getTorrent(infohash, ['torrent_file_name', 'swift_torrent_hash'], include_mypref=False)
        if torrent:
            if torrent.get('torrent_file_name', False) and os.path.isfile(torrent['torrent_file_name']):
                result = torrent['torrent_file_name']

            elif torrent.get('swift_torrent_hash', False):
                sdef = SwiftDef(torrent['swift_torrent_hash'])
                torrent_filename = os.path.join(self._tor_col_dir, sdef.get_roothash_as_hex())

                if os.path.isfile(torrent_filename):
                    result = torrent_filename
        if result:
            try:
                torrent = TorrentDef.load(result)
                # check DHT
                if torrent.is_private():
                    dht = 'no-DHT'
                else:
                    dht = 'DHT'
                tracker_set.add(dht)

                torrent_tracker_tuple = torrent.get_trackers_as_single_tuple()
                for tracker in torrent_tracker_tuple:
                    tracker_set.add(tracker)
            except:
                pass

        checked_tracker_set = set()
        for tracker in tracker_set:
            if tracker == 'no-DHT' or tracker == 'DHT':
                continue
            tracker_url = getUniformedURL(tracker)
            if tracker_url:
                checked_tracker_set.add(tracker_url)

        return list(checked_tracker_set)

    # ------------------------------------------------------------
    # Updates the TorrentTrackerMapping table.
    # ------------------------------------------------------------
    @forceDBThread
    def _updateTorrentTrackerMapping(self, torrent_id, tracker):
        self._torrentdb.addTorrentTrackerMapping(torrent_id, tracker)

    # ------------------------------------------------------------
    # Creates a new session for a request, or append the request to an
    # existings tracker session.
    # ------------------------------------------------------------
    def _createSessionForRequest(self, infohash, tracker_url):
        # skip DHT, for now
        if tracker_url == 'no-DHT' or tracker_url == 'DHT':
            return

        # >> Step 1: Try to append the request to an existing session
        # check there is any existing session that scrapes this torrent
        request_handled = False
        with self._lock:
            for session in self._session_list:
                if session.getTracker() != tracker_url or session.hasFailed():
                    continue

                if session.hasInfohash(infohash):
                    # a torrent check is already there, ignore this request
                    request_handled = True
                    break

                if not session.hasInitiated():
                    # only append when the request is less than 74
                    if session.getInfohashListSize() < MAX_TRACKER_MULTI_SCRAPE:
                        session.addInfohash(infohash)
                        self._updatePendingResponseDict(infohash)
                        request_handled = True
                        break

        if request_handled:
            if DEBUG:
                print >> sys.stderr, 'TorrentChecking: Session [%s] appended.' % binascii.b2a_hex(infohash)
            return

        # >> Step 2: No session to append to, create a new one
        # create a new session for this request
        session = None
        try:
            session = TrackerSession.createSession(tracker_url, self.updateResultFromSession)

            connectionEstablished = session.establishConnection()
            if not connectionEstablished:
                raise RuntimeError('Cannot establish connection.')

            session.addInfohash(infohash)

            with self._lock:
                self._session_list.append(session)
                self._interrupt_socket.interrupt()

            # update the number of responses this torrent is expecting
            self._updatePendingResponseDict(infohash)

            if DEBUG:
                print >> sys.stderr, 'TorrentChecking: Session [%s] created.' % binascii.b2a_hex(infohash)

        except Exception as e:
            if DEBUG:
                print >> sys.stderr, 'TorrentChecking: Failed to create session for tracker[%s]: %s' % \
                (tracker_url, e)

            if session:
                session.cleanup()

            self._tracker_info_cache.updateTrackerInfo(tracker_url, False)

    # ------------------------------------------------------------
    # Updates the pending response dictionary.
    # ------------------------------------------------------------
    def _updatePendingResponseDict(self, infohash):

        if infohash in self._pending_response_dict:
            self._pending_response_dict[infohash]['remainingResponses'] += 1
            self._pending_response_dict[infohash]['updated'] = False
        else:
            self._pending_response_dict[infohash] = {'infohash': infohash, 'remainingResponses': 1, 'seeders':-2, 'leechers':-2, 'updated': False}

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

    # ------------------------------------------------------------
    # Updates result into the database.
    # ------------------------------------------------------------
    @forceDBThread
    def _updateTorrentResult(self, response):
        infohash = response['infohash']
        seeders = response['seeders']
        leechers = response['leechers']
        last_check = response['last_check']

        # the torrent status logic, TODO: do it in other way
        if DEBUG:
            print >> sys.stderr, "TorrentChecking: Update result %d/%d for %s"\
                % (seeders, leechers, bin2str(infohash))

        torrent_id = self._torrentdb.getTorrentID(infohash)
        retries = self._torrentdb.getTorrentCheckRetries(torrent_id)

        # the result logic
        is_good_result = False
        if seeders > 0 or leechers > 0:
            is_good_result = True

        # the status logic
        if is_good_result:
            retries = 0
            status = u'good'
        else:
            if retries < self._max_torrrent_check_retries:
                retries += 1
            if retries < self._max_torrrent_check_retries:
                status = u'unknown'
            else:
                status = u'dead'

        # calculate next check time: <last-time> + <interval> * (2 ^ <retries>)
        next_check = last_check + self._torrrent_check_retry_interval * (2 ** retries)

        self._torrentdb.updateTorrentCheckResult(torrent_id,
                infohash, seeders, leechers, last_check, next_check,
                status, retries)

    # ------------------------------------------------------------
    # Updates the check result into the database
    # This is for the torrents whose checks have failed and the results
    # will be -2/-2 at last.
    # ------------------------------------------------------------
    @forceDBThread
    def _checkResponseFinal(self, response):
        seeders = response['seeders']
        leechers = response['leechers']

        # the result logic
        is_good_result = False
        if seeders > 0 or leechers > 0:
            is_good_result = True

        if is_good_result:
            return

        response['seeders'] = 0
        response['leechers'] = 0
        response['last_check'] = int(time.time())

        self._updateTorrentResult(response)

    # ------------------------------------------------------------
    # Selects torrents to check.
    # This method selects trackers in Round-Robin fashion.
    # ------------------------------------------------------------
    @forceDBThread
    def _selectTorrentsToCheck(self):
        current_time = int(time.time())
        for _ in range(self._tracker_info_cache.getTrackerInfoListSize()):
            # update the new tracker index
            self._tracker_selection_idx = (self._tracker_selection_idx + 1) % self._tracker_info_cache.getTrackerInfoListSize()

            tracker, _ = self._tracker_info_cache.getTrackerInfo(self._tracker_selection_idx)
            if DEBUG:
                print >> sys.stderr, 'TorrentChecking: Should we check tracker[%s].' % tracker

            if tracker == 'no-DHT' or tracker == 'DHT' or not self._tracker_info_cache.toCheckTracker(tracker):
                continue

            if DEBUG:
                print >> sys.stderr, 'TorrentChecking: Selecting torrents to check on tracker[%s].' % tracker

            # get all the torrents on this tracker
            try:
                all_torrent_list = self._torrentdb.getTorrentsOnTracker(tracker, current_time)
            except:
                print_exc()
                return

            # get the torrents that should be checked
            scheduled_torrents = 0
            for torrent_id, infohash, last_check in all_torrent_list:
                # check interval
                interval = current_time - last_check

                # recheck interval is: interval * 2^(retries)
                if interval < self._torrent_check_interval:
                    continue

                self._processed_gui_request_queue.put((torrent_id, infohash, [tracker, ]))
                scheduled_torrents += 1

            if scheduled_torrents:
                self._interrupt_socket.interrupt()
                if DEBUG:
                    print >> sys.stderr, 'TorrentChecking: Selected %d torrents to check on tracker[%s].' % (scheduled_torrents, tracker)
                break

            elif DEBUG:
                print >> sys.stderr, 'TorrentChecking: Selected 0 torrents to check on tracker[%s].' % (tracker)

    # ------------------------------------------------------------
    # The thread function.
    # ------------------------------------------------------------
    def run(self):
        # TODO: someone please check this? I am not really sure what this is.
        if prctlimported:
            prctl.set_name("Tribler" + currentThread().getName())

        # wait for the tracker info cache to be initialized
        if DEBUG:
            print >> sys.stderr, 'TorrentChecking: Start initializing TrackerInfoCache...'

        self._tracker_info_cache.loadCacheFromDb()

        if DEBUG:
            print >> sys.stderr, 'TorrentChecking: TrackerInfoCache initialized.'
        print >> sys.stderr, 'TorrentChecking: initialized.'

        last_time_select_torrent = 0
        while not self._should_stop:
            def process_queue(queue, callback):
                requests = []

                try:
                    while True:
                        requests.append(queue.get_nowait())

                except Queue.Empty:
                    pass

                except Exception as e:
                    print >> sys.stderr, 'TorrentChecking: Unexpected error while handling requests'
                    print_exc()

                if requests:
                    callback(requests)

            process_queue(self._gui_request_queue, self._processGuiRequests)
            process_queue(self._processed_gui_request_queue, self._onProcessedGuiRequests)

            # torrent selection
            current_time = int(time.time())
            time_remaining = max(0, self._torrent_select_interval - (current_time - last_time_select_torrent))
            if time_remaining == 0:
                if DEBUG:
                    print >> sys.stderr, 'TorrentChecking: Selecting new torrent'

                try:
                    self._selectTorrentsToCheck()

                except Exception as e:
                    print >> sys.stderr, 'TorrentChecking: Unexpected error during TorrentSelection: ', e
                    print_exc()

                last_time_select_torrent = current_time
                time_remaining = self._torrent_select_interval

            # create read and write socket check list
            # check non-blocking connection TCP sockets if they are writable
            # check UDP and TCP response sockets if they are readable
            check_read_socket_list = [self._interrupt_socket.get_socket()]
            check_write_socket_list = []

            session_dict = {}
            with self._lock:
                for session in self._session_list:
                    session_dict[session.getSocket()] = session

            for session_socket, session in session_dict.iteritems():
                if session.isTrackerType('UDP'):
                    check_read_socket_list.append(session_socket)
                else:
                    if session.isAction(TRACKER_ACTION_CONNECT):
                        check_write_socket_list.append(session_socket)
                    else:
                        check_read_socket_list.append(session_socket)

            # select
            try:
                read_socket_list, write_socket_list, error_socket_list = \
                    select.select(\
                    check_read_socket_list, check_write_socket_list, [], \
                    time_remaining)

            except Exception as e:
                if DEBUG:
                    print >> sys.stderr, 'TorrentChecking: Error while selecting: ', e

            if not self._should_stop:
                current_time = int(time.time())
                # we don't want any unexpected exception to break the loop
                try:
                    # >> Step 1: Check the sockets
                    # check writable sockets (TCP connections)
                    if DEBUG:
                        print >> sys.stderr, 'TorrentChecking: got %d writable sockets' % len(write_socket_list)
                    for write_socket in write_socket_list:
                        session = session_dict[write_socket]
                        session.handleRequest()

                    # check readable sockets
                    if DEBUG:
                        print >> sys.stderr, 'TorrentChecking: got %d readable sockets' % (len(read_socket_list) - 1)
                    for read_socket in read_socket_list:
                        session = session_dict.get(read_socket, self._interrupt_socket)
                        session.handleRequest()

                    # >> Step 2: Handle timedout UDP sessions
                    for session in session_dict.values():
                        diff = current_time - session.getLastContact()
                        if diff > session.getRetryInterval():
                            session.increaseRetries()

                            if session.getRetries() > session.getMaxRetries():
                                session.setFailed()
                                if DEBUG:
                                    print >> sys.stderr, 'TorrentChecking: Tracker[%s] retried out.' % session.getTracker()
                            else:
                                # re-establish the connection
                                session.reestablishConnection()
                                if DEBUG:
                                    print >> sys.stderr, 'TorrentChecking: Tracker[%s] retry, %d.' % (session.getTracker(), session.getRetries())

                    # >> Step 3: Remove completed sessions
                    with self._lock:
                        for i in range(len(self._session_list) - 1, -1, -1):
                            session = self._session_list[i]

                            if session.hasFailed() or session.hasFinished():
                                self._tracker_info_cache.updateTrackerInfo(session.getTracker(), session.hasFailed())

                                # set torrent remaining responses
                                for infohash in session.getInfohashList():
                                    self._pending_response_dict[infohash]['remainingResponses'] -= 1

                                session.cleanup()
                                self._session_list.pop(i)

                    # >> Step 4. check and update new results
                    for infohash, response in self._pending_response_dict.items():
                        if response['updated']:
                            response['updated'] = False
                            self._updateTorrentResult(response)

                        if self._pending_response_dict[infohash]['remainingResponses'] == 0:
                            self._checkResponseFinal(response)
                            del self._pending_response_dict[infohash]

                    # update tracker info cache
                    self._tracker_info_cache.updateTrackerInfoIntoDb()

                # All kinds of unexpected exceptions
                except Exception as err:
                    print >> sys.stderr, 'TorrentChecking: Unexpected exception: ', err
                    print_exc()

                if DEBUG:
                    print >> sys.stderr, 'TorrentChecking: sessions: %d' % len(self._session_list)
                    for session in self._session_list:
                        print >> sys.stderr, 'TorrentChecking: session[%s], finished=%d, failed=%d' % \
                        (session.getTracker(), session.hasFinished(), session.hasFailed())

        # the thread is shutting down, kill all the tracker sessions
        for session in self._session_list:
            session.cleanup()

        self._interrupt_socket.close()
        print >> sys.stderr, 'TorrentChecking: shutdown'

class InterruptSocket:

    """
    When we need the poll to return before the timeout expires, we
    will send some data to the InterruptSocket and discard the data.
    """

    def __init__(self):
        self.ip = "127.0.0.1"
        self.port = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.interrupt_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # we assume that one port in the range below is free
        for self.port in xrange(10000, 12345):
            try:
                if DEBUG:
                    print >> sys.stderr, "InterruptSocket: Trying to start InterruptSocket on port", self.port
                self.socket.bind((self.ip, self.port))
                break
            except:
                pass

    def interrupt(self):
        self.interrupt_socket.sendto("+", (self.ip, self.port))

    def handleRequest(self):
        try:
            self.socket.recv(1024)
        except:
            pass

    def close(self):
        self.interrupt_socket.close()
        self.socket.close()

    def get_ip(self):
        return self.ip

    def get_port(self):
        return self.port

    def get_socket(self):
        return self.socket
