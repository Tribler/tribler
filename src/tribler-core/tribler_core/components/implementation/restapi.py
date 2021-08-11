from tribler_common.simpledefs import STATE_START_API

from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.exception_handler import CoreExceptionHandler
from tribler_core.components.interfaces.reporter import ReporterComponent
from tribler_core.restapi.rest_manager import ApiKeyMiddleware, RESTManager, error_middleware
from tribler_core.restapi.root_endpoint import RootEndpoint


class RESTComponentImp(RESTComponent):

    async def run(self):
        await self.use(ReporterComponent)
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
