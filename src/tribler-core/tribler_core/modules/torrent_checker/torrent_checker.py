import asyncio
import logging
import random
import socket
import time
from asyncio import CancelledError, gather

from ipv8.database import database_blob
from ipv8.taskmanager import TaskManager, task

from pony.orm import db_session, select

from tribler_common.simpledefs import NTFY

from tribler_core.modules.torrent_checker.torrentchecker_session import (
    FakeBep33DHTSession,
    FakeDHTSession,
    UdpSocketManager,
    create_tracker_session,
)
from tribler_core.modules.tracker_manager import MAX_TRACKER_FAILURES
from tribler_core.utilities.tracker_utils import MalformedTrackerURLException
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import has_bep33_support, is_valid_url

TRACKER_SELECTION_INTERVAL = 20    # The interval for querying a random tracker
TORRENT_SELECTION_INTERVAL = 120   # The interval for checking the health of a random torrent
MIN_TORRENT_CHECK_INTERVAL = 900   # How much time we should wait before checking a torrent again
TORRENT_CHECK_RETRY_INTERVAL = 30  # Interval when the torrent was successfully checked for the last time
MAX_TORRENTS_CHECKED_PER_SESSION = 50


class TorrentChecker(TaskManager):

    def __init__(self, session):
        super(TorrentChecker, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tribler_session = session

        self._should_stop = False
        self._session_list = {'DHT': []}

        self.socket_mgr = self.udp_transport = None

        # We keep track of the results of popular torrents checked by you.
        # The popularity community gossips this information around.
        self.torrents_checked = set()

    async def initialize(self):
        self.register_task("tracker_check", self.check_random_tracker, interval=TRACKER_SELECTION_INTERVAL)
        self.register_task("torrent_check", self.check_random_torrent, interval=TORRENT_SELECTION_INTERVAL)
        self.socket_mgr = UdpSocketManager()
        await self.create_socket_or_schedule()

    async def listen_on_udp(self):
        loop = asyncio.get_event_loop()
        transport, _ = await loop.create_datagram_endpoint(lambda: self.socket_mgr, local_addr=('0.0.0.0', 0))
        return transport

    async def create_socket_or_schedule(self):
        """
        This method attempts to bind to a UDP port. If it fails for some reason (i.e. no network connection), we try
        again later.
        """
        try:
            self.udp_transport = await self.listen_on_udp()
        except socket.error as e:
            self._logger.error("Error when creating UDP socket in torrent checker: %s", e)
            self.register_task("listen_udp_port", self.create_socket_or_schedule, delay=10)

    async def shutdown(self):
        """
        Shutdown the torrent health checker.

        Once shut down it can't be started again.
        :returns A deferred that will fire once the shutdown has completed.
        """
        self._should_stop = True

        if self.udp_transport:
            self.udp_transport.close()
            self.udp_transport = None

        await self.shutdown_task_manager()

    async def check_random_tracker(self):
        """
        Calling this method will fetch a random tracker from the database, select some torrents that have this
        tracker, and perform a request to these trackers.
        Return whether the check was successful.
        """
        if self._should_stop:
            self._logger.warning("Not performing tracker check since we are shutting down")
            return False

        tracker = self.get_valid_next_tracker_for_auto_check()
        if tracker is None:
            self._logger.warning(u"No tracker to select from, skip")
            return False

        self._logger.debug(u"Start selecting torrents on tracker %s.", tracker.url)

        # get the torrents that should be checked
        with db_session:
            dynamic_interval = TORRENT_CHECK_RETRY_INTERVAL * (2 ** tracker.failures)
            # FIXME: this is a really dumb fix for update_tracker_info not being called in some cases
            if tracker.failures >= MAX_TRACKER_FAILURES:
                self.update_tracker_info(tracker.url, False)
                return False
            torrents = select(ts for ts in tracker.torrents if ts.last_check + dynamic_interval < int(time.time()))
            infohashes = [t.infohash for t in torrents[:MAX_TORRENTS_CHECKED_PER_SESSION]]

        if len(infohashes) == 0:
            # We have no torrent to recheck for this tracker. Still update the last_check for this tracker.
            self._logger.info("No torrent to check for tracker %s", tracker.url)
            self.update_tracker_info(tracker.url, True)
            return False

        try:
            session = self._create_session_for_request(tracker.url, timeout=30)
        except MalformedTrackerURLException as e:
            # Remove the tracker from the database
            self.remove_tracker(tracker.url)
            self._logger.error(e)
            return False

        # We shuffle the list so that different infohashes are checked on subsequent scrape requests if the total
        # number of infohashes exceeds the maximum number of infohashes we check.
        random.shuffle(infohashes)
        for infohash in infohashes:
            session.add_infohash(infohash)

        self._logger.info(u"Selected %d new torrents to check on tracker: %s", len(infohashes), tracker.url)
        try:
            await self.connect_to_tracker(session)
            return True
        except:
            return False

    async def connect_to_tracker(self, session):
        try:
            info_dict = await session.connect_to_tracker()
            return self._on_result_from_session(session, info_dict)
        except CancelledError:
            self._logger.info("Tracker session is being cancelled (url %s)", session.tracker_url)
            self.clean_session(session)
        except Exception as e:
            self._logger.warning("Got session error for URL %s: %s", session.tracker_url, str(e).replace(u'\n]', u']'))
            self.clean_session(session)
            self.tribler_session.tracker_manager.update_tracker_info(session.tracker_url, False)
            e.tracker_url = session.tracker_url
            raise e

    @db_session
    def check_random_torrent(self):
        """
        Perform a full health check on a random torrent in the database.
        We prioritize torrents that have no health info attached.
        """
        random_torrents = list(self.tribler_session.mds.TorrentState.select().
                               order_by(lambda g: g.last_check).limit(10))

        if not random_torrents:
            self._logger.info("Could not find any eligible torrent for random torrent check")
            return None

        if not self.torrents_checked:
            # We have not checked any torrent yet - pick three torrents to health check
            random_torrents = random.sample(random_torrents, min(3, len(random_torrents)))
            infohashes = []
            for random_torrent in random_torrents:
                self.check_torrent_health(bytes(random_torrent.infohash))
                infohashes.append(random_torrent.infohash)
            return infohashes

        random_torrent = random.choice(random_torrents)
        self.check_torrent_health(bytes(random_torrent.infohash))
        return [bytes(random_torrent.infohash)]

    def get_valid_next_tracker_for_auto_check(self):
        tracker = self.get_next_tracker_for_auto_check()
        while tracker and not is_valid_url(tracker.url):
            self.remove_tracker(tracker.url)
            tracker = self.get_next_tracker_for_auto_check()
        return tracker

    def get_next_tracker_for_auto_check(self):
        return self.tribler_session.tracker_manager.get_next_tracker_for_auto_check()

    def remove_tracker(self, tracker_url):
        self.tribler_session.tracker_manager.remove_tracker(tracker_url)

    def update_tracker_info(self, tracker_url, is_successful):
        self.tribler_session.tracker_manager.update_tracker_info(tracker_url, is_successful)

    def is_blacklisted_tracker(self, tracker_url):
        return tracker_url in self.tribler_session.tracker_manager.blacklist

    @db_session
    def get_valid_trackers_of_torrent(self, torrent_id):
        """ Get a set of valid trackers for torrent. Also remove any invalid torrent."""
        db_tracker_list = self.tribler_session.mds.TorrentState.get(infohash=database_blob(torrent_id)).trackers
        return set([tracker.url for tracker in db_tracker_list
                    if is_valid_url(tracker.url) and not self.is_blacklisted_tracker(tracker.url)])

    def update_torrents_checked(self, new_result):
        """
        Update the set with torrents that we have checked ourselves.
        """
        new_result_tuple = (new_result['infohash'], new_result['seeders'],
                            new_result['leechers'], new_result['last_check'])
        if new_result['seeders'] > 0:
            self.torrents_checked.add(new_result_tuple)

    def on_torrent_health_check_completed(self, infohash, result):
        final_response = {}
        if not result or not isinstance(result, list):
            self._logger.info("Received invalid torrent checker result")
            self.tribler_session.notifier.notify(NTFY.CHANNEL_ENTITY_UPDATED,
                                                 {"infohash": hexlify(infohash),
                                                  "num_seeders": 0,
                                                  "num_leechers": 0,
                                                  "last_tracker_check": int(time.time()),
                                                  "health": "updated"})
            return final_response

        torrent_update_dict = {'infohash': infohash, 'seeders': 0, 'leechers': 0, 'last_check': int(time.time())}
        for response in reversed(result):
            if isinstance(response, Exception):
                final_response[response.tracker_url] = {'error': str(response)}
                continue
            elif response is None:
                self._logger.warning("Torrent health response is none!")
                continue
            response_keys = list(response.keys())
            final_response[response_keys[0]] = response[response_keys[0]][0]

            s = response[response_keys[0]][0]['seeders']
            l = response[response_keys[0]][0]['leechers']

            # More leeches is better, because undefined peers are marked as leeches in DHT
            if s > torrent_update_dict['seeders'] or \
                    (s == torrent_update_dict['seeders'] and l > torrent_update_dict['leechers']):
                torrent_update_dict['seeders'] = s
                torrent_update_dict['leechers'] = l

        self._update_torrent_result(torrent_update_dict)
        self.update_torrents_checked(torrent_update_dict)

        # TODO: DRY! Stop doing lots of formats, just make REST endpoint automatically encode binary data to hex!
        self.tribler_session.notifier.notify(NTFY.CHANNEL_ENTITY_UPDATED,
                                             {"infohash": hexlify(infohash),
                                              "num_seeders": torrent_update_dict["seeders"],
                                              "num_leechers": torrent_update_dict["leechers"],
                                              "last_tracker_check": torrent_update_dict["last_check"],
                                              "health": "updated"})
        return final_response

    @task
    async def check_torrent_health(self, infohash, timeout=20, scrape_now=False):
        """
        Check the health of a torrent with a given infohash.
        :param infohash: Torrent infohash.
        :param timeout: The timeout to use in the performed requests
        :param scrape_now: Flag whether we want to force scraping immediately
        """
        tracker_set = []

        # We first check whether the torrent is already in the database and checked before
        with db_session:
            result = self.tribler_session.mds.TorrentState.get(infohash=database_blob(infohash))
            if result:
                torrent_id = result.infohash
                last_check = result.last_check
                time_diff = time.time() - last_check
                if time_diff < MIN_TORRENT_CHECK_INTERVAL and not scrape_now:
                    self._logger.debug("time interval too short, not doing torrent health check for %s",
                                       hexlify(infohash))
                    return {
                        "db": {
                            "seeders": result.seeders,
                            "leechers": result.leechers,
                            "infohash": hexlify(infohash)
                        }
                    }

                # get torrent's tracker list from DB
                tracker_set = self.get_valid_trackers_of_torrent(torrent_id)

        hops = self.tribler_session.config.get_default_number_hops()
        socks_listen_ports = self.tribler_session.config.get_tunnel_community_socks5_listen_ports()
        proxy = ('127.0.0.1', socks_listen_ports[hops - 1]) if hops > 0 else None

        tasks = []
        for tracker_url in tracker_set:
            session = self._create_session_for_request(tracker_url, timeout=timeout, proxy=proxy)
            session.add_infohash(infohash)
            tasks.append(self.connect_to_tracker(session))

        if has_bep33_support():
            # Create a (fake) DHT session for the lookup if we have support for BEP33.
            session = FakeBep33DHTSession(self.tribler_session, infohash, timeout)

        else:
            # Otherwise, fallback on the normal DHT metainfo lookups.
            session = FakeDHTSession(self.tribler_session, infohash, timeout)

        self._session_list['DHT'].append(session)
        tasks.append(self.connect_to_tracker(session))

        res = await gather(*tasks, return_exceptions=True)
        return self.on_torrent_health_check_completed(infohash, res)

    def _create_session_for_request(self, tracker_url, timeout=20, proxy=None):
        session = create_tracker_session(tracker_url, timeout, proxy, self.socket_mgr)

        if tracker_url not in self._session_list:
            self._session_list[tracker_url] = []
        self._session_list[tracker_url].append(session)

        self._logger.debug(u"Session created for tracker %s", tracker_url)
        return session

    def clean_session(self, session):
        self.tribler_session.tracker_manager.update_tracker_info(session.tracker_url, not session.is_failed)
        self.register_task(f"Stop tracker session {str(session.tracker_address)}-{str(id(session))}", session.cleanup)

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
            torrent = self.tribler_session.mds.TorrentState.get(infohash=database_blob(infohash))
            if not torrent:
                self._logger.warning(
                    "Tried to update torrent health data in DB for an unknown torrent: %s", hexlify(infohash))
                return
            torrent.seeders = seeders
            torrent.leechers = leechers
            torrent.last_check = last_check
