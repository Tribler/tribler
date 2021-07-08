from asyncio import get_event_loop

from tribler_common.sentry_reporter.sentry_reporter import SentryReporter

from tribler_core.modules.component import Component
from tribler_core.modules.exception_handler.exception_handler import CoreExceptionHandler
from tribler_core.utilities.unicode import hexlify


class ExceptionHandlerComponent(Component):
    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config
        trustchain_keypair = mediator.trustchain_keypair

        exception_handler = CoreExceptionHandler(self.logger, config=config.error_handling)
        get_event_loop().set_exception_handler(exception_handler.unhandled_error_observer)

        user_id_str = hexlify(trustchain_keypair.key.pk).encode('utf-8')
        SentryReporter.set_user(user_id_str)

        mediator.optional['exception_handler'] = exception_handler
