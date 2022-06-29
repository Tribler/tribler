from tribler.core.components.component import Component
from tribler.core.components.gigachannel_manager.gigachannel_manager import GigaChannelManager
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.metadata_store.metadata_store_component import MetadataStoreComponent


class GigachannelManagerComponent(Component):
    gigachannel_manager: GigaChannelManager = None

    async def run(self):
        await super().run()

        config = self.session.config
        notifier = self.session.notifier

        libtorrent_component = await self.require_component(LibtorrentComponent)
        download_manager = libtorrent_component.download_manager if libtorrent_component else None

        metadata_store_component = await self.require_component(MetadataStoreComponent)

        self.gigachannel_manager = GigaChannelManager(
            notifier=notifier, metadata_store=metadata_store_component.mds, download_manager=download_manager
        )
        if not config.gui_test_mode:
            self.gigachannel_manager.start()

    async def shutdown(self):
        await super().shutdown()
        if self.gigachannel_manager:
            await self.gigachannel_manager.shutdown()
