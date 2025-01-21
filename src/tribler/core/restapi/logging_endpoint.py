import logging
from logging.handlers import MemoryHandler

from aiohttp import web

from tribler.core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class LoggingEndpoint(RESTEndpoint):
    """
    This endpoint allows retrieval of the logs.
    """

    path = '/api/logging'

    def __init__(self) -> None:
        """
        Create a new logging endpoint.
        """
        super().__init__()

        self.base_handler = logging.getLogger().handlers[0]

        self.memory_logger = MemoryHandler(100000)
        logging.getLogger().addHandler(self.memory_logger)

        self.app.add_routes([web.get("", self.get_logs)])

    def get_logs(self, request: web.Request) -> RESTResponse:
        """
        Return the most recent logs.
        """
        return RESTResponse("\n".join(self.base_handler.format(r) for r in self.memory_logger.buffer))
