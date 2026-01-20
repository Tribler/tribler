import logging
from logging.handlers import MemoryHandler

from aiohttp import web

from tribler.core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class RotatingMemoryHandler(MemoryHandler):
    """
    A custom MemoryHandler flusher. Instead of delegating to the ``target`` and flushing the ``buffer``, simply keep
    the last ``capacity`` records in the buffer.
    """

    def flush(self) -> None:
        """
        This is called when our buffer is at capacity and needs to be flushed.
        We get the handler lock and rotate the buffer.
        """
        self.acquire()
        try:
            self.buffer = self.buffer[-self.capacity:]
        finally:
            self.release()


class LoggingEndpoint(RESTEndpoint):
    """
    This endpoint allows retrieval of the logs.
    """

    path = "/api/logging"

    def __init__(self) -> None:
        """
        Create a new logging endpoint.
        """
        super().__init__()

        self.base_handler = logging.getLogger().handlers[0]

        self.memory_logger = RotatingMemoryHandler(400)
        logging.getLogger().addHandler(self.memory_logger)

        self.app.add_routes([web.get("", self.get_logs)])

    async def get_logs(self, request: web.Request) -> RESTResponse:
        """
        Return the most recent logs.
        """
        return RESTResponse("\n".join(self.base_handler.format(r) for r in self.memory_logger.buffer))
