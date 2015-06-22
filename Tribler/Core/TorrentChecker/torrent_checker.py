from binascii import hexlify
from collections import deque
import logging
import select
import time

from twisted.internet import reactor

from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import blocking_call_on_reactor_thread, call_on_reactor_thread

from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.Core.TorrentChecker.session import TRACKER_ACTION_CONNECT, create_tracker_session

from .session import FakeDHTSession

# some settings
DEFAULT_TORRENT_SELECTION_INTERVAL = 20  # every 20 seconds, the thread will select torrents to check
DEFAULT_TORRENT_CHECK_INTERVAL = 900  # base multipier for the check delay

DEFAULT_MAX_TORRENT_CHECK_RETRIES = 8  # max check delay increments when failed.
DEFAULT_TORRENT_CHECK_RETRY_INTERVAL = 30  # interval when the torrent was successfully checked for the last time

DEFAULT_SOCKET_SELECTION_INTERVAL = 0.3  # interval between two socket selections


class TorrentChecker(TaskManager):

    def __init__(self, session):
        super(TorrentChecker, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._session = session

        self._torrent_db = None

        self._should_stop = False

        self._pending_request_queue = deque()
        self._pending_response_dict = {}

        self._torrent_check_interval = DEFAULT_TORRENT_CHECK_INTERVAL
        self._torrent_check_retry_interval = DEFAULT_TORRENT_CHECK_RETRY_INTERVAL
        self._max_torrent_check_retries = DEFAULT_MAX_TORRENT_CHECK_RETRIES
        self._socket_selection_interval = DEFAULT_SOCKET_SELECTION_INTERVAL

        self._session_list = [FakeDHTSession(session, self._on_result_from_session),]
        self._last_torrent_selection_time = 0

        self._check_read_socket_list = []
        self._check_write_socket_list = []

    @property
    def should_stop(self):
        return self._should_stop

    @blocking_call_on_reactor_thread
    def initialize(self):
        self._torrent_db = self._session.open_dbhandler(NTFY_TORRENTS)

        self._reschedule_torrent_select()

        self.register_task(u"task_check_sockets", reactor.callLater(self._socket_selection_interval,
                                                                    self._task_select_sockets))

    @blocking_call_on_reactor_thread
    def shutdown(self):
        """
        Shutdown the torrent health checker.

        Once shut down it can't be started again.
        """
        # stop the checking task
        self._should_stop = True
        self.cancel_all_pending_tasks()

        # kill all the tracker sessions
        for session in self._session_list:
            session.cleanup()
        self._session_list = None

        self._pending_request_queue = None
        self._pending_response_dict = None

        self._torrent_db = None
        self._session = None
        self._check_read_socket_list = None
        self._check_write_socket_list = None

    def _task_select_sockets(self):
        """
        The LoopingCall task that checks the sockets using select().
        """
        read_socket_list, write_socket_list, _ = select.select(self._check_read_socket_list,
                                                               self._check_write_socket_list,
                                                               [], 0.0)

        result = self._check_sessions(read_socket_list, write_socket_list, [])
        if result is None:
            return
        self._check_read_socket_list, self._check_write_socket_list = result

        self.register_task(u"task_check_sockets", reactor.callLater(self._socket_selection_interval,
                                                                    self._task_select_sockets))

    def _reschedule_torrent_select(self):
        """
        Changes the torrent selection interval dynamically and schedules the task.
        """
        # dynamically change the interval: update at least every 2h
        num_torrents = self._torrent_db.getNumberCollectedTorrents()

        torrent_select_interval = min(max(7200 / num_torrents, 10), 100) if num_torrents \
            else DEFAULT_TORRENT_SELECTION_INTERVAL

        self._logger.debug(u"torrent selection interval changed to %s", torrent_select_interval)

        self.register_task(u"torrent_checker torrent selection",
                           reactor.callLater(torrent_select_interval, self._task_select_torrents))

    def _task_select_torrents(self):
        """
        The regularly scheduled task that selects torrent to check.
        """
        # update the torrent selection interval
        self._reschedule_torrent_select()

        # start selecting torrents
        current_time = int(time.time())

        result = self._session.lm.tracker_manager.get_next_tracker_for_auto_check()
        if result is None:
            self._logger.warn(u"No tracker to select from, skip")
            return

        tracker_url, _ = result
        self._logger.debug(u"Start selecting torrents on tracker %s.", tracker_url)

        all_torrent_list = self._torrent_db.getTorrentsOnTracker(tracker_url, current_time)

        # get the torrents that should be checked
        scheduled_torrents = 0
        for torrent_id, infohash, last_check in all_torrent_list:
            # recheck interval is: interval * 2^(retries)
            if current_time - last_check < self._torrent_check_interval:
                continue

            self._pending_request_queue.append((torrent_id, infohash, [tracker_url, ]))
            scheduled_torrents += 1

        self._logger.debug(u"Selected %d new torrents to check on tracker: %s", scheduled_torrents, tracker_url)

    @call_on_reactor_thread
    def add_gui_request(self, infohash):
        """
        Public API for adding a GUI request.
        :param infohash: Torrent infohash.
        """
        result = self._torrent_db.getTorrent(infohash, (u'torrent_id', u'last_tracker_check'), False)
        if result is None:
            self._logger.warn(u"torrent info not found, skip. infohash: %s", hexlify(infohash))
            return

        torrent_id = result[u'torrent_id']
        last_check = result[u'last_tracker_check']
        time_diff = time.time() - last_check
        if time_diff < self._torrent_check_interval:
            self._logger.debug(u"time interval too short, skip GUI request. infohash: %s", hexlify(infohash))
            return

        if torrent_id <= 0:
            self._logger.warn(u"no torrent_id, skip GUI request. infohash: %s", hexlify(infohash))
            return

        # get torrent's tracker list from DB
        tracker_set = set()
        db_tracker_list = self._torrent_db.getTrackerListByTorrentID(torrent_id)
        for tracker in db_tracker_list:
            tracker_set.add(tracker)

        if not tracker_set:
            self._logger.warn(u"no trackers, skip GUI request. infohash: %s", hexlify(infohash))
            # TODO: add code to handle torrents with no tracker
            return

        self._pending_request_queue.append((torrent_id, infohash, tracker_set))

    @blocking_call_on_reactor_thread
    def _check_sessions(self, read_socket_list, write_socket_list, _):
        current_time = int(time.time())

        session_dict = {}
        for session in self._session_list:
            session_dict[session.socket] = session

        # >> Step 1: Check the sockets
        self._logger.debug(u"got %d writable sockets, %d readable sockets",
                           len(write_socket_list), len(read_socket_list))
        # check writable sockets (TCP connections)
        for write_socket in write_socket_list:
            session = session_dict[write_socket]
            session.process_request()

        # check readable sockets
        for read_socket in read_socket_list:
            session = session_dict[read_socket]
            session.process_request()

        # >> Step 2: Handle timed out UDP sessions
        for session in session_dict.values():
            diff = current_time - session.last_contact
            if diff > session.retry_interval:
                session._is_timed_out = True

                for infohash in session.infohash_list:
                    self._pending_response_dict[infohash][u'updated'] = True

                session.increase_retries()

                if session.retries > session.max_retries:
                    session._is_failed = True
                    self._logger.debug(u"%s max retry count hit", session)
                else:
                    # re-establish the connection
                    # Do it in a callLater so the timed out flag is not cleared until we are done with it.
                    self._logger.debug(u"%s retrying: %d/%d", session, session.retries, self._max_torrent_check_retries)
                    reactor.callLater(0, session.recreate_connection)

        # >> Step 3: Remove completed sessions and update tracker info
        if self._session_list:
            for i in range(len(self._session_list) - 1, -1, -1):
                session = self._session_list[i]

                if session.is_failed or session.is_finished:
                    self._logger.debug(u"%s is %s", session, u'failed' if session.is_failed else u'finished')

                    # update tracker info
                    self._session.lm.tracker_manager.update_tracker_info(session.tracker_url, not session.is_failed)

                    # set torrent remaining responses
                    for infohash in session.infohash_list:
                        self._pending_response_dict[infohash][u'remaining_responses'] -= 1

                    session.cleanup()
                    self._session_list.pop(i)

        # >> Step 4. check and update new results
        for infohash, response in self._pending_response_dict.items():
            if response[u'updated']:
                response[u'updated'] = False
                self._update_torrent_result(response)

            if self._pending_response_dict[infohash][u'remaining_responses'] == 0:
                del self._pending_response_dict[infohash]

        self._logger.debug(u"total sessions: %d", len(self._session_list))
        for session in self._session_list:
            self._logger.debug(u"%s, finished: %d, failed: %d", session, session.is_finished, session.is_failed)

        # ---------------------------------------------------
        # Start processing pending requests and make select socket lists

        # process all pending request
        self._process_pending_requests()

        # create read and write socket check list
        # check non-blocking connection TCP sockets if they are writable
        # check UDP and TCP response sockets if they are readable
        check_read_socket_list = []
        check_write_socket_list = []

        session_dict = {}
        for session in self._session_list:
            session_dict[session.socket] = session

        for session_socket, session in session_dict.iteritems():
            if session.tracker_type == u'DHT':
                # FakeDHTSession doesn't really have a socket as it uses LibtorrentMgr's DHT
                continue
            if session.tracker_type == u'UDP':
                check_read_socket_list.append(session_socket)
            else:
                if session.action == TRACKER_ACTION_CONNECT:
                    check_write_socket_list.append(session_socket)
                else:
                    check_read_socket_list.append(session_socket)

        # return select socket lists
        return check_read_socket_list, check_write_socket_list

    def _process_pending_requests(self):
        """
        Processes all pending requests.
        """
        while len(self._pending_request_queue) > 0:
            _, infohash, tracker_set = self._pending_request_queue.popleft()
            for tracker_url in tracker_set:
                self._create_session_for_request(infohash, tracker_url)

    def _create_session_for_request(self, infohash, tracker_url):
        # skip no-DHT
        if tracker_url == u'no-DHT':
            return

        # >> Step 1: Try to append the request to an existing session
        # check there is any existing session that scrapes this torrent
        request_handled = False
        for session in self._session_list:
            if session.tracker_url != tracker_url or session.is_failed:
                continue

            if session.has_request(infohash):
                # a torrent check is already there, ignore this request
                request_handled = True
                break

            if session.can_add_request():
                session.add_request(infohash)
                self._update_pending_response(infohash)
                request_handled = True
                break

        if request_handled:
            self._logger.debug(u'infohash [%s] appended', hexlify(infohash))
            return

        # >> Step 2: No session to append to, create a new one
        # create a new session for this request
        session = None
        try:
            session = create_tracker_session(tracker_url, self._on_result_from_session)

            connection_established = session.create_connection()
            if not connection_established:
                raise RuntimeError(u"Could not establish connection")

            session.add_request(infohash)

            self._session_list.append(session)

            # update the number of responses this torrent is expecting
            self._update_pending_response(infohash)

            self._logger.debug(u"Session created for infohash %s", hexlify(infohash))

        except Exception as e:
            self._logger.error(u"Failed to create session for tracker %s: %s", tracker_url, e)

            if session:
                session.cleanup()

            self._session.lm.tracker_manager.update_tracker_info(tracker_url, False)

    def _update_pending_response(self, infohash):
        if infohash in self._pending_response_dict:
            self._pending_response_dict[infohash][u'remaining_responses'] += 1
            self._pending_response_dict[infohash][u'updated'] = False
        else:
            self._pending_response_dict[infohash] = {u'infohash': infohash,
                                                     u'remaining_responses': 1,
                                                     u'seeders': -2,
                                                     u'leechers': -2,
                                                     u'updated': False}

    def _on_result_from_session(self, infohash, seeders, leechers):
        if self.should_stop:
            return
        response = self._pending_response_dict[infohash]
        response[u'last_check'] = int(time.time())
        if response[u'seeders'] < seeders or (response[u'seeders'] == seeders and response[u'leechers'] < leechers):
            response[u'seeders'] = seeders
            response[u'leechers'] = leechers
            response[u'updated'] = True

    def _update_torrent_result(self, response):
        infohash = response[u'infohash']
        seeders = response[u'seeders']
        leechers = response[u'leechers']
        last_check = response[u'last_check']

        # the torrent status logic, TODO: do it in other way
        self._logger.debug(u"Update result %s/%s for %s", seeders, leechers, hexlify(infohash))

        result = self._torrent_db.getTorrent(infohash, (u'torrent_id', u'tracker_check_retries'), include_mypref=False)
        torrent_id = result[u'torrent_id']
        retries = result[u'tracker_check_retries']

        # the status logic
        if seeders > 0:
            retries = 0
            status = u'good'
        else:
            retries += 1
            if retries < self._max_torrent_check_retries:
                status = u'unknown'
            else:
                status = u'dead'
                # prevent retries from exceeding the maximum
                retries = self._max_torrent_check_retries

        # calculate next check time: <last-time> + <interval> * (2 ^ <retries>)
        next_check = last_check + self._torrent_check_retry_interval * (2 ** retries)

        self._torrent_db.updateTorrentCheckResult(torrent_id,
                                                  infohash, seeders, leechers, last_check, next_check,
                                                  status, retries)
