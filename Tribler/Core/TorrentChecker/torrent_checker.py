from binascii import hexlify
from collections import deque
import logging
import time
from twisted.internet.error import ConnectingCancelledError

from twisted.internet.defer import Deferred, DeferredList, CancelledError

from twisted.internet import reactor

from Tribler.dispersy.taskmanager import TaskManager, LoopingCall
from Tribler.dispersy.util import blocking_call_on_reactor_thread, call_on_reactor_thread

from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.Core.TorrentChecker.session import create_tracker_session, UdpTrackerSession

from .session import FakeDHTSession

# some settings
DEFAULT_TORRENT_SELECTION_INTERVAL = 20  # every 20 seconds, the thread will select torrents to check
DEFAULT_TORRENT_CHECK_INTERVAL = 900  # base multiplier for the check delay

DEFAULT_MAX_TORRENT_CHECK_RETRIES = 8  # max check delay increments when failed.
DEFAULT_TORRENT_CHECK_RETRY_INTERVAL = 30  # interval when the torrent was successfully checked for the last time

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

        self._session_list = [FakeDHTSession(session, self._on_result_from_session), ]
        self._last_torrent_selection_time = 0

        # Track all session cleanups
        self.session_stop_defer_list = []

    @property
    def should_stop(self):
        return self._should_stop

    @blocking_call_on_reactor_thread
    def initialize(self):
        self._torrent_db = self._session.open_dbhandler(NTFY_TORRENTS)
        self._reschedule_torrent_select()

        # Check the session every 200ms
        self.register_task(u'task_check_torrent_sessions',
                           LoopingCall(self.check_sessions)).start(0.2, now=True)

    def shutdown(self):
        """
        Shutdown the torrent health checker.

        Once shut down it can't be started again.
        :returns A deferred that will fire once the shutdown has completed.
        """
        self._should_stop = True

        # it's now safe to block on the reactor thread
        self.cancel_all_pending_tasks()

        # kill all the tracker sessions.
        # Wait for the defers to all have triggered by using a DeferredList
        for session in self._session_list:
            self.session_stop_defer_list.append(session.cleanup())

        defer_stop_list = DeferredList(self.session_stop_defer_list)

        self._session_list = None

        self._pending_request_queue = None
        self._pending_response_dict = None

        self._torrent_db = None
        self._session = None

        return defer_stop_list

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
        if self._should_stop:
            return

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
    def add_gui_request(self, infohash, scrape_now=False):
        """
        Public API for adding a GUI request.
        :param infohash: Torrent infohash.
        :param scrape_now: Flag whether we want to force scraping immediately
        """
        result = self._torrent_db.getTorrent(infohash, (u'torrent_id', u'last_tracker_check'), False)
        if result is None:
            self._logger.warn(u"torrent info not found, skip. infohash: %s", hexlify(infohash))
            return

        torrent_id = result[u'torrent_id']
        last_check = result[u'last_tracker_check']
        time_diff = time.time() - last_check
        if time_diff < self._torrent_check_interval and not scrape_now:
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

    @call_on_reactor_thread
    def check_sessions(self):
        """
        This function initiates all tracker session if they are ready,
        checks if they have not timed out yet (udp only) and cleans them if they
        have failed or are done.
        :return:
        """
        if self._should_stop:
            return

        # >. Step 1: Perform all calls to the trackers
        check_udp_session_list = self.check_not_initiated_sessions()

        # >> Step 2: Handle timed out UDP sessions
        self.check_timed_out_udp_session(check_udp_session_list)

        # >> Step 3: Remove completed sessions and update tracker info
        self.clean_completed_sessions()

        # >> Step 4. check and update new results
        self.update_with_new_results()

        self._logger.debug(u"total sessions: %d", len(self._session_list))
        for session in self._session_list:
            self._logger.debug(u"%s, finished: %d, failed: %d", session, session.is_finished, session.is_failed)

        # process all pending request
        self._process_pending_requests()

    def check_not_initiated_sessions(self):
        """
        Loops over all sessions and lets them connect to their tracker
        if they haven't done so yet.
        Returns a list of all active udp sessions as they need to be checked from
        timeouts.
        :return: A list of all udp sessions that are currently active
        """
        check_udp_session_list = []
        for session in self._session_list:
            if session.is_initiated:
                if isinstance(session, UdpTrackerSession) and not session.is_finished:
                    check_udp_session_list.append(session)
                continue # pragma: no cover

            self.session_connect_to_tracker(session)

        return check_udp_session_list

    def session_connect_to_tracker(self, tracker_session):
        """
        This function takes a tracker session and starts it, handling the deferred being returned
        by adding the right callbacks to it.

        :param tracker_session: The tracker session that needs to start.
        """
        def on_error(failure):
            """
            Handles the scenario of when a tracker session has failed by calling the
            tracker_manager's update_tracker_info function.
            :param failure: The failure object raised by Twisted.
            """
            # Trap value errors that are thrown by e.g. the HTTPTrackerSession when a connection fails.
            # And trap CancelledErrors that can be thrown when shutting down.
            failure.trap(ValueError, CancelledError, ConnectingCancelledError)
            self._logger.info(u"Failed to create session for tracker %s", tracker_session.tracker_url)
            # Do not update if the connection got cancelled, we are probably shutting down
            # and the tracker_manager may have shutdown already.
            if failure.check(CancelledError, ConnectingCancelledError) is None:
                self._session.lm.tracker_manager.update_tracker_info(tracker_session.tracker_url, False)

        # Make the connection to the trackers and handle the response
        deferred = tracker_session.connect_to_tracker()
        deferred.addCallbacks(self._on_result_from_session, on_error)

    def check_timed_out_udp_session(self, udp_sessions):
        """
        This method checks if udp sessions have timed out
        and either retries if they have retries left or cleans them
        if they are out of retries.
        """
        current_time = int(time.time())

        for session in udp_sessions:
            diff = current_time - session.last_contact
            if diff > session.retry_interval():
                session._is_timed_out = True

                for infohash in session.infohash_list:
                    self._pending_response_dict[infohash][u'updated'] = True
                    self._pending_response_dict[infohash][u'last_check'] = int(time.time())

                session.increase_retries()

                if session.retries > session.max_retries:
                    session._is_failed = True
                    self._logger.debug(u"%s max retry count hit", session)
                else:
                    # re-establish the connection
                    # Do it in a callLater so the timed out flag is not cleared until we are done with it.
                    self._logger.debug(u"%s retrying: %d/%d", session, session.retries, self._max_torrent_check_retries)
                    self.session_connect_to_tracker(session)

    def clean_completed_sessions(self):
        """
        Cleans sessions that have failed or are done.
        Updated the tracker info by calling the tracker_manager.
        """
        if self._session_list:
            for i in range(len(self._session_list) - 1, -1, -1):
                session = self._session_list[i]

                if session.is_failed or session.is_finished:
                    self._logger.debug(u"%s is %s", session, u'failed' if session.is_failed else u'finished')

                    # update tracker info
                    self._session.lm.tracker_manager.update_tracker_info(session.tracker_url, not session.is_failed)

                    if not session.infohash_list:
                        continue # pragma: no cover

                    # set torrent remaining responses
                    for infohash in session.infohash_list:
                        self._pending_response_dict[infohash][u'remaining_responses'] -= 1

                    self.session_stop_defer_list.append(session.cleanup())
                    self._session_list.pop(i)

    def update_with_new_results(self):
        """
        Updates the response dictionaries with new results.
        """
        for infohash, response in self._pending_response_dict.items():
            if response[u'updated']:
                response[u'updated'] = False
                self._update_torrent_result(response)

            if self._pending_response_dict[infohash][u'remaining_responses'] == 0:
                del self._pending_response_dict[infohash]

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

            # If this is not the session concerned with this url, continue
            if session.tracker_url != tracker_url or session.is_failed or session.is_finished:
                continue

            # a torrent check is already there, ignore this request
            if session.has_request(infohash):
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

        # before creating a new session, check if the tracker is alive
        if not self._session.lm.tracker_manager.should_check_tracker(tracker_url):
            self._logger.warn(u"skipping recently failed tracker %s by %d times", tracker_url,
                              self._session.lm.tracker_manager.get_tracker_info(tracker_url)['failures'])
            return

        session = create_tracker_session(tracker_url, self._on_result_from_session)

        session.create_connection()
        session.add_request(infohash)

        self._session_list.append(session)

        # update the number of responses this torrent is expecting
        self._update_pending_response(infohash)

        self._logger.debug(u"Session created for infohash %s", hexlify(infohash))

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

    def _on_result_from_session(self, seed_leech_dict):
        if self.should_stop:
            return

        for infohash in seed_leech_dict:
            seeders = seed_leech_dict[infohash][0]
            leechers = seed_leech_dict[infohash][1]

            response = self._pending_response_dict[infohash]
            response[u'last_check'] = int(time.time())

            # Since an infohash can have multiple trackers, possibly with different values, we want to
            # store the one with the most seeders else the one with the most leechers.
            # TODO(Laurens): since this makes no sense to me, find out how to do it better.
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
