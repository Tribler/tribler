from ipv8.messaging.anonymization.community import TunnelCommunity

from tribler_common.simpledefs import STATE_LOAD_CHECKPOINTS, STATE_READABLE_STARTED, STATE_START_LIBTORRENT

from tribler_core.modules.component import Component
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.session import Mediator


class LibtorrentComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.download_manager = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)

        config = mediator.config
        notifier = mediator.notifier
        trustchain_keypair = mediator.trustchain_keypair

        payout_manager = mediator.optional.get('payout_manager', None)
        api_manager = mediator.optional.get('api_manager', None)

        if api_manager:
            api_manager.get_endpoint('state').readable_status = STATE_START_LIBTORRENT

        download_manager = DownloadManager(config=config.libtorrent,
                                           state_dir=config.state_dir,
                                           notifier=notifier,
                                           peer_mid=trustchain_keypair.key_to_hash(),
                                           download_defaults=config.download_defaults,
                                           payout_manager=payout_manager,
                                           bootstrap_infohash=config.bootstrap.infohash,
                                           dummy_mode=config.core_test_mode)

        download_manager.initialize()
        ipv8 = await mediator.optional['ipv8']
        download_manager.tunnel_community = ipv8.get_overlay(TunnelCommunity)

        if api_manager:
            api_manager.get_endpoint('state').readable_status = STATE_LOAD_CHECKPOINTS

        await download_manager.load_checkpoints()

        if api_manager:
            api_manager.get_endpoint('createtorrent').download_manager = download_manager
            api_manager.get_endpoint('libtorrent').download_manager = download_manager
            api_manager.get_endpoint('torrentinfo').download_manager = download_manager
            api_manager.get_endpoint('downloads').download_manager = download_manager
            api_manager.get_endpoint('channels').download_manager = download_manager
            api_manager.get_endpoint('collections').download_manager = download_manager

        if config.core_test_mode:
            uri = "magnet:?xt=urn:btih:0000000000000000000000000000000000000000"
            await download_manager.start_download_from_uri(uri)

        if api_manager and download_manager:
            api_manager.get_endpoint('settings').download_manager = download_manager

        if api_manager:
            api_manager.get_endpoint('state').readable_status = STATE_READABLE_STARTED

        self.download_manager = download_manager
        mediator.optional['download_manager'] = download_manager

    async def shutdown(self, mediator):
        await super().shutdown(mediator)

        self.download_manager.stop_download_states_callback()
        await self.download_manager.shutdown()
