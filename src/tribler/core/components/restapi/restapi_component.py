from itertools import chain
from typing import Type

from ipv8.REST.root_endpoint import RootEndpoint as IPV8RootEndpoint

from tribler.core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler.core.components.bandwidth_accounting.restapi.bandwidth_endpoint import BandwidthEndpoint
from tribler.core.components.component import Component
from tribler.core.components.database.database_component import DatabaseComponent
from tribler.core.components.exceptions import NoneComponent
from tribler.core.components.gigachannel.gigachannel_component import GigaChannelComponent
from tribler.core.components.gigachannel_manager.gigachannel_manager_component import GigachannelManagerComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.knowledge.knowledge_component import KnowledgeComponent
from tribler.core.components.knowledge.restapi.knowledge_endpoint import KnowledgeEndpoint
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.libtorrent.restapi.create_torrent_endpoint import CreateTorrentEndpoint
from tribler.core.components.libtorrent.restapi.downloads_endpoint import DownloadsEndpoint
from tribler.core.components.libtorrent.restapi.libtorrent_endpoint import LibTorrentEndpoint
from tribler.core.components.libtorrent.restapi.torrentinfo_endpoint import TorrentInfoEndpoint
from tribler.core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler.core.components.metadata_store.restapi.channels_endpoint import ChannelsEndpoint
from tribler.core.components.metadata_store.restapi.metadata_endpoint import MetadataEndpoint
from tribler.core.components.metadata_store.restapi.remote_query_endpoint import RemoteQueryEndpoint
from tribler.core.components.metadata_store.restapi.search_endpoint import SearchEndpoint
from tribler.core.components.reporter.exception_handler import CoreExceptionHandler, default_core_exception_handler
from tribler.core.components.reporter.reported_error import ReportedError
from tribler.core.components.reporter.reporter_component import ReporterComponent
from tribler.core.components.resource_monitor.resource_monitor_component import ResourceMonitorComponent
from tribler.core.components.restapi.rest.debug_endpoint import DebugEndpoint
from tribler.core.components.restapi.rest.events_endpoint import EventsEndpoint
from tribler.core.components.restapi.rest.rest_endpoint import RESTEndpoint
from tribler.core.components.restapi.rest.rest_manager import ApiKeyMiddleware, RESTManager, error_middleware
from tribler.core.components.restapi.rest.root_endpoint import RootEndpoint
from tribler.core.components.restapi.rest.settings_endpoint import SettingsEndpoint
from tribler.core.components.restapi.rest.shutdown_endpoint import ShutdownEndpoint
from tribler.core.components.restapi.rest.statistics_endpoint import StatisticsEndpoint
from tribler.core.components.restapi.rest.trustview_endpoint import TrustViewEndpoint
from tribler.core.components.torrent_checker.torrent_checker_component import TorrentCheckerComponent
from tribler.core.components.tunnel.tunnel_component import TunnelsComponent
from tribler.core.utilities.unicode import hexlify


