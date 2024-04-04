from __future__ import annotations

import typing
from asyncio import get_running_loop
from binascii import unhexlify
from collections import OrderedDict, defaultdict

from tribler.core.notifier import Notification
from tribler.core.user_activity.types import InfoHash

if typing.TYPE_CHECKING:
    from tribler.core.torrent_checker.torrent_checker import TorrentChecker
    from tribler.core.session import Session
    from tribler.core.database.layers.user_activity import UserActivityLayer
    from ipv8.taskmanager import TaskManager


class UserActivityManager:
    """
    A manager for user activity events.
    """

    def __init__(self, task_manager: TaskManager, session: Session, max_query_history: int) -> None:
        """
        Create a new activity manager.
        """
        super().__init__()

        self.infohash_to_queries: dict[InfoHash, list[str]] = defaultdict(list)
        self.queries: OrderedDict[str, typing.Set[InfoHash]] = OrderedDict()
        self.max_query_history = max_query_history
        self.database_manager = None
        self.torrent_checker = None
        self.task_manager = task_manager

        self.database_manager: UserActivityLayer = session.db.user_activity
        self.torrent_checker: TorrentChecker = session.torrent_checker

        # Hook events
        session.notifier.add(Notification.torrent_finished, self.on_torrent_finished)
        session.notifier.add(Notification.remote_query_results, self.on_query_results)
        session.notifier.add(Notification.local_query_results, self.on_query_results)
        self.task_manager.register_task("Check preferable", self.check_preferable,
                                        interval=session.config.get("user_activity/health_check_interval"))

    def on_query_results(self, data: dict) -> None:
        """
        Start tracking a query and its results.
        If any of the results get downloaded, we store the query (see ``on_torrent_finished``).
        """
        query = data.get("query")
        if query is None:
            return

        results = {tmd.infohash for tmd in data["results"]}
        for infohash in results:
            self.infohash_to_queries[infohash].append(query)
        self.queries[query] = results | self.queries.get(query, set())

        if len(self.queries) > self.max_query_history:
            query, results = self.queries.popitem(False)
            for infohash in results:
                self.infohash_to_queries[infohash].remove(query)
                if not self.infohash_to_queries[infohash]:
                    self.infohash_to_queries.pop(infohash)

    def on_torrent_finished(self, infohash: str, name: str, hidden: bool) -> None:
        """
        When a torrent finishes, check if we were tracking the infohash. If so, store the query and its result.
        """
        b_infohash = InfoHash(unhexlify(infohash))
        queries = self.infohash_to_queries[b_infohash]
        for query in queries:
            losing_infohashes = self.queries[query] - {b_infohash}
            self.task_manager.register_anonymous_task("Store query", get_running_loop().run_in_executor,
                                                      None, self.database_manager.store,
                                                      query, b_infohash, losing_infohashes)

    def check_preferable(self) -> None:
        """
        Check a preferable torrent.
        This causes a chain of events that leads to the torrent being gossiped more often in the ``ContentDiscovery``
        community.
        """
        random_infohashes = self.database_manager.get_preferable_to_random(limit=1)  # Note: this set can be empty!
        for infohash in random_infohashes:
            self.check(infohash)

    def check(self, infohash: bytes) -> None:
        """
        Check the health of a given infohash.
        """
        self.task_manager.register_anonymous_task("Check preferable torrent",
                                                  self.torrent_checker.check_torrent_health, infohash)
