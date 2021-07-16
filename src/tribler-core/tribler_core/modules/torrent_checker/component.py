from tribler_common.simpledefs import STATE_START_TORRENT_CHECKER

from tribler_core.modules.component import Component
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.modules.torrent_checker.tracker_manager import TrackerManager
from tribler_core.restapi.rest_manager import RESTManager
from tribler_core.session import Mediator


class TorrentCheckerComponent(Component):
    provided_futures = (TorrentChecker, )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.torrent_checker = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)
        config = mediator.config

        metadata_store = await mediator.awaitable_components.get(MetadataStore)
        download_manager = await mediator.awaitable_components.get(DownloadManager)
        if not metadata_store or not download_manager:
            return

        tracker_manager = TrackerManager(state_dir=config.state_dir, metadata_store=metadata_store)
        torrent_checker = TorrentChecker(config=config,
                                         download_manager=download_manager,
                                         notifier=mediator.notifier,
                                         tracker_manager=tracker_manager,
                                         metadata_store=metadata_store)
        mediator.awaitable_components[TorrentChecker].set_result(torrent_checker)
        self.torrent_checker = torrent_checker

        api_manager = await mediator.awaitable_components.get(RESTManager)
        if api_manager:
            api_manager.get_endpoint('state').readable_status = STATE_START_TORRENT_CHECKER
        await torrent_checker.initialize()

        if api_manager:
            api_manager.get_endpoint('metadata').torrent_checker = torrent_checker

    async def shutdown(self, mediator):
        if self.torrent_checker:
            mediator.notifier.notify_shutdown_state("Shutting down Torrent Checker...")
            await self.torrent_checker.shutdown()
        await super().shutdown(mediator)
