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
from threading import Thread, Lock, Event
import Queue

from traceback import print_exc, print_stack

from Tribler.Core.Session import Session
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Swift.SwiftDef import SwiftDef

try:
    prctlimported = True
    import prctl
except ImportError as e:
    prctlimported = False

from Tribler.TrackerChecking.TrackerInfoCache import TrackerInfoCache
from Tribler.TrackerChecking.TrackerSession import TrackerSession
from Tribler.TrackerChecking.TrackerSession import\
    TRACKER_ACTION_CONNECT, TRACKER_ACTION_ANNOUNCE, TRACKER_ACTION_SCRAPE
from Tribler.TrackerChecking.TrackerSession import\
    UDP_TRACKER_RECHECK_INTERVAL, UDP_TRACKER_MAX_RETRIES
from Tribler.TrackerChecking.TrackerSession import\
    MAX_TRACKER_MULTI_SCRAPE

from Tribler.Core.Utilities.utilities import parse_magnetlink
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.Core.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker


# some settings
DEBUG = True

DEFAULT_MAX_GUI_REQUESTS = 1000
DEFAULT_MAX_SELECTED_REQUESTS = 2000

# ============================================================
# This is the single-threaded tracker checking class.
# ============================================================
class TorrentChecking(Thread):

    __single = None

    # ------------------------------------------------------------
    # Intialization.
    # ------------------------------------------------------------
    def __init__(self, args=None):
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
        self._select_timeout = 2

        self._lock = Lock()
        self._session_dict = dict()
        self._pending_response_dict = dict()

        # initialize a tracker status cache, TODO: add parameters
        self._tracker_info_cache = TrackerInfoCache()

        self._tracker_selection_idx = 0
        self._torrent_select_interval = 10
        self._torrent_check_interval = 60
        self._torrent_check_max_retries = 5

        # request queues
        self._new_request_event = Event()

        self._max_gui_requests = DEFAULT_MAX_GUI_REQUESTS
        self._max_selected_requests = DEFAULT_MAX_SELECTED_REQUESTS

        self._gui_request_queue = Queue.Queue(self._max_gui_requests)
        self._selected_request_queue = Queue.Queue(self._max_selected_requests)

        self._should_stop = False

        self._tor_col_dir = Session.get_instance().get_torrent_collecting_dir()

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

    # ------------------------------------------------------------
    # (Public API)
    # The public interface to shutdown the thread.
    # ------------------------------------------------------------
    def shutdown(self):
        self._should_stop = True
        self._new_request_event.set()

    # ------------------------------------------------------------
    # (Public API)
    # The public API interface to add a torrent check request. Returns true
    # if successful, false otherwise.
    # Note that, the input argument "gui_torrent" is of class
    # "Tribler.Main.Utility.GuiDBTuples.Torrent", NOT "Core.TorrentDef"!
    # So you need to get the TorrentDef to access more information
    # ------------------------------------------------------------
    def addGuiRequest(self, gui_torrent):
        if gui_torrent.torrent_id == -1:
            return False

        # enqueue a new GUI request
        successful = True
        try:
            gui_request = dict()
            gui_request['torrent_id'] = gui_torrent.torrent_id
            gui_request['infohash']   = gui_torrent.infohash
            gui_request['trackers']   = set()
            if 'trackers' in gui_torrent:
                for tracker in gui_torrent.trackers:
                    gui_request['trackers'].add(tracker)
            self._gui_request_queue.put_nowait(gui_request)
            self._new_request_event.set()
        except Queue.Full:
            if DEBUG:
                print >> sys.stderr, '[WARN] GUI request queue is full.'
            successful = False
        except Exception as e:
            print >> sys.stderr,\
                '[WARN] Unexpected error while adding GUI request:', e
            successful = False
        return successful

    # ------------------------------------------------------------
    # (For Unit Test ONLY) Adds an infohash request.
    # ------------------------------------------------------------
    def addInfohashRequest(self, infohash):
        try:
            request = dict()
            request['infohash'] = infohash
            request['trackers'] = set()
            self._gui_request_queue.put_nowait(request)
            self._new_request_event.set()
        except Queue.Full:
            if DEBUG:
                print >> sys.stderr, '[WARN] GUI request queue is full.'

    # ------------------------------------------------------------
    # Processes a GUI request.
    # ------------------------------------------------------------
    @forceDBThread
    def _processGuiRequest(self, gui_request):
        infohash    = gui_request['infohash']
        tracker_set = gui_request['trackers']
        if 'torrent_id' in gui_request:
            torrent_id = gui_request['torrent_id']
        else:
            torrent_id = self._torrentdb.getTorrentID(infohash)

        # get torrent's tracker list from DB
        db_tracker_list = self._getTrackerList(torrent_id, infohash)
        for tracker in db_tracker_list:
            tracker_set.add(tracker)
        if not tracker_set:
            # TODO: add method to handle torrents with no tracker
            return

        # for each valid tracker, try to create new session or append
        # the request to an existing session
        successful = False
        for tracker_url in tracker_set:
            self._tracker_info_cache.addNewTrackerInfo(tracker_url)
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

        return list(tracker_set)

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
        # skip DHT
        if tracker_url == 'no-DHT' or tracker_url == 'DHT':
            return
        # check if this tracker is worth checking
        if not self._tracker_info_cache.toCheckTracker(tracker_url):
            return

        # >> Step 1: Try to append the request to an existing session
        # check there is any existing session that scrapes this torrent
        self._lock.acquire()
        request_handled = False
        for _, session in self._session_dict.items():
            if session.getTracker() != tracker_url:
                continue
            if session.hasFailed():
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
        self._lock.release()
        if request_handled:
            if DEBUG:
                print >> sys.stderr,\
                '[DEBUG] Session [%s] appended.' % binascii.b2a_hex(infohash)
            return

        # >> Step 2: No session to append to, create a new one
        # create a new session for this request
        self._lock.acquire()
        session = None
        try:
            session = TrackerSession.createSession(tracker_url,\
                self.updateResultFromSession)

            connectionEstablished = session.establishConnection()
            if not connectionEstablished:
                raise RuntimeError('Cannot establish connection.')

            session.addInfohash(infohash)
            self._session_dict[session.getSocket()] = session
            # update the number of responses this torrent is expecting
            self._updatePendingResponseDict(infohash)

            if DEBUG:
                print >> sys.stderr,\
                '[DEBUG] Session [%s] created.' % binascii.b2a_hex(infohash)
        except Exception as e:
            if DEBUG:
                print >> sys.stderr, \
                '[WARN] Failed to create session for tracker[%s]: %s' % \
                (tracker_url, e)
            if session:
                session.cleanup()
                del session
            self._tracker_info_cache.updateTrackerInfo(tracker_url, False)
        self._lock.release()

    # ------------------------------------------------------------
    # Updates the pending response dictionary.
    # ------------------------------------------------------------
    def _updatePendingResponseDict(self, infohash):
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
        seeders  = response['seeders']
        leechers = response['leechers']
        last_check = response['last_check']

        # the torrent status logic, TODO: do it in other way
        status = 'unknown'
        if seeders > 0:
            status = 'good'
        elif seeders == 0:
            status = 'dead'

        # only use updateTorrent() to update results and status
        kw = {'seeder': seeders, 'leecher': leechers, 'status': status,\
            'last_tracker_check': last_check}
        self._torrentdb.updateTorrent(response['infohash'], **kw)

        if status == 'good':
            self._torrentdb.updateGoodTorrentByInfohash(response['infohash'])
        else:
            self._torrentdb.updateDeadTorrentByInfohash(response['infohash'],\
                self._torrent_check_max_retries)

    # ------------------------------------------------------------
    # Updates the check result into the database
    # This is for the torrents whose checks have failed and the results
    # will be -2/-2 at last.
    # ------------------------------------------------------------
    @forceDBThread
    def _checkResponseFinal(self, response):
        seeders  = response['seeders']
        leechers = response['leechers']

        if seeders >= 0 and leechers >= 0:
            return

        last_check = int(time.time())
        # the torrent status logic, TODO: do it in other way
        status = 'unknown'
        if seeders > 0:
            status = 'good'
        elif seeders == 0:
            status = 'dead'

        seeders = 0
        leechers = 0
        kw = {'seeder': seeders, 'leecher': leechers, 'status': status,\
              'last_tracker_check': last_check}
        try:
            self._torrentdb.updateTorrent(response['infohash'], **kw)
        except:
            pass

    # ------------------------------------------------------------
    # Selects torrents to check.
    # This method selects trackers in Round-Robin fashion.
    # ------------------------------------------------------------
    @forceDBThread
    def _selectTorrentsToCheck(self):
        tracker = None
        check_torrent_list = list()

        current_time = int(time.time())
        checked_count = 0
        while checked_count < self._tracker_info_cache.getTrackerInfoListSize():
            if self._tracker_selection_idx >= self._tracker_info_cache.getTrackerInfoListSize():
                return

            tracker, _ = \
                self._tracker_info_cache.getTrackerInfo(self._tracker_selection_idx)
            if tracker == 'no-DHT' or tracker == 'DHT':
                checked_count += 1
                continue
            # skip the dead trackers
            if not self._tracker_info_cache.toCheckTracker(tracker):
                self._tracker_selection_idx += 1
                if self._tracker_selection_idx >= self._tracker_info_cache.getTrackerInfoListSize():
                    self._tracker_selection_idx = 0
                checked_count += 1
                continue

            if DEBUG:
                print >> sys.stderr,\
                '[DEBUG] Selecting torrents to check on tracker[%s].' % tracker

            # get all the torrents on this tracker
            try:
                all_torrent_list = self._torrentdb.getTorrentsOnTracker(tracker)
            except:
                return
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
                infohash = str2bin(torrent[0])
                retries = torrent[1]
                last_check = torrent[2]

                self._createSessionForRequest(infohash, tracker)
            break

        # update the tracker index
        self._tracker_selection_idx += 1
        if self._tracker_selection_idx >= self._tracker_info_cache.getTrackerInfoListSize():
            self._tracker_selection_idx = 0

    # ------------------------------------------------------------
    # The thread function.
    # ------------------------------------------------------------
    def run(self):
        # TODO: someone please check this? I am not really sure what this is.
        if prctlimported:
            prctl.set_name("Tribler" + currentThread().getName())

        # wait for the tracker info cache to be initialized
        if DEBUG:
            print >> sys.stderr,\
            '[DEBUG] Start initializing TrackerInfoCache...'
        self._tracker_info_cache.loadCacheFromDb()
        if DEBUG:
            print >> sys.stderr,\
            '[DEBUG] TrackerInfoCache initialized.'

        last_time_select_torrent = 0
        while not self._should_stop:
            # handle GUI requests
            try:
                while True:
                    gui_request = self._gui_request_queue.get_nowait()
                    self._processGuiRequest(gui_request)
            except Queue.Empty:
                pass
            except Exception as e:
                print >> sys.stderr,\
                '[WARN] Unexpected error while handling GUI requests:', e

            # torrent selection
            this_time = int(time.time())
            if this_time - last_time_select_torrent > self._torrent_select_interval:
                try:
                    self._selectTorrentsToCheck()
                except Exception as e:
                    print >> sys.stderr, \
                    '[WARN] Unexpected error during TorrentSelection: ', e
                    print_exc()
                    print_stack()
                last_time_select_torrent = this_time

            # sleep if no existing session and no request
            self._lock.acquire()
            if self._session_dict:
                has_session = True
            else:
                has_session = False
            self._lock.release()
            if not has_session:
                # TODO: make this configurable
                self._new_request_event.wait(5)
                self._new_request_event.clear()
                continue

            # create read and write socket check list
            # check non-blocking connection TCP sockets if they are writable
            # check UDP and TCP response sockets if they are readable
            check_read_socket_list = []
            check_write_socket_list = []

            # all finished or failed sessions will be handled later
            completed_session_list = []

            self._lock.acquire()
            for sock, session in self._session_dict.items():
                if session.hasFailed() or session.hasFinished():
                    completed_session_list.append(session)
                    continue

                if session.isTrackerType('UDP'):
                    check_read_socket_list.append(sock)
                else:
                    if session.isAction(TRACKER_ACTION_CONNECT):
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
                    if session.hasFailed() or session.hasFinished():
                        completed_session_list.append(session)

                # check readable sockets
                for read_socket in read_socket_list:
                    session = self._session_dict[read_socket]
                    session.handleRequest()
                    if session.hasFailed() or session.hasFinished():
                        completed_session_list.append(session)

                # >> Step 2: Handles the completed sessions
                for session in completed_session_list:
                    if session.hasFailed():
                        success = False
                    elif session.hasFinished():
                        success = True
                    else:
                        raise RuntimeError('This should not happen.', session)

                    # set torrent remaining responses
                    for infohash in session.getInfohashList():
                        self._pending_response_dict[infohash]['remainingResponses'] -= 1

                    # update the Tracker Status Cache
                    self._tracker_info_cache.updateTrackerInfo( \
                        session.getTracker(), success)

                    # cleanup
                    del self._session_dict[session.getSocket()]
                    session.cleanup()
                    del session

                # >> Step 3. check and update new results
                new_result_list = list()
                for infohash, response in self._pending_response_dict.items():
                    if response['updated']:
                        new_result_list
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
                    if not session.isTrackerType('UDP'):
                        continue

                    interval = UDP_TRACKER_RECHECK_INTERVAL * (2**session.getRetries())
                    if current_time - session.getLastContact() < interval:
                        continue

                    session.increaseRetries()
                    if session.getRetries() > UDP_TRACKER_MAX_RETRIES:
                        session.setFailed()
                        session.cleanup()
                        print >> sys.stderr, \
                        '[DEBUG] Tracker[%s] retried out.' % session.getTracker()
                    else:
                        # re-establish the connection
                        session.reestablishConnection()
                        print >> sys.stderr, \
                        '[DEBUG] Tracker[%s] retry, %d.' % (session.getTracker(), session.getRetries())

                # update tracker info cache
                self._tracker_info_cache.updateTrackerInfoIntoDb()

            # All kinds of unexpected exceptions
            except Exception as err:
                print >> sys.stderr, \
                '[FATAL] Unexpected exception: ', err
                print_exc()
                print_stack()
                time.sleep(1000)

            if DEBUG:
                print >> sys.stderr,\
                '[DEBUG] sessions:  %d' % len(self._session_dict)
                for _, session in self._session_dict.items():
                    print >> sys.stderr, '[DEBUG] session[%s], finished=%d, failed=%d' %\
                    (session.getTracker(), session.hasFinished(), session.hasFailed())

            self._lock.release()

        # the thread is shutting down, kill all the tracker sessions
        for _, session in self._session_dict.items():
            session.cleanup()