from tribler_core.components.base import Component
from tribler_core.components.implementation.libtorrent import LibtorrentComponent
from tribler_core.components.implementation.metadata_store import MetadataStoreComponent
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.restapi import RESTComponent
from tribler_core.modules.metadata_store.manager.gigachannel_manager import GigaChannelManager
from tribler_core.restapi.rest_manager import RESTManager


class GigachannelManagerComponent(Component):
    gigachannel_manager: GigaChannelManager

    _rest_manager: RESTManager

    async def run(self):
        await self.use(ReporterComponent)

        config = self.session.config
        notifier = self.session.notifier

        libtorrent_component = await self.use(LibtorrentComponent)
        if not libtorrent_component:
            self._missed_dependency(LibtorrentComponent.__name__)

        download_manager = libtorrent_component.download_manager if libtorrent_component else None

        metadata_store_component = await self.use(MetadataStoreComponent)
        if not metadata_store_component:
            self._missed_dependency(MetadataStoreComponent.__name__)

        rest_component = await self.use(RESTComponent)
        if not rest_component:
            self._missed_dependency(RESTComponent.__name__)

        self._rest_manager = rest_component.rest_manager

        self.gigachannel_manager = GigaChannelManager(
            notifier=notifier, metadata_store=metadata_store_component.mds, download_manager=download_manager
        )
        if not config.gui_test_mode:
            self.gigachannel_manager.start()

        self._rest_manager.get_endpoint('channels').gigachannel_manager = self.gigachannel_manager
        self._rest_manager.get_endpoint('collections').gigachannel_manager = self.gigachannel_manager

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Gigachannel Manager...")
        self._rest_manager.get_endpoint('channels').gigachannel_manager = None
        self._rest_manager.get_endpoint('collections').gigachannel_manager = None

        await self.release(RESTComponent)

        if self.gigachannel_manager:
            await self.gigachannel_manager.shutdown()
