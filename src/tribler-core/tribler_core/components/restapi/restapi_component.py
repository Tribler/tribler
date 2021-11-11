

from ipv8.REST.root_endpoint import RootEndpoint as IPV8RootEndpoint

from tribler_common.reported_error import ReportedError

from tribler_core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler_core.components.bandwidth_accounting.restapi.bandwidth_endpoint import BandwidthEndpoint
from tribler_core.components.base import Component
from tribler_core.components.reporter.exception_handler import CoreExceptionHandler, default_core_exception_handler
from tribler_core.components.gigachannel.gigachannel_component import GigaChannelComponent
from tribler_core.components.gigachannel_manager.gigachannel_manager_component import GigachannelManagerComponent
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.libtorrent.restapi.create_torrent_endpoint import CreateTorrentEndpoint
from tribler_core.components.libtorrent.restapi.downloads_endpoint import DownloadsEndpoint
from tribler_core.components.libtorrent.restapi.libtorrent_endpoint import LibTorrentEndpoint
from tribler_core.components.libtorrent.restapi.torrentinfo_endpoint import TorrentInfoEndpoint
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.metadata_store.restapi.channels_endpoint import ChannelsEndpoint
from tribler_core.components.metadata_store.restapi.metadata_endpoint import MetadataEndpoint
from tribler_core.components.metadata_store.restapi.remote_query_endpoint import RemoteQueryEndpoint
from tribler_core.components.metadata_store.restapi.search_endpoint import SearchEndpoint
from tribler_core.components.reporter.exception_handler import CoreExceptionHandler
from tribler_core.components.reporter.reporter_component import ReporterComponent
from tribler_core.components.resource_monitor.resource_monitor_component import ResourceMonitorComponent
from tribler_core.components.restapi.rest.debug_endpoint import DebugEndpoint
from tribler_core.components.restapi.rest.events_endpoint import EventsEndpoint
from tribler_core.components.restapi.rest.rest_manager import ApiKeyMiddleware, RESTManager, error_middleware
from tribler_core.components.restapi.rest.root_endpoint import RootEndpoint
from tribler_core.components.restapi.rest.settings_endpoint import SettingsEndpoint
from tribler_core.components.restapi.rest.shutdown_endpoint import ShutdownEndpoint
from tribler_core.components.restapi.rest.statistics_endpoint import StatisticsEndpoint
from tribler_core.components.restapi.rest.trustview_endpoint import TrustViewEndpoint
from tribler_core.components.tag.restapi.tags_endpoint import TagsEndpoint
from tribler_core.components.tag.tag_component import TagComponent
from tribler_core.components.torrent_checker.torrent_checker_component import TorrentCheckerComponent
from tribler_core.components.tunnel.tunnel_component import TunnelsComponent


class RESTComponent(Component):
    rest_manager: RESTManager = None

    _events_endpoint: EventsEndpoint
    _core_exception_handler: CoreExceptionHandler = default_core_exception_handler

    async def run(self):
        await super().run()
        await self.get_component(ReporterComponent)
        session = self.session
        config = session.config
        notifier = session.notifier
        shutdown_event = session.shutdown_event

        root_endpoint = RootEndpoint(middlewares=[ApiKeyMiddleware(config.api.key), error_middleware])
        add = root_endpoint.add_endpoint

        log_dir = config.general.get_path_as_absolute('log_dir', config.state_dir)
        metadata_store_component = await self.get_component(MetadataStoreComponent)

        # fmt: off
        ipv8_component                 = await self.require_component(Ipv8Component)
        libtorrent_component           = await self.require_component(LibtorrentComponent)
        resource_monitor_component     = await self.require_component(ResourceMonitorComponent)
        bandwidth_accounting_component = await self.require_component(BandwidthAccountingComponent)
        gigachannel_component          = await self.require_component(GigaChannelComponent)
        tag_component                  = await self.require_component(TagComponent)

        tunnel_component               = await self.get_component(TunnelsComponent)
        torrent_checker_component      = await self.get_component(TorrentCheckerComponent)
        gigachannel_manager_component  = await self.get_component(GigachannelManagerComponent)

        torrent_checker = torrent_checker_component.torrent_checker if torrent_checker_component else None
        tunnel_community = tunnel_component.community if tunnel_component else None
        gigachannel_manager = gigachannel_manager_component.gigachannel_manager if gigachannel_manager_component else None

        add('/events',        EventsEndpoint(notifier))
        add('/settings',      SettingsEndpoint(config,
                                               download_manager=libtorrent_component.download_manager))
        add('/shutdown',      ShutdownEndpoint(shutdown_event.set))
        add('/debug',         DebugEndpoint(config.state_dir,
                                            log_dir,
                                            tunnel_community=tunnel_community,
                                            resource_monitor=resource_monitor_component.resource_monitor))
        add('/bandwidth',     BandwidthEndpoint(bandwidth_accounting_component.community))
        add('/trustview',     TrustViewEndpoint(bandwidth_accounting_component.database))
        add('/downloads',     DownloadsEndpoint(libtorrent_component.download_manager,
                                                metadata_store=metadata_store_component.mds,
                                                tunnel_community=tunnel_community)),
        add('/createtorrent', CreateTorrentEndpoint(libtorrent_component.download_manager))
        add('/statistics',    StatisticsEndpoint(ipv8=ipv8_component.ipv8,
                                                 metadata_store=metadata_store_component.mds))
        add('/libtorrent',    LibTorrentEndpoint(libtorrent_component.download_manager))
        add('/torrentinfo',   TorrentInfoEndpoint(libtorrent_component.download_manager))
        add('/metadata',      MetadataEndpoint(torrent_checker,
                                               metadata_store_component.mds,
                                               tags_db=tag_component.tags_db))
        add('/channels',      ChannelsEndpoint(libtorrent_component.download_manager,
                                               gigachannel_manager,
                                               gigachannel_component.community,
                                               metadata_store_component.mds,
                                               tags_db=tag_component.tags_db))
        add('/collections',   ChannelsEndpoint(libtorrent_component.download_manager,
                                               gigachannel_manager,
                                               gigachannel_component.community,
                                               metadata_store_component.mds,
                                               tags_db=tag_component.tags_db))
        add('/search',        SearchEndpoint(metadata_store_component.mds,
                                             tags_db=tag_component.tags_db))
        add('/remote_query',  RemoteQueryEndpoint(gigachannel_component.community,
                                                  metadata_store_component.mds))
        add('/tags',          TagsEndpoint(tag_component.tags_db, tag_component.community))

        ipv8_root_endpoint = IPV8RootEndpoint()
        for _, endpoint in ipv8_root_endpoint.endpoints.items():
            endpoint.initialize(ipv8_component.ipv8)
        add('/ipv8', ipv8_root_endpoint),
        # fmt: on

        # ACHTUNG!
        # AIOHTTP endpoints cannot be added after the app has been started!
        rest_manager = RESTManager(config=config.api, root_endpoint=root_endpoint, state_dir=config.state_dir)
        await rest_manager.start()
        self.rest_manager = rest_manager

        def report_callback(reported_error: ReportedError):
            self._events_endpoint.on_tribler_exception(reported_error)

        self._core_exception_handler.report_callback = report_callback

    async def shutdown(self):
        await super().shutdown()

        if self._core_exception_handler:
            self._core_exception_handler.report_callback = None

        if self.rest_manager:
            await self.rest_manager.stop()
