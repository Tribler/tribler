from tribler_core.components.base import Component
from tribler_core.components.libtorrent import LibtorrentComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.reporter import ReporterComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.components.gigachannel_manager.gigachannel_manager import GigaChannelManager
from tribler_core.restapi.rest_manager import RESTManager


class GigachannelManagerComponent(Component):
    gigachannel_manager: GigaChannelManager

    _rest_manager: RESTManager

    async def run(self):
        await self.get_component(ReporterComponent)

        config = self.session.config
        notifier = self.session.notifier

        libtorrent_component = await self.require_component(LibtorrentComponent)
        download_manager = libtorrent_component.download_manager if libtorrent_component else None

        metadata_store_component = await self.require_component(MetadataStoreComponent)
        rest_component = await self.require_component(RESTComponent)

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

        await self.release_component(RESTComponent)

        await self.gigachannel_manager.shutdown()
