from __future__ import annotations

import json
import logging
from typing import Dict, TYPE_CHECKING

from aiohttp import web

from tribler.core.components.restapi.rest.aiohttp_patch import patch_make_request
from tribler.core.utilities.async_group.async_group import AsyncGroup

if TYPE_CHECKING:
    from tribler.core.components.restapi.rest.events_endpoint import EventsEndpoint
    from ipv8.REST.root_endpoint import RootEndpoint as IPV8RootEndpoint

patch_make_request(web.Application)

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_REQUEST_ENTITY_TOO_LARGE = 413
HTTP_INTERNAL_SERVER_ERROR = 500

MAX_REQUEST_SIZE = 16 * 1024 ** 2  # 16 MB


class RESTEndpoint:
    path = ''

    def __init__(self, middlewares=(), client_max_size=MAX_REQUEST_SIZE):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.app = web.Application(middlewares=middlewares, client_max_size=client_max_size)
        self.endpoints: Dict[str, RESTEndpoint] = {}
        self.async_group = AsyncGroup()
        self.setup_routes()

        self._shutdown = False

    def setup_routes(self):
        pass

    def add_endpoint(self, prefix: str, endpoint: RESTEndpoint | EventsEndpoint | IPV8RootEndpoint):
        self.endpoints[prefix] = endpoint
        self.app.add_subapp(prefix, endpoint.app)

    async def shutdown(self):
        if self._shutdown:
            return
        self._shutdown = True

        shutdown_group = AsyncGroup()
        for endpoint in self.endpoints.values():
            if isinstance(endpoint, RESTEndpoint):
                shutdown_group.add_task(endpoint.shutdown())  # IPV8RootEndpoint doesn't have a shutdown method

        await shutdown_group.wait()
        await self.async_group.cancel()


class RESTResponse(web.Response):

    def __init__(self, body=None, headers=None, content_type=None, status=200, **kwargs):
        if not isinstance(status, int):
            status = getattr(status, 'status_code')
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
            content_type = 'application/json'
        super().__init__(body=body, headers=headers, content_type=content_type, status=status, **kwargs)


class RESTStreamResponse(web.StreamResponse):

    def __init__(self, headers=None, **kwargs):
        super().__init__(headers=headers, **kwargs)
