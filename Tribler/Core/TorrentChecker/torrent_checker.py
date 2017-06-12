import logging
import time
from binascii import hexlify
from twisted.internet import reactor
from twisted.internet.defer import DeferredList, CancelledError, fail, succeed
from twisted.internet.error import ConnectingCancelledError
from twisted.python.failure import Failure

from Tribler.Core.TorrentChecker.session import create_tracker_session, FakeDHTSession
from Tribler.Core.Utilities.tracker_utils import MalformedTrackerURLException
from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import blocking_call_on_reactor_thread, call_on_reactor_thread

# some settings
DEFAULT_TORRENT_SELECTION_INTERVAL = 20  # every 20 seconds, the thread will select torrents to check
DEFAULT_TORRENT_CHECK_INTERVAL = 900  # base multiplier for the check delay

DEFAULT_MAX_TORRENT_CHECK_RETRIES = 8  # max check delay increments when failed.
DEFAULT_TORRENT_CHECK_RETRY_INTERVAL = 30  # interval when the torrent was successfully checked for the last time


class TorrentChecker(TaskManager):

    def __init__(self, session):
        super(TorrentChecker, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tribler_session = session

        self._torrent_db = None

        self._should_stop = False

        self._torrent_check_interval = DEFAULT_TORRENT_CHECK_INTERVAL
        self._torrent_check_retry_interval = DEFAULT_TORRENT_CHECK_RETRY_INTERVAL
        self._max_torrent_check_retries = DEFAULT_MAX_TORRENT_CHECK_RETRIES

        self._session_list = {'DHT': []}
        self._last_torrent_selection_time = 0

        # Track all session cleanups
        self.session_stop_defer_list = []

    @blocking_call_on_reactor_thread
    def initialize(self):
        self._torrent_db = self.tribler_session.open_dbhandler(NTFY_TORRENTS)
        self._reschedule_tracker_select()

    def shutdown(self):
        """
        Shutdown the torrent health checker.

        Once shut down it can't be started again.
        :returns A deferred that will fire once the shutdown has completed.
        """
        self._should_stop = True

        self.cancel_all_pending_tasks()

        # kill all the tracker sessions.
        # Wait for the defers to all have triggered by using a DeferredList
        for tracker_url in self._session_list.keys():
            for session in self._session_list[tracker_url]:
                self.session_stop_defer_list.append(session.cleanup())

        defer_stop_list = DeferredList(self.session_stop_defer_list)

        self._session_list = None

        self._torrent_db = None
        self.tribler_session = None

        return defer_stop_list

    def _reschedule_tracker_select(self):
        """
        Changes the tracker selection interval dynamically and schedules the task.
        """
        # dynamically change the interval: update at least every 2h
        num_torrents = self._torrent_db.getNumberCollectedTorrents()

        tracker_select_interval = min(max(7200 / num_torrents, 10), 100) if num_torrents \
            else DEFAULT_TORRENT_SELECTION_INTERVAL

        self._logger.debug(u"tracker selection interval changed to %s", tracker_select_interval)

        self.register_task(u"torrent_checker_tracker_selection",
                           reactor.callLater(tracker_select_interval, self._task_select_tracker))

    def _task_select_tracker(self):
        """
        The regularly scheduled task that selects torrents associated with a specific tracker to check.
        """

        # update the torrent selection interval
        self._reschedule_tracker_select()

        # start selecting torrents
        result = self.tribler_session.lm.tracker_manager.get_next_tracker_for_auto_check()
        if result is None:
            self._logger.warn(u"No tracker to select from, skip")
            return succeed(None)

        tracker_url, _ = result
        self._logger.debug(u"Start selecting torrents on tracker %s.", tracker_url)

        # get the torrents that should be checked
        infohashes = self._torrent_db.getTorrentsOnTracker(tracker_url, int(time.time()))

        if len(infohashes) == 0:
            # We have not torrent to recheck for this tracker. Still update the last_check for this tracker.
            self._logger.info("No torrent to check for tracker %s", tracker_url)
            self.tribler_session.lm.tracker_manager.update_tracker_info(tracker_url, True)
            return succeed(None)
        elif tracker_url != u'DHT' and tracker_url != u'no-DHT'\
                and self.tribler_session.lm.tracker_manager.should_check_tracker(tracker_url):

            try:
                session = self._create_session_for_request(tracker_url, timeout=30)
            except MalformedTrackerURLException as e:
                self._logger.error(e)
                return succeed(None)

            for infohash in infohashes:
                session.add_infohash(infohash)

            self._logger.info(u"Selected %d new torrents to check on tracker: %s", len(infohashes), tracker_url)
            return session.connect_to_tracker().addCallbacks(*self.get_callbacks_for_session(session))\
                .addErrback(lambda _: None)

    def get_callbacks_for_session(self, session):
        success_lambda = lambda info_dict: self._on_result_from_session(session, info_dict)
        error_lambda = lambda failure: self.on_session_error(session, failure)
        return success_lambda, error_lambda

    def on_gui_request_completed(self, infohash, result):
        final_response = {}

        torrent_update_dict = {'infohash': infohash, 'seeders': 0, 'leechers': 0, 'last_check': time.time()}
        for success, response in result:
            if not success and isinstance(response, Failure):
                final_response[response.tracker_url] = {'error': response.getErrorMessage()}
                continue

            response_seeders = response[response.keys()[0]][0]['seeders']
            response_leechers = response[response.keys()[0]][0]['leechers']
            if response_seeders > torrent_update_dict['seeders'] or \
                    (response_seeders == torrent_update_dict['seeders']
                     and response_leechers < torrent_update_dict['leechers']):
                torrent_update_dict['seeders'] = response_seeders
                torrent_update_dict['leechers'] = response_leechers

            final_response[response.keys()[0]] = response[response.keys()[0]][0]

        self._update_torrent_result(torrent_update_dict)

        return final_response

    @call_on_reactor_thread
    def add_gui_request(self, infohash, timeout=20, scrape_now=False):
        """
        Public API for adding a GUI request.
        :param infohash: Torrent infohash.
        :param timeout: The timeout to use in the performed requests
        :param scrape_now: Flag whether we want to force scraping immediately
        """
        result = self._torrent_db.getTorrent(infohash, (u'torrent_id', u'last_tracker_check',
                                                        u'num_seeders', u'num_leechers'), False)
        if result is None:
            self._logger.warn(u"torrent info not found, skip. infohash: %s", hexlify(infohash))
            return fail(Failure(RuntimeError("Torrent not found")))

        torrent_id = result[u'torrent_id']
        last_check = result[u'last_tracker_check']
        time_diff = time.time() - last_check
        if time_diff < self._torrent_check_interval and not scrape_now:
            self._logger.debug(u"time interval too short, skip GUI request. infohash: %s", hexlify(infohash))
            return succeed({"db": {"seeders": result[u'num_seeders'],
                                   "leechers": result[u'num_leechers'], "infohash": infohash.encode('hex')}})

        # get torrent's tracker list from DB
        tracker_set = set()
        db_tracker_list = self._torrent_db.getTrackerListByTorrentID(torrent_id)
        for tracker in db_tracker_list:
            tracker_set.add(tracker)

        if not tracker_set:
            self._logger.warn(u"no trackers, skip GUI request. infohash: %s", hexlify(infohash))
            # TODO: add code to handle torrents with no tracker
            return fail(Failure(RuntimeError("No trackers available for this torrent")))

        deferred_list = []
        for tracker_url in tracker_set:
            if tracker_url == u'DHT':
                # Create a (fake) DHT session for the lookup
                session = FakeDHTSession(self.tribler_session, infohash, timeout)
                self._session_list['DHT'].append(session)
                deferred_list.append(session.connect_to_tracker().
                                     addCallbacks(*self.get_callbacks_for_session(session)))
            elif tracker_url != u'no-DHT':
                session = self._create_session_for_request(tracker_url, timeout=timeout)
                session.add_infohash(infohash)
                deferred_list.append(session.connect_to_tracker().
                                     addCallbacks(*self.get_callbacks_for_session(session)))

        return DeferredList(deferred_list, consumeErrors=True).addCallback(
            lambda res: self.on_gui_request_completed(infohash, res))

    def on_session_error(self, session, failure):
        """
        Handles the scenario of when a tracker session has failed by calling the
        tracker_manager's update_tracker_info function.
        Trap value errors that are thrown by e.g. the HTTPTrackerSession when a connection fails.
        And trap CancelledErrors that can be thrown when shutting down.
        :param failure: The failure object raised by Twisted.
        """
        failure.trap(ValueError, CancelledError, ConnectingCancelledError, RuntimeError)
        self._logger.warning(u"Got session error for URL %s: %s", session.tracker_url, failure)

        # Do not update if the connection got cancelled, we are probably shutting down
        # and the tracker_manager may have shutdown already.
        if failure.check(CancelledError, ConnectingCancelledError) is None:
            self.tribler_session.lm.tracker_manager.update_tracker_info(session.tracker_url, False)

        failure.tracker_url = session.tracker_url
        return failure

    def _create_session_for_request(self, tracker_url, timeout=20):
        session = create_tracker_session(tracker_url, timeout)

        if tracker_url not in self._session_list:
            self._session_list[tracker_url] = []
        self._session_list[tracker_url].append(session)

        self._logger.debug(u"Session created for tracker %s", tracker_url)
        return session

    def clean_session(self, session):
        self.tribler_session.lm.tracker_manager.update_tracker_info(session.tracker_url, not session.is_failed)
        self.session_stop_defer_list.append(session.cleanup())

        # Remove the session from our session list dictionary
        self._session_list[session.tracker_url].remove(session)

    def _on_result_from_session(self, session, result_list):
        if self._should_stop:
            return

        self.clean_session(session)

        return result_list

    def _update_torrent_result(self, response):
        infohash = response['infohash']
        seeders = response['seeders']
        leechers = response['leechers']
        last_check = response['last_check']

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
