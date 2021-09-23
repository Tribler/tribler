from tribler_core.components.base import Component
from tribler_core.components.implementation.libtorrent import LibtorrentComponent
from tribler_core.components.implementation.metadata_store import MetadataStoreComponent
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.restapi import RESTComponent
from tribler_core.modules.metadata_store.manager.gigachannel_manager import GigaChannelManager
from tribler_core.restapi.rest_manager import RESTManager


class GigachannelManagerComponent(Component):
    rest_manager: RESTManager
    gigachannel_manager: GigaChannelManager


    async def run(self):
        await self.use(ReporterComponent, required=False)

        config = self.session.config
        notifier = self.session.notifier

        download_manager = (await self.use(LibtorrentComponent)).download_manager
        metadata_store = (await self.use(MetadataStoreComponent)).mds
        rest_manager = self.rest_manager = (await self.use(RESTComponent)).rest_manager

        manager = GigaChannelManager(
            notifier=notifier, metadata_store=metadata_store, download_manager=download_manager
        )
        if not config.gui_test_mode:
            manager.start()

        rest_manager.get_endpoint('channels').gigachannel_manager = manager
        rest_manager.get_endpoint('collections').gigachannel_manager = manager

        self.gigachannel_manager = manager

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Gigachannel Manager...")

        self.rest_manager.get_endpoint('channels').gigachannel_manager = None
        self.rest_manager.get_endpoint('collections').gigachannel_manager = None
        await self.release(RESTComponent)

        await self.gigachannel_manager.shutdown()
