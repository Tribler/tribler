from tribler_common.simpledefs import STATE_START_TORRENT_CHECKER

from tribler_core.modules.component import Component
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.modules.torrent_checker.tracker_manager import TrackerManager
from tribler_core.session import Mediator


class TorrentCheckerComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.torrent_checker = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)

        config = mediator.config
        notifier = mediator.notifier

        metadata_store = mediator.optional.get('metadata_store', None)
        download_manager = mediator.optional.get('download_manager', None)
        api_manager = mediator.optional.get('api_manager', None)

        if not metadata_store:
            return

        tracker_manager = TrackerManager(state_dir=config.state_dir, metadata_store=metadata_store)

        if api_manager:
            api_manager.get_endpoint('state').readable_status = STATE_START_TORRENT_CHECKER

        torrent_checker = TorrentChecker(config=config,
                                         download_manager=download_manager,
                                         notifier=notifier,
                                         tracker_manager=tracker_manager,
                                         metadata_store=metadata_store)
        if api_manager:
            api_manager.get_endpoint('metadata').torrent_checker = torrent_checker

        mediator.optional['torrent_checker'] = torrent_checker
        self.torrent_checker = torrent_checker
        await torrent_checker.initialize()

    async def shutdown(self, mediator):
        await super().shutdown(mediator)
        mediator.notifier.notify_shutdown_state("Shutting down Torrent Checker...")
        await self.torrent_checker.shutdown()
