import typing
from asyncio import get_running_loop
from binascii import unhexlify
from collections import OrderedDict, defaultdict

from ipv8.taskmanager import TaskManager

from tribler.core import notifications
from tribler.core.components.component import Component
from tribler.core.components.content_discovery.content_discovery_component import ContentDiscoveryComponent
from tribler.core.components.database.database_component import DatabaseComponent
from tribler.core.components.database.db.layers.user_activity_layer import UserActivityLayer
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.components.torrent_checker.torrent_checker_component import TorrentCheckerComponent
from tribler.core.components.user_activity.settings import UserActivitySettings
from tribler.core.components.user_activity.types import InfoHash
from tribler.core.sentry_reporter.sentry_reporter import SentryReporter


class UserActivityComponent(Component):
    infohash_to_queries: typing.Dict[InfoHash, typing.List[str]]
    queries: typing.Dict[str, typing.Set[InfoHash]]
    max_query_history: int
    database_manager: UserActivityLayer
    torrent_checker: TorrentChecker
    task_manager: TaskManager

    def __init__(self, reporter: typing.Optional[SentryReporter] = None) -> None:
        super().__init__(reporter)

        self.infohash_to_queries: dict[InfoHash, list[str]] = defaultdict(list)
        self.queries: OrderedDict[str, typing.Set[InfoHash]] = OrderedDict()
        self.max_query_history = UserActivitySettings().max_query_history
        self.database_manager = None
        self.torrent_checker = None
        self.task_manager = TaskManager()

    async def run(self) -> None:
        await super().run()

        # Load settings
        self.max_query_history = self.session.config.user_activity.max_query_history

        # Wait for dependencies
        await self.require_component(ContentDiscoveryComponent)  # remote_query_results notification
        await self.require_component(LibtorrentComponent)  # torrent_finished notification
        database_component = await self.require_component(DatabaseComponent)  # local_query_results notification
        torrent_checker_component = await self.require_component(TorrentCheckerComponent)

        self.database_manager: UserActivityLayer = database_component.db.user_activity_layer
        self.torrent_checker: TorrentChecker = torrent_checker_component.torrent_checker

        # Hook events
        self.session.notifier.add_observer(notifications.torrent_finished, self.on_torrent_finished)
        self.session.notifier.add_observer(notifications.remote_query_results, self.on_query_results)
        self.session.notifier.add_observer(notifications.local_query_results, self.on_query_results)
        self.task_manager.register_task("Check preferable", self.check_preferable,
                                        interval=self.session.config.user_activity.health_check_interval)

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
            self.task_manager.register_anonymous_task("Check preferable torrent",
                                                      self.torrent_checker.check_torrent_health, infohash)

    async def shutdown(self) -> None:
        await super().shutdown()
        await self.task_manager.shutdown_task_manager()
