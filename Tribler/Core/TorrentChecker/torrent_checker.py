from __future__ import absolute_import

import logging
import random
import socket
import time
from binascii import hexlify

from ipv8.database import database_blob
from ipv8.taskmanager import TaskManager

from pony.orm import db_session

from twisted.internet import reactor
from twisted.internet.defer import CancelledError, DeferredList, maybeDeferred, succeed
from twisted.internet.error import ConnectingCancelledError, ConnectionLost
from twisted.internet.task import LoopingCall
from twisted.python.failure import Failure
from twisted.web.client import HTTPConnectionPool

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import LEGACY_ENTRY
from Tribler.Core.Modules.MetadataStore.serialization import REGULAR_TORRENT
from Tribler.Core.TorrentChecker.session import FakeDHTSession, UdpSocketManager, create_tracker_session
from Tribler.Core.Utilities.tracker_utils import MalformedTrackerURLException
from Tribler.Core.Utilities.utilities import has_bep33_support, is_valid_url
from Tribler.Core.simpledefs import NTFY_TORRENT, NTFY_UPDATE


TRACKER_SELECTION_INTERVAL = 20    # The interval for querying a random tracker
TORRENT_SELECTION_INTERVAL = 120   # The interval for checking the health of a random torrent
MIN_TORRENT_CHECK_INTERVAL = 900   # How much time we should wait before checking a torrent again
TORRENT_CHECK_RETRY_INTERVAL = 30  # Interval when the torrent was successfully checked for the last time


