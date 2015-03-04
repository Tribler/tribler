import binascii
import time
import logging

import select
import socket

import threading
from threading import Thread
import Queue

from traceback import print_exc

from Tribler.Core import NoDispersyRLock
from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.Core.TorrentDef import TorrentDef

try:
    prctlimported = True
    import prctl
except ImportError as e:
    prctlimported = False

from Tribler.TrackerChecking.TrackerUtility import getUniformedURL
from Tribler.TrackerChecking.TrackerInfoCache import TrackerInfoCache
from Tribler.TrackerChecking.TrackerSession import TrackerSession
from Tribler.TrackerChecking.TrackerSession import TRACKER_ACTION_CONNECT
from Tribler.TrackerChecking.TrackerSession import MAX_TRACKER_MULTI_SCRAPE

from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread, bin2str


# some settings
DEFAULT_MAX_GUI_REQUESTS = 5000

DEFAULT_TORRENT_SELECTION_INTERVAL = 20  # every 20 seconds, the thread will select torrents to check
DEFAULT_TORRENT_CHECK_INTERVAL = 900  # a torrent will only be checked every 15 mins

DEFAULT_MAX_TORRENT_CHECK_RETRIES = 8
DEFAULT_TORRENT_CHECK_RETRY_INTERVAL = 30


