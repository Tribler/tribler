from tribler_common.simpledefs import STATE_START_API
from tribler_core.modules.component import Component
from tribler_core.modules.exception_handler.exception_handler import CoreExceptionHandler
from tribler_core.restapi.rest_manager import ApiKeyMiddleware, RESTManager, error_middleware
from tribler_core.restapi.root_endpoint import RootEndpoint


class RESTComponent(Component):
    provided_futures = (RESTManager, )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_manager = None

    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config
        notifier = mediator.notifier
        shutdown_event = mediator.optional.get('shutdown_event', None)
        exception_handler = await mediator.awaitable_components.get(CoreExceptionHandler)

        root_endpoint = RootEndpoint(config, middlewares=[ApiKeyMiddleware(config.api.key), error_middleware])

        api_manager = RESTManager(config=config.api, root_endpoint=root_endpoint)
        # Unfortunately, AIOHTTP endpoints cannot be added after the app has been started.
        # On the other hand, we have to start the state endpoint from the beginning, to
        # communicate with the upgrader. Thus, we start the endpoints immediately and
        # then gradually connect them to their respective backends during the core start process.
        await api_manager.start()
        api_manager.get_endpoint('settings').tribler_config = config

        state_endpoint = api_manager.get_endpoint('state')
        state_endpoint.connect_notifier(notifier)
        state_endpoint.readable_status = STATE_START_API
        if exception_handler:
            exception_handler.events_endpoint = api_manager.get_endpoint('events')
            exception_handler.state_endpoint = state_endpoint

        api_manager.get_endpoint('events').connect_notifier(notifier)
        if shutdown_event:
            api_manager.get_endpoint('shutdown').connect_shutdown_callback(shutdown_event.set)

        self.api_manager = api_manager
        mediator.awaitable_components[RESTManager].set_result(api_manager)

    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down API Manager...")
        await self.api_manager.stop()
        await super().shutdown(mediator)
