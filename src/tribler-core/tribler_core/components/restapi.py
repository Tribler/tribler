from abc import ABC
from typing import Optional, Set, Tuple

from tribler_common.simpledefs import STATE_START_API
from tribler_core.components.base import Component
from tribler_core.components.reporter import ReporterComponent
from tribler_core.exception_handler import CoreExceptionHandler
from tribler_core.restapi.rest_manager import ApiKeyMiddleware, RESTManager, error_middleware
from tribler_core.restapi.root_endpoint import RootEndpoint
from tribler_core.restapi.state_endpoint import StateEndpoint


class RestfulComponent(Component, ABC):
    _rest_manager: Optional[RESTManager] = None
    endpoint_attrs: Set[Tuple[str, str]]

    def __init__(self):
        super().__init__()
        self.endpoint_attrs = set()

    async def set_readable_status(self, readable_status):
        rest_component = await self.get_component(RESTComponent)
        if rest_component:
            state_endpoint: StateEndpoint = rest_component.rest_manager.get_endpoint('state')
            state_endpoint.readable_status = readable_status

    async def init_endpoints(self, endpoints, values, ipv8=None, ipv8_endpoints=()):
        rest_component = await self.get_component(RESTComponent)
        if not rest_component:
            return

        self._rest_manager = rest_component.rest_manager

        if ipv8 and ipv8_endpoints:
            ipv8_root_endpoint = self._rest_manager.get_endpoint('ipv8')
            if ipv8_root_endpoint:
                for path, endpoint in ipv8_root_endpoint.endpoints.items():
                    if path in ipv8_endpoints:
                        endpoint.initialize(ipv8)

        for endpoint_name in endpoints:
            endpoint = self._rest_manager.get_endpoint(endpoint_name)
            if endpoint:
                for attr_name, attr_value in values:
                    setattr(endpoint, attr_name, attr_value)
                    self.endpoint_attrs.add((endpoint_name, attr_name))

    def release_endpoints(self):
        if not self._rest_manager:
            return

        for endpoint_name, attr_name in self.endpoint_attrs:
            endpoint = self._rest_manager.get_endpoint(endpoint_name)
            setattr(endpoint, attr_name, None)

        self.release_component(RESTComponent)


class RESTComponent(Component):
    rest_manager: RESTManager

    async def run(self):
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

        rest_manager.get_endpoint('shutdown').connect_shutdown_callback(shutdown_event.set)
        rest_manager.get_endpoint('settings').tribler_config = config

        state_endpoint = rest_manager.get_endpoint('state')
        state_endpoint.connect_notifier(notifier)
        state_endpoint.readable_status = STATE_START_API

        events_endpoint = rest_manager.get_endpoint('events')
        events_endpoint.connect_notifier(notifier)

        debug_endpoint = rest_manager.get_endpoint('debug')
        log_dir = config.general.get_path_as_absolute('log_dir', config.state_dir)
        debug_endpoint.log_dir = log_dir
        debug_endpoint.state_dir = config.state_dir

        def report_callback(text_long, sentry_event):
            events_endpoint.on_tribler_exception(text_long, sentry_event,
                                                 config.error_handling.core_error_reporting_requires_user_consent)
            state_endpoint.on_tribler_exception(text_long, sentry_event)

        CoreExceptionHandler.report_callback = report_callback

        # We provide the REST API only after the essential endpoints (events, state and shutdown) and
        # the exception handler were initialized
        self.rest_manager = rest_manager

    async def shutdown(self):
        # TODO: disconnect notifier from endpoints
        CoreExceptionHandler.report_callback = None
        self.session.notifier.notify_shutdown_state("Shutting down API Manager...")
        await self.rest_manager.stop()