class TorrentChecking(Thread):

    __single = None

    def __init__(self, session, torrent_select_interval=DEFAULT_TORRENT_SELECTION_INTERVAL,
                 torrent_check_interval=DEFAULT_TORRENT_CHECK_INTERVAL,
                 max_torrrent_check_retries=DEFAULT_MAX_TORRENT_CHECK_RETRIES,
                 torrrent_check_retry_interval=DEFAULT_TORRENT_CHECK_RETRY_INTERVAL):
        if TorrentChecking.__single:
            raise RuntimeError("Torrent Checking is singleton")
        TorrentChecking.__single = self

        super(TorrentChecking, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        name = 'TorrentChecking' + self.getName()
        self.setName(name)

        self._logger.debug('Starting TorrentChecking from %s.', threading.currentThread().getName())
        self.setDaemon(True)

        self.session = session

        self._torrentdb = session.open_dbhandler(NTFY_TORRENTS)
        self._interrupt_socket = InterruptSocket()

        self._lock = NoDispersyRLock()
        self._session_list = []
        self._pending_response_dict = dict()

        # initialize a tracker status cache, TODO: add parameters
        self._tracker_info_cache = TrackerInfoCache(session)

        self._tracker_selection_idx = 0
        self._torrent_select_interval = torrent_select_interval
        self._torrent_check_interval = torrent_check_interval

        self._max_torrrent_check_retries = max_torrrent_check_retries
        self._torrrent_check_retry_interval = torrrent_check_retry_interval

        # self._max_gui_requests = DEFAULT_MAX_GUI_REQUESTS
        self._gui_request_queue = Queue.Queue()
        self._processed_gui_request_queue = Queue.Queue()

        self._should_stop = False

    @staticmethod
    def getInstance(*args, **kw):
        if TorrentChecking.__single is None:
            TorrentChecking(*args, **kw)
        return TorrentChecking.__single

    @staticmethod
    def delInstance():
        TorrentChecking.__single.shutdown()
        TorrentChecking.__single = None

    def setTorrentSelectionInterval(self, interval):
        self._torrent_select_interval = interval

    def shutdown(self):
        if not self._should_stop:
            self._should_stop = True
            self._interrupt_socket.interrupt()
            # TODO(emilon): we should have a lower fixed timeout on the select() so we can interrupt earlier if we need so.
            # self.join()

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
            self._logger.debug('TorrentChecking: GUI request queue is full.')
            successful = False

        except Exception as e:
            self._logger.debug('TorrentChecking: Unexpected error while adding GUI request: %s', e)
            successful = False

        return successful

    @forceDBThread
    def _processGuiRequests(self, gui_requests):
        for gui_request in gui_requests:
            infohash = gui_request['infohash']
            tracker_set = gui_request['trackers']

            if 'last_check' in gui_requests:
                last_check = gui_requests['last_check']
            else:
                last_check = self._torrentdb.getTorrent(infohash, ("torrent_id", "last_tracker_check"), False)
                last_check = last_check["last_tracker_check"]
            time_diff = time.time() - last_check
            if time_diff < self._torrent_check_interval:
                self._logger.debug("Ignoring a GUI request, time interval too short")
                continue

            if 'torrent_id' in gui_request:
                torrent_id = gui_request['torrent_id']
            else:
                torrent_id = self._torrentdb.getTorrentID(infohash)

            if torrent_id <= 0:
                self._logger.debug("TorrentChecking: ignoring gui request, no torrent_id")
                continue

            if not tracker_set:
                # get torrent's tracker list from DB
                db_tracker_list = self._getTrackerList(torrent_id, infohash)
                for tracker in db_tracker_list:
                    tracker_set.add(tracker)

            if not tracker_set:
                self._logger.debug("TorrentChecking: ignoring gui request, no trackers")
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

    def _getTrackerList(self, torrent_id, infohash):
        tracker_set = set()

        # get trackers from DB (TorrentTrackerMapping table)
        db_tracker_list = self._torrentdb.getTrackerListByTorrentID(torrent_id)
        for tracker in db_tracker_list:
            tracker_set.add(tracker)

        # get trackers from its .torrent file
        torrent_data = self.session.get_collected_torrent(infohash)
        if torrent_data:
            try:
                torrent = TorrentDef.load_from_memory(torrent_data)
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

    @forceDBThread
    def _updateTorrentTrackerMapping(self, torrent_id, tracker):
        self._torrentdb.addTorrentTrackerMapping(torrent_id, tracker)

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
            self._logger.debug('TorrentChecking: Session [%s] appended.', binascii.b2a_hex(infohash))
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

            self._logger.debug('TorrentChecking: Session [%s] created.', binascii.b2a_hex(infohash))

        except Exception as e:
            self._logger.debug('TorrentChecking: Failed to create session for tracker[%s]: %s', tracker_url, e)

            if session:
                session.cleanup()

            self._tracker_info_cache.updateTrackerInfo(tracker_url, False)

    def _updatePendingResponseDict(self, infohash):

        if infohash in self._pending_response_dict:
            self._pending_response_dict[infohash]['remainingResponses'] += 1
            self._pending_response_dict[infohash]['updated'] = False
        else:
            self._pending_response_dict[infohash] = {'infohash': infohash,
                                                     'remainingResponses': 1,
                                                     'seeders': -2,
                                                     'leechers': -2,
                                                     'updated': False}

    def updateResultFromSession(self, infohash, seeders, leechers):
        response = self._pending_response_dict[infohash]
        response['last_check'] = int(time.time())
        if response['seeders'] < seeders or \
                (response['seeders'] == seeders and response['leechers'] < leechers):
            response['seeders'] = seeders
            response['leechers'] = leechers
            response['updated'] = True

    @forceDBThread
    def _updateTorrentResult(self, response):
        infohash = response['infohash']
        seeders = response['seeders']
        leechers = response['leechers']
        last_check = response['last_check']

        # the torrent status logic, TODO: do it in other way
        self._logger.debug("TorrentChecking: Update result %s/%s for %s", seeders, leechers, bin2str(infohash))

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
            retries += 1
            if retries < self._max_torrrent_check_retries:
                status = u'unknown'
            else:
                status = u'dead'
                # prevent retries from exceeding the maximum
                retries = self._max_torrrent_check_retries

        # calculate next check time: <last-time> + <interval> * (2 ^ <retries>)
        next_check = last_check + self._torrrent_check_retry_interval * (2 ** retries)

        self._torrentdb.updateTorrentCheckResult(torrent_id,
                                                 infohash, seeders, leechers, last_check, next_check,
                                                 status, retries)

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

    @forceDBThread
    def _selectTorrentsToCheck(self):
        current_time = int(time.time())
        for _ in range(self._tracker_info_cache.getTrackerInfoListSize()):
            # update the new tracker index
            self._tracker_selection_idx = (
                self._tracker_selection_idx + 1) % self._tracker_info_cache.getTrackerInfoListSize()

            tracker, _ = self._tracker_info_cache.getTrackerInfo(self._tracker_selection_idx)
            self._logger.debug('TorrentChecking: Should we check tracker[%s].', tracker)

            if tracker == 'no-DHT' or tracker == 'DHT' or not self._tracker_info_cache.toCheckTracker(tracker):
                continue

            self._logger.debug('TorrentChecking: Selecting torrents to check on tracker[%s].', tracker)

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
                self._logger.debug('TorrentChecking: Selected %d torrents to check on tracker[%s].',
                                   scheduled_torrents, tracker)
                break

            else:
                self._logger.debug('TorrentChecking: Selected 0 torrents to check on tracker[%s].', tracker)

    # ------------------------------------------------------------
    # The thread function.
    # ------------------------------------------------------------
    def run(self):
        # TODO: someone please check this? I am not really sure what this is.
        if prctlimported:
            prctl.set_name("Tribler" + threading.currentThread().getName())

        # wait for the tracker info cache to be initialized
        self._logger.debug('TorrentChecking: Start initializing TrackerInfoCache...')

        self._tracker_info_cache.loadCacheFromDb()

        self._logger.debug('TorrentChecking: TrackerInfoCache initialized.')
        self._logger.info('TorrentChecking: initialized.')

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
                    self._logger.error('TorrentChecking: Unexpected error while handling requests %s', e)
                    print_exc()

                if requests:
                    callback(requests)

            process_queue(self._gui_request_queue, self._processGuiRequests)
            process_queue(self._processed_gui_request_queue, self._onProcessedGuiRequests)

            # torrent selection
            current_time = int(time.time())
            time_remaining = max(0, self._torrent_select_interval - (current_time - last_time_select_torrent))
            if time_remaining == 0:
                self._logger.debug('TorrentChecking: Selecting new torrent')

                try:
                    self._selectTorrentsToCheck()

                except Exception as e:
                    self._logger.error('TorrentChecking: Unexpected error during TorrentSelection: %s', e)
                    print_exc()

                last_time_select_torrent = current_time
                time_remaining = self._torrent_select_interval
            else:
                self._logger.debug('TorrentChecking: Will wait for an interrupt for %.1f', time_remaining)

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
                read_socket_list, write_socket_list, error_socket_list = select.select(check_read_socket_list,
                                                                                       check_write_socket_list,
                                                                                       [],
                                                                                       time_remaining)

            except Exception as e:
                self._logger.debug('TorrentChecking: Error while selecting: %s', e)

            if not self._should_stop:
                current_time = int(time.time())
                # we don't want any unexpected exception to break the loop
                try:
                    # >> Step 1: Check the sockets
                    # check writable sockets (TCP connections)
                    self._logger.debug('TorrentChecking: got %d writable sockets', len(write_socket_list))
                    for write_socket in write_socket_list:
                        session = session_dict[write_socket]
                        session.handleRequest()

                    # check readable sockets
                    self._logger.debug('TorrentChecking: got %d readable sockets', len(read_socket_list))
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
                                self._logger.debug('TorrentChecking: UDP Tracker[%s] retried out.',
                                                   session.getTracker())
                            else:
                                # re-establish the connection
                                session.reestablishConnection()
                                self._logger.debug('TorrentChecking: UDP Tracker[%s] retry, %d.',
                                                   session.getTracker(), session.getRetries())

                    # >> Step 3: Remove completed sessions
                    with self._lock:
                        for i in range(len(self._session_list) - 1, -1, -1):
                            session = self._session_list[i]

                            if session.hasFailed() or session.hasFinished():
                                self._logger.debug('TorrentChecking: session[%s] is %s',
                                                   session.getTracker(),
                                                   'failed' if session.hasFailed() else 'finished')

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
                    self._logger.error('TorrentChecking: Unexpected exception: %s', err)
                    print_exc()

                self._logger.debug('TorrentChecking: sessions: %d', len(self._session_list))
                for session in self._session_list:
                    self._logger.debug('TorrentChecking: session[%s], finished=%d, failed=%d',
                                       session.getTracker(), session.hasFinished(), session.hasFailed())

        # the thread is shutting down, kill all the tracker sessions
        for session in self._session_list:
            session.cleanup()

        self._interrupt_socket.close()
        self._logger.info('TorrentChecking: shutdown')


class InterruptSocket(object):

    """
    When we need the poll to return before the timeout expires, we
    will send some data to the InterruptSocket and discard the data.
    """

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.ip = "127.0.0.1"
        self.port = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.ip, 0))
        self.port = self.socket.getsockname()[1]
        self._logger.debug("Bound InterruptSocket on port %s", self.port)

        self.interrupt_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def interrupt(self):
        if self.interrupt_socket:
            self.interrupt_socket.sendto("+", (self.ip, self.port))

    def handleRequest(self):
        try:
            self.socket.recv(1024)
        except:
            pass

    def close(self):
        self.interrupt_socket.close()
        self.interrupt_socket = None
        self.socket.close()
        self.socket = None

    def get_ip(self):
        return self.ip

    def get_port(self):
        return self.port

    def get_socket(self):
        return self.socket
