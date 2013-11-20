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

from Tribler.Core.Utilities.utilities import parse_magnetlink
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.Core.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker


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
            print >> sys.stderr, '[DEBUG] Skipping torrent[%s] invalid ID.' %\
                binascii.b2a_hex(gui_torrent.infohash)
            return False

        infohash = gui_torrent.infohash

        # get torrent's tracker list
        self._lock.acquire()
        retries, last_check, tracker_list = \
            self._getTorrentInfo(infohash, gui_torrent)
        self._lock.release()
        if not tracker_list:
            # TODO: add method to handle torrents with no tracker
            print >> sys.stderr, '[DEBUG] Skipping torrent[%s] with no tracker.' %\
                binascii.b2a_hex(infohash)
            return False

        # for each valid tracker, try to (1) append a request or
        # (2) create a new session.
        successful = False
        for tracker_url in tracker_list:
            # check if this tracker is worth checking
            if not self._tracker_info_cache.toCheckTracker(tracker_url):
                continue

            # >> Step 1: Try to append the request to an existing session
            # check there is any existing session that scrapes this torrent
            self._lock.acquire()
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
                session = TrackerSession.createSession(tracker_url,\
                    self.updateResultFromSession)

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
        #if torrent and 'tracker_list' in torrent and torrent['tracker_list']:
        #    return (retries, last_check, torrent['tracker_list'])

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
        #self._updateTorrentTrackerList(infohash, tracker_list)

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
        print >> sys.stderr, '[DEBUG] update called: %s, %d, %d' %\
            (binascii.b2a_hex(infohash), seeders, leechers)
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
        if self._should_stop:
            return

        if not tracker_list:
            return

        trackers_data = ''
        for tracker in tracker_list:
            trackers_data += tracker
            trackers_data += '\n'
        trackers_data = trackers_data[:-1]

        kw = {'trackers': trackers_data }
        try:
            self._torrentdb.updateTorrent(infohash, **kw)
        except:
            pass

    # ------------------------------------------------------------
    # Updates result into the database.
    # ------------------------------------------------------------
    @forceDBThread
    def _updateTorrentResult(self, response):
        if self._should_stop:
            return

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
        try:
            self._torrentdb.updateTorrent(response['infohash'], **kw)
        except:
            pass

    # ------------------------------------------------------------
    # Updates the check result into the database
    # This is for the torrents whose checks have failed and the results
    # will be -2/-2 at last.
    # ------------------------------------------------------------
    @forceDBThread
    def _checkResponseFinal(self, response):
        if self._should_stop:
            return

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

        session = TrackerSession.createSession(tracker,\
            self.updateResultFromSession)
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
                return

            tracker, _ = \
                self._tracker_info_cache.trackerInfoDict.items()[self._tracker_selection_idx]
            # skip the dead trackers
            if not self._tracker_info_cache.toCheckTracker(tracker):
                self._tracker_selection_idx += 1
                if self._tracker_selection_idx >= len(self._tracker_info_cache.trackerInfoDict):
                    self._tracker_selection_idx = 0
                continue

            # get all the torrents on this tracker
            try:
                if self._should_stop:
                    return
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
            session = TrackerSession.createSession(tracker,\
                self.updateResultFromSession)

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
        if prctlimported:
            prctl.set_name("Tribler" + currentThread().getName())

        last_time_select_torrent = 0
        while not self._should_stop:
            # torrent selection
            this_time = int(time.time())
            if this_time - last_time_select_torrent > self._torrent_select_interval:
                self._lock.acquire()
                try:
                    #self._selectTorrentsToCheck()
                    pass
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
                    if self._should_stop:
                        self._lock.release()
                        return
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
                    if self._should_stop:
                        self._lock.release()
                        return
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

            print >> sys.stderr, '[DEBUG] Sessions: %d' % len(self._session_dict.keys())

            self._lock.release()

