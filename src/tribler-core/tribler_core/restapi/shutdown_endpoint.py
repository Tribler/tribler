import logging
from asyncio import ensure_future, get_event_loop

from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Boolean

from tribler_core.modules.process_checker import ProcessChecker
from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class ShutdownEndpoint(RESTEndpoint):
    """
    With this endpoint you can shutdown Tribler.
    """

    def __init__(self, session):
        super(ShutdownEndpoint, self).__init__(session)
        self.process_checker = ProcessChecker()

    def setup_routes(self):
        self.app.add_routes([web.put('', self.shutdown)])

    @docs(
        tags=["General"],
        summary="Shutdown Tribler.",
        responses={
            200: {
                "schema": schema(TriblerShutdownResponse={
                    'shutdown': Boolean
                })
            }
        }
    )
    async def shutdown(self, request):
        async def shutdown():
            try:
                keep_loop_running = await self.session.shutdown()
            except Exception as e:
                self._logger.error(e)
                keep_loop_running = False

            self.process_checker.remove_lock_file()
            # Flush the logs to the file before exiting
            for handler in logging.getLogger().handlers:
                handler.flush()
            if not keep_loop_running:
                get_event_loop().stop()

        ensure_future(shutdown())
        return RESTResponse({"shutdown": True})