class RESTComponent(Component):
    rest_manager: RESTManager = None
    root_endpoint: RootEndpoint = None
    swagger_doc_extraction_mode: bool = False

    _events_endpoint: EventsEndpoint
    _core_exception_handler: CoreExceptionHandler = default_core_exception_handler

    def maybe_add(self, endpoint_cls: Type[RESTEndpoint], *args, **kwargs):
        """ Add the corresponding endpoint to the path in case there are no `NoneComponent`
        in *args or **kwargs
        """
        self.logger.info(f'Adding: "{endpoint_cls.path}"...')
        arguments_chain = chain(args, kwargs.values())
        need_to_skip = any(isinstance(arg, NoneComponent) for arg in arguments_chain)
        if need_to_skip and not self.swagger_doc_extraction_mode:
            self.logger.warning("Skipped")
            return

        self.root_endpoint.add_endpoint(endpoint_cls.path, endpoint_cls(*args, **kwargs))
        self.logger.info("OK")

    async def run(self):
        await super().run()
        await self.get_component(ReporterComponent)
        session = self.session
        config = session.config
        notifier = session.notifier
        shutdown_event = session.shutdown_event

        log_dir = config.general.get_path_as_absolute('log_dir', config.state_dir)
        metadata_store_component = await self.maybe_component(MetadataStoreComponent)

        key_component = await self.maybe_component(KeyComponent)
        ipv8_component = await self.maybe_component(Ipv8Component)
        libtorrent_component = await self.maybe_component(LibtorrentComponent)
        resource_monitor_component = await self.maybe_component(ResourceMonitorComponent)
        bandwidth_accounting_component = await self.maybe_component(BandwidthAccountingComponent)
        gigachannel_component = await self.maybe_component(GigaChannelComponent)
        knowledge_component = await self.maybe_component(KnowledgeComponent)
        tunnel_component = await self.maybe_component(TunnelsComponent)
        torrent_checker_component = await self.maybe_component(TorrentCheckerComponent)
        gigachannel_manager_component = await self.maybe_component(GigachannelManagerComponent)
        db_component = await self.maybe_component(DatabaseComponent)

        public_key = key_component.primary_key.key.pk if not isinstance(key_component, NoneComponent) else b''
        self._events_endpoint = EventsEndpoint(notifier, public_key=hexlify(public_key))
        self.root_endpoint = RootEndpoint(middlewares=[ApiKeyMiddleware(config.api.key), error_middleware])

        torrent_checker = None if config.gui_test_mode else torrent_checker_component.torrent_checker
        tunnel_community = None if config.gui_test_mode else tunnel_component.community
        gigachannel_manager = None if config.gui_test_mode else gigachannel_manager_component.gigachannel_manager

        # add endpoints
        self.root_endpoint.add_endpoint(EventsEndpoint.path, self._events_endpoint)
        self.maybe_add(SettingsEndpoint, config, download_manager=libtorrent_component.download_manager)
        self.maybe_add(ShutdownEndpoint, shutdown_event.set)
        self.maybe_add(DebugEndpoint, config.state_dir, log_dir, tunnel_community=tunnel_community,
                       resource_monitor=resource_monitor_component.resource_monitor,
                       core_exception_handler=self._core_exception_handler)
        self.maybe_add(BandwidthEndpoint, bandwidth_accounting_component.community)
        self.maybe_add(TrustViewEndpoint, bandwidth_accounting_component.database)
        self.maybe_add(DownloadsEndpoint, libtorrent_component.download_manager,
                       metadata_store=metadata_store_component.mds, tunnel_community=tunnel_community)
        self.maybe_add(CreateTorrentEndpoint, libtorrent_component.download_manager)
        self.maybe_add(StatisticsEndpoint, ipv8=ipv8_component.ipv8, metadata_store=metadata_store_component.mds)
        self.maybe_add(LibTorrentEndpoint, libtorrent_component.download_manager)
        self.maybe_add(TorrentInfoEndpoint, libtorrent_component.download_manager)
        self.maybe_add(MetadataEndpoint, torrent_checker, metadata_store_component.mds,
                       tribler_db=db_component.db,
                       tag_rules_processor=knowledge_component.rules_processor)
        self.maybe_add(ChannelsEndpoint, libtorrent_component.download_manager, gigachannel_manager,
                       gigachannel_component.community, metadata_store_component.mds,
                       tribler_db=db_component.db,
                       tag_rules_processor=knowledge_component.rules_processor)
        self.maybe_add(SearchEndpoint, metadata_store_component.mds, tribler_db=db_component.db)
        self.maybe_add(RemoteQueryEndpoint, gigachannel_component.community, metadata_store_component.mds)
        self.maybe_add(KnowledgeEndpoint, db=db_component.db, community=knowledge_component.community)

        if not isinstance(ipv8_component, NoneComponent):
            ipv8_root_endpoint = IPV8RootEndpoint()
            for _, endpoint in ipv8_root_endpoint.endpoints.items():
                endpoint.initialize(ipv8_component.ipv8)
            self.root_endpoint.add_endpoint('/ipv8', ipv8_root_endpoint)

        # Note: AIOHTTP endpoints cannot be added after the app has been started!
        rest_manager = RESTManager(config=config.api, root_endpoint=self.root_endpoint, state_dir=config.state_dir)
        await rest_manager.start()
        self.rest_manager = rest_manager

        def report_callback(reported_error: ReportedError):
            self._events_endpoint.on_tribler_exception(reported_error)

        self._core_exception_handler.report_callback = report_callback
        # Reraise the unreported error, if there is one
        if self._core_exception_handler.unreported_error:
            report_callback(self._core_exception_handler.unreported_error)
            self._core_exception_handler.unreported_error = None

    async def shutdown(self):
        await super().shutdown()

        if self.root_endpoint:
            await self.root_endpoint.shutdown()

        if self._core_exception_handler:
            self._core_exception_handler.report_callback = None

        if self.rest_manager:
            await self.rest_manager.stop()
