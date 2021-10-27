import json
import logging

from aiohttp import web

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500


class RESTEndpoint:

    def __init__(self, middlewares=()):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.app = web.Application(middlewares=middlewares, client_max_size=2*1024**2)
        self.endpoints = {}
        self.setup_routes()

    def setup_routes(self):
        pass

    def add_endpoint(self, prefix, endpoint):
        self.endpoints[prefix] = endpoint
        self.app.add_subapp(prefix, endpoint.app)


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
