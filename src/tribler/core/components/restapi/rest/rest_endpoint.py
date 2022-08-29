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

    def bad_request(self, msg: str, status: int = HTTP_BAD_REQUEST, exc_info=None, **kwargs):
        logger_msg = msg
        if kwargs:
            logger_msg += f', context: {kwargs!r}'
        self._logger.error(logger_msg, exc_info=exc_info)
        result = {"error": msg}
        if kwargs:
            result["context"] = kwargs
        return RESTResponse(result, status=status)

    def not_found(self, msg, **kwargs):
        return self.bad_request(msg, status=HTTP_NOT_FOUND, **kwargs)

    def internal_error(self, exc: Exception = None, msg: str = None, **kwargs):
        if msg is None and exc is not None:
            msg = f'{exc.__class__.__name__}: {exc}'
        return self.bad_request(msg, status=HTTP_INTERNAL_SERVER_ERROR, exc_info=exc, **kwargs)


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
