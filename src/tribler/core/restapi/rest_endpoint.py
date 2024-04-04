from __future__ import annotations

import json
import logging
from typing import Dict, TYPE_CHECKING

from aiohttp import web
from aiohttp.web_request import Request
from ipv8.taskmanager import TaskManager

if TYPE_CHECKING:
    from ipv8.REST.root_endpoint import RootEndpoint as IPV8RootEndpoint


HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_REQUEST_ENTITY_TOO_LARGE = 413
HTTP_INTERNAL_SERVER_ERROR = 500

MAX_REQUEST_SIZE = 16 * 1024 ** 2  # 16 MB


class RESTEndpoint(TaskManager):
    path: str

    def __init__(self, middlewares=(), client_max_size=MAX_REQUEST_SIZE) -> None:
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.app = web.Application(middlewares=middlewares, client_max_size=client_max_size)


class RootEndpoint(RESTEndpoint):

    def __init__(self, middlewares=(), client_max_size=MAX_REQUEST_SIZE) -> None:
        super().__init__(middlewares, client_max_size)
        self.endpoints: Dict[str, RESTEndpoint] = {}

    def add_endpoint(self, prefix: str, endpoint: RESTEndpoint | IPV8RootEndpoint) -> None:
        self.endpoints[prefix] = endpoint
        self.app.add_subapp(prefix, endpoint.app)


class RESTResponse(web.Response):

    def __init__(self, body=None, headers=None, content_type=None, status=200, **kwargs) -> None:
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
            content_type = 'application/json'
        super().__init__(body=body, headers=headers, content_type=content_type, status=status, **kwargs)


def return_handled_exception(exception: Exception) -> RESTResponse:
    """
    Create a RESTResponse that tells the use that an exception is handled.

    :param request: the request that encountered the exception
    :param exception: the handled exception
    :return: JSON dictionary describing the exception
    """
    return RESTResponse({
        "error": {
            "handled": True,
            "code": exception.__class__.__name__,
            "message": str(exception)
        }
    }, status=HTTP_INTERNAL_SERVER_ERROR)
