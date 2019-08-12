from __future__ import absolute_import

import logging
from asyncio import ensure_future, get_event_loop

from aiohttp import web

from Tribler.Core.Modules.process_checker import ProcessChecker
from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class ShutdownEndpoint(RESTEndpoint):
    """
    With this endpoint you can shutdown Tribler.
    """

    def __init__(self, session):
        super(ShutdownEndpoint, self).__init__(session)
        self.process_checker = ProcessChecker()

    def setup_routes(self):
        self.app.add_routes([web.put('', self.shutdown)])

    async def shutdown(self, request):
        """
        .. http:put:: /shutdown

        A PUT request to this endpoint will shutdown Tribler.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/shutdown

            **Example response**:

            .. sourcecode:: javascript

                {
                    "shutdown": True
                }
        """

        async def shutdown():
            try:
                await self.session.shutdown()
            except Exception as e:
                self._logger.error(e)

            self.process_checker.remove_lock_file()
            # Flush the logs to the file before exiting
            for handler in logging.getLogger().handlers:
                handler.flush()
            get_event_loop().stop()

        ensure_future(shutdown())
        return RESTResponse({"shutdown": True})