class TorrentChecker(TaskManager):

    def __init__(self, session):
        super(TorrentChecker, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tribler_session = session

        self._should_stop = False

        self.tracker_check_lc = self.register_task("tracker_check", LoopingCall(self.check_random_tracker))
        self.torrent_check_lc = self.register_task("torrent_check", LoopingCall(self.check_random_torrent))

        self._session_list = {'DHT': []}

        # Track all session cleanups
        self.session_stop_defer_list = []

        self.socket_mgr = self.udp_port = None
        self.connection_pool = None

        # We keep track of the results of popular torrents checked by you.
        # The popularity community gossips this information around.
        self.torrents_checked = set()

    def initialize(self):
        self.tracker_check_lc.start(TRACKER_SELECTION_INTERVAL, now=False)
        self.torrent_check_lc.start(TORRENT_SELECTION_INTERVAL, now=False)
        self.connection_pool = HTTPConnectionPool(reactor, False)
        self.socket_mgr = UdpSocketManager()
        self.create_socket_or_schedule()

    def listen_on_udp(self):
        return reactor.listenUDP(0, self.socket_mgr)

    def create_socket_or_schedule(self):
        """
        This method attempts to bind to a UDP port. If it fails for some reason (i.e. no network connection), we try
        again later.
        """
        try:
            self.udp_port = self.listen_on_udp()
        except socket.error as exc:
            self._logger.error("Error when creating UDP socket in torrent checker: %s", exc)
            self.register_task("listen_udp_port", reactor.callLater(10, self.create_socket_or_schedule))

    def shutdown(self):
        """
        Shutdown the torrent health checker.

        Once shut down it can't be started again.
        :returns A deferred that will fire once the shutdown has completed.
        """
        self._should_stop = True

        if self.udp_port:
            self.session_stop_defer_list.append(maybeDeferred(self.udp_port.stopListening))
            self.udp_port = None

        if self.connection_pool:
            self.session_stop_defer_list.append(self.connection_pool.closeCachedConnections())

        self.shutdown_task_manager()

        # kill all the tracker sessions.
        # Wait for the defers to all have triggered by using a DeferredList
        for tracker_url in self._session_list.keys():
            for session in self._session_list[tracker_url]:
                self.session_stop_defer_list.append(session.cleanup())

        return DeferredList(self.session_stop_defer_list)

    def check_random_tracker(self):
        """
        Calling this method will fetch a random tracker from the database, select some torrents that have this
        tracker, and perform a request to these trackers.
        """
        tracker_url = self.get_valid_next_tracker_for_auto_check()
        if tracker_url is None:
            self._logger.warn(u"No tracker to select from, skip")
            return succeed(None)

        self._logger.debug(u"Start selecting torrents on tracker %s.", tracker_url)

        # get the torrents that should be checked
        infohashes = []
        with db_session:
            tracker = self.tribler_session.lm.mds.TrackerState.get(url=tracker_url)
            if tracker:
                torrents = tracker.torrents
                for torrent in torrents:
                    dynamic_interval = TORRENT_CHECK_RETRY_INTERVAL * (2 ** tracker.failures)
                    if torrent.last_check + dynamic_interval < int(time.time()):
                        infohashes.append(torrent.infohash)

        if len(infohashes) == 0:
            # We have no torrent to recheck for this tracker. Still update the last_check for this tracker.
            self._logger.info("No torrent to check for tracker %s", tracker_url)
            self.update_tracker_info(tracker_url, True)
            return succeed(None)
        elif tracker_url != u'DHT' and tracker_url != u'no-DHT':
            try:
                session = self._create_session_for_request(tracker_url, timeout=30)
            except MalformedTrackerURLException as e:
                # Remove the tracker from the database
                self.remove_tracker(tracker_url)
                self._logger.error(e)
                return succeed(None)

            # We shuffle the list so that different infohashes are checked on subsequent scrape requests if the total
            # number of infohashes exceeds the maximum number of infohashes we check.
            random.shuffle(infohashes)
            for infohash in infohashes:
                session.add_infohash(infohash)

            self._logger.info(u"Selected %d new torrents to check on tracker: %s", len(infohashes), tracker_url)
            return session.connect_to_tracker().addCallbacks(*self.get_callbacks_for_session(session)) \
                .addErrback(lambda _: None)

    @db_session
    def check_random_torrent(self):
        """
        Perform a full health check on a random torrent in the database.
        We prioritize torrents that have no health info attached.
        """
        random_torrents = self.tribler_session.lm.mds.TorrentState.select(
            lambda g: (metadata for metadata in g.metadata if metadata.status != LEGACY_ENTRY and
                       metadata.metadata_type == REGULAR_TORRENT))\
            .order_by(lambda g: g.last_check).limit(10)

        if not random_torrents:
            self._logger.info("Could not find any eligible torrent for random torrent check")
            return None

        if not self.torrents_checked:
            # We have not checked any torrent yet - pick three torrents to health check
            random_torrents = random.sample(random_torrents, min(3, len(random_torrents)))
            infohashes = []
            for random_torrent in random_torrents:
                self.check_torrent_health(str(random_torrent.infohash))
                infohashes.append(str(random_torrent.infohash))
            return infohashes

        random_torrent = random.choice(random_torrents)
        self.check_torrent_health(str(random_torrent.infohash))
        return [random_torrent.infohash]

    def get_callbacks_for_session(self, session):
        success_lambda = lambda info_dict: self._on_result_from_session(session, info_dict)
        error_lambda = lambda failure: self.on_session_error(session, failure)
        return success_lambda, error_lambda

    def get_valid_next_tracker_for_auto_check(self):
        tracker_url = self.get_next_tracker_for_auto_check()
        while tracker_url and not is_valid_url(tracker_url):
            self.remove_tracker(tracker_url)
            tracker_url = self.get_next_tracker_for_auto_check()
        return tracker_url

    def get_next_tracker_for_auto_check(self):
        return self.tribler_session.lm.tracker_manager.get_next_tracker_for_auto_check()

    def remove_tracker(self, tracker_url):
        self.tribler_session.lm.tracker_manager.remove_tracker(tracker_url)

    def update_tracker_info(self, tracker_url, value):
        self.tribler_session.lm.tracker_manager.update_tracker_info(tracker_url, value)

    def is_blacklisted_tracker(self, tracker_url):
        return tracker_url in self.tribler_session.lm.tracker_manager.blacklist

    @db_session
    def get_valid_trackers_of_torrent(self, torrent_id):
        """ Get a set of valid trackers for torrent. Also remove any invalid torrent."""
        db_tracker_list = self.tribler_session.lm.mds.TorrentState.get(infohash=database_blob(torrent_id)).trackers
        return set([str(tracker.url) for tracker in db_tracker_list
                    if is_valid_url(str(tracker.url)) and not self.is_blacklisted_tracker(str(tracker.url))])

    def update_torrents_checked(self, new_result):
        """
        Update the set with torrents that we have checked ourselves.
        """
        new_result_tuple = (new_result['infohash'], new_result['seeders'],
                            new_result['leechers'], new_result['last_check'])
        self.torrents_checked.add(new_result_tuple)

    def on_torrent_health_check_completed(self, infohash, result):
        final_response = {}
        if not result or not isinstance(result, list):
            self._logger.info("Received invalid torrent checker result")
            return final_response

        torrent_update_dict = {'infohash': infohash, 'seeders': 0, 'leechers': 0, 'last_check': int(time.time())}
        for success, response in reversed(result):
            if not success and isinstance(response, Failure):
                final_response[response.tracker_url] = {'error': response.getErrorMessage()}
                continue
            final_response[response.keys()[0]] = response[response.keys()[0]][0]

            s = response[response.keys()[0]][0]['seeders']
            l = response[response.keys()[0]][0]['leechers']

            # More leeches is better, because undefined peers are marked as leeches in DHT
            if s > torrent_update_dict['seeders'] or \
                    (s == torrent_update_dict['seeders'] and l > torrent_update_dict['leechers']):
                torrent_update_dict['seeders'] = s
                torrent_update_dict['leechers'] = l

        self._update_torrent_result(torrent_update_dict)
        self.update_torrents_checked(torrent_update_dict)

        # TODO: DRY! Stop doing lots of formats, just make REST endpoint automatically encode binary data to hex!
        self.tribler_session.notifier.notify(NTFY_TORRENT, NTFY_UPDATE, infohash,
                                             {"num_seeders": torrent_update_dict["seeders"],
                                              "num_leechers": torrent_update_dict["leechers"],
                                              "last_tracker_check": torrent_update_dict["last_check"],
                                              "health": "updated"})
        return final_response

    def check_torrent_health(self, infohash, timeout=20, scrape_now=False):
        """
        Check the health of a torrent with a given infohash.
        :param infohash: Torrent infohash.
        :param timeout: The timeout to use in the performed requests
        :param scrape_now: Flag whether we want to force scraping immediately
        """
        tracker_set = []

        # We first check whether the torrent is already in the database and checked before
        with db_session:
            result = self.tribler_session.lm.mds.TorrentState.get(infohash=database_blob(infohash))
            if result:
                torrent_id = str(result.infohash)
                last_check = result.last_check
                time_diff = time.time() - last_check
                if time_diff < MIN_TORRENT_CHECK_INTERVAL and not scrape_now:
                    self._logger.debug("time interval too short, not doing torrent health check for %s",
                                       hexlify(infohash))
                    return succeed({
                        "db": {
                            "seeders": result.seeders,
                            "leechers": result.leechers,
                            "infohash": hexlify(infohash)
                        }
                    })

                # get torrent's tracker list from DB
                tracker_set = self.get_valid_trackers_of_torrent(torrent_id)

        deferred_list = []
        for tracker_url in tracker_set:
            session = self._create_session_for_request(tracker_url, timeout=timeout)
            session.add_infohash(infohash)
            deferred_list.append(session.connect_to_tracker().
                                 addCallbacks(*self.get_callbacks_for_session(session)))

        # Create a (fake) DHT session for the lookup if we have support for BEP33.
        if has_bep33_support():
            session = FakeDHTSession(self.tribler_session, infohash, timeout)
            self._session_list['DHT'].append(session)
            deferred_list.append(session.connect_to_tracker().
                                 addCallbacks(*self.get_callbacks_for_session(session)))

        return DeferredList(deferred_list, consumeErrors=True).addCallback(
            lambda res: self.on_torrent_health_check_completed(infohash, res))

    def on_session_error(self, session, failure):
        """
        Handles the scenario of when a tracker session has failed by calling the
        tracker_manager's update_tracker_info function.
        Trap value errors that are thrown by e.g. the HTTPTrackerSession when a connection fails.
        And trap CancelledErrors that can be thrown when shutting down.
        :param failure: The failure object raised by Twisted.
        """
        failure.trap(ValueError, CancelledError, ConnectingCancelledError, ConnectionLost, RuntimeError)
        self._logger.warning(u"Got session error for URL %s: %s", session.tracker_url,
                             str(failure).replace(u'\n]', u']'))

        self.clean_session(session)

        # Do not update if the connection got cancelled, we are probably shutting down
        # and the tracker_manager may have shutdown already.
        if failure.check(CancelledError, ConnectingCancelledError) is None:
            self.tribler_session.lm.tracker_manager.update_tracker_info(session.tracker_url, False)

        failure.tracker_url = session.tracker_url
        return failure

    def _create_session_for_request(self, tracker_url, timeout=20):
        session = create_tracker_session(tracker_url, timeout, self.socket_mgr, connection_pool=self.connection_pool)

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
        if len(self._session_list[session.tracker_url]) == 0 and session.tracker_url != u"DHT":
            del self._session_list[session.tracker_url]

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

        self._logger.debug(u"Update result %s/%s for %s", seeders, leechers, hexlify(infohash))

        with db_session:
            # Update torrent state
            torrent = self.tribler_session.lm.mds.TorrentState.get(infohash=database_blob(infohash))
            if not torrent:
                # Something is wrong, there should exist a corresponding TorrentState entry in the DB.
                return
            torrent.seeders = seeders
            torrent.leechers = leechers
            torrent.last_check = last_check
