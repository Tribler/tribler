from abc import ABC
from typing import Any, Dict, List, Set, Tuple

from ipv8_service import IPv8

from tribler_common.reported_error import ReportedError

from tribler_core.components.base import Component
from tribler_core.components.reporter.exception_handler import CoreExceptionHandler, default_core_exception_handler
from tribler_core.components.reporter.reporter_component import ReporterComponent
from tribler_core.components.restapi.rest.debug_endpoint import DebugEndpoint
from tribler_core.components.restapi.rest.events_endpoint import EventsEndpoint
from tribler_core.components.restapi.rest.rest_manager import ApiKeyMiddleware, RESTManager, error_middleware
from tribler_core.components.restapi.rest.root_endpoint import RootEndpoint


class RestfulComponent(Component, ABC):
    endpoint_attrs: Set[Tuple[str, str]]

    def __init__(self):
        super().__init__()
        self.endpoint_attrs = set()

    async def init_endpoints(self, endpoints: List[str], values: Dict[str, Any]):
        rest_component = await self.get_component(RESTComponent)
        if not rest_component:
            return

        for endpoint_name in endpoints:
            endpoint = rest_component.rest_manager.get_endpoint(endpoint_name)
            if endpoint:
                for attr_name, attr_value in values.items():
                    setattr(endpoint, attr_name, attr_value)
                    self.endpoint_attrs.add((endpoint_name, attr_name))

    async def init_ipv8_endpoints(self, ipv8: IPv8, endpoints: List[str]):
        rest_component = await self.get_component(RESTComponent)
        if not rest_component:
            return

        ipv8_root_endpoint = rest_component.rest_manager.get_endpoint('ipv8')
        if ipv8_root_endpoint:
            path_set = {'/' + name for name in endpoints}
            for path, endpoint in ipv8_root_endpoint.endpoints.items():
                if path in path_set:
                    endpoint.initialize(ipv8)

    async def run(self):
        await super().run()
        await self.get_component(ReporterComponent)

    async def shutdown(self):
        await super().shutdown()
        rest_component = await self.get_component(RESTComponent)
        if not rest_component:
            return

        for endpoint_name, attr_name in self.endpoint_attrs:
            endpoint = rest_component.rest_manager.get_endpoint(endpoint_name)
            if endpoint:
                setattr(endpoint, attr_name, None)


class RESTComponent(Component):
    rest_manager: RESTManager = None

    _events_endpoint: EventsEndpoint
    _state_endpoint: StateEndpoint
    _core_exception_handler: CoreExceptionHandler = default_core_exception_handler

    async def run(self):
        await super().run()
        await self.get_component(ReporterComponent)
        session = self.session
        config = session.config
        notifier = session.notifier
        shutdown_event = session.shutdown_event

        root_endpoint = RootEndpoint(config, middlewares=[ApiKeyMiddleware(config.api.key), error_middleware])
        rest_manager = RESTManager(config=config.api, root_endpoint=root_endpoint, state_dir=config.state_dir)
        # Unfortunately, AIOHTTP endpoints cannot be added after the app has been started.
        # On the other hand, we have to start the state endpoint from the beginning, to
        # communicate with the upgrader. Thus, we start the endpoints immediately and
        # then gradually connect them to their respective backends during the core start process.
        await rest_manager.start()
        self.rest_manager = rest_manager

        rest_manager.get_endpoint('shutdown').connect_shutdown_callback(shutdown_event.set)
        rest_manager.get_endpoint('settings').tribler_config = config

        self._events_endpoint = rest_manager.get_endpoint('events')
        assert self._events_endpoint is not None
        self._events_endpoint.connect_notifier(notifier)

        debug_endpoint: DebugEndpoint = rest_manager.get_endpoint('debug')
        assert debug_endpoint is not None
        log_dir = config.general.get_path_as_absolute('log_dir', config.state_dir)
        debug_endpoint.log_dir = log_dir
        debug_endpoint.state_dir = config.state_dir

        def report_callback(reported_error: ReportedError):
            self._events_endpoint.on_tribler_exception(reported_error)

        self._core_exception_handler.report_callback = report_callback

    async def shutdown(self):
        await super().shutdown()

        if self._core_exception_handler:
            self._core_exception_handler.report_callback = None

        if self.rest_manager:
            await self.rest_manager.stop()
