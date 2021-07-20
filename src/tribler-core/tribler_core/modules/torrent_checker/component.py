from tribler_common.simpledefs import STATE_START_TORRENT_CHECKER
from tribler_core.awaitable_resources import METADATA_STORE, DOWNLOAD_MANAGER, TORRENT_CHECKER, REST_MANAGER

from tribler_core.modules.component import Component
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.modules.torrent_checker.tracker_manager import TrackerManager
from tribler_core.restapi.rest_manager import RESTManager
from tribler_core.session import Mediator


class TorrentCheckerComponent(Component):
    role = TORRENT_CHECKER

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rest_manager = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)
        config = mediator.config

        metadata_store = await self.use(mediator, METADATA_STORE)
        download_manager = await self.use(mediator, DOWNLOAD_MANAGER)

        tracker_manager = TrackerManager(state_dir=config.state_dir, metadata_store=metadata_store)
        torrent_checker = TorrentChecker(config=config,
                                         download_manager=download_manager,
                                         notifier=mediator.notifier,
                                         tracker_manager=tracker_manager,
                                         metadata_store=metadata_store)
        self.provide(mediator, torrent_checker)

        rest_manager = self._rest_manager =  await self.use(mediator, REST_MANAGER)
        rest_manager.get_endpoint('state').readable_status = STATE_START_TORRENT_CHECKER

        await torrent_checker.initialize()
        rest_manager.get_endpoint('metadata').torrent_checker = torrent_checker

    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down Torrent Checker...")
        self._rest_manager.get_endpoint('metadata').torrent_checker = None
        self.release_dependency(mediator, REST_MANAGER)

        await self._provided_object.shutdown()
        await super().shutdown(mediator)
