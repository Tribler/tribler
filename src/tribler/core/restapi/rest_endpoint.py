from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Dict

from aiohttp import web
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
    """
    The base class for all Tribler REST endpoints.
    """

    path: str

    def __init__(self, middlewares: tuple = (), client_max_size: int = MAX_REQUEST_SIZE) -> None:
        """
        Create a new REST endpoint.
        """
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.app = web.Application(middlewares=middlewares, client_max_size=client_max_size)


class RootEndpoint(RESTEndpoint):
    """
    Create a new root endpoint.

    Essentially, this is the same as any other REST endpoint, but it is supposed to be the top in the hierarchy.
    """

    def __init__(self, middlewares: tuple = (), client_max_size: int = MAX_REQUEST_SIZE) -> None:
        """
        Create a new root endpoint.
        """
        super().__init__(middlewares, client_max_size)
        self.endpoints: Dict[str, RESTEndpoint] = {}

    def add_endpoint(self, prefix: str, endpoint: RESTEndpoint | IPV8RootEndpoint) -> None:
        """
        Add an endpoint to this root endpoint.
        """
        self.endpoints[prefix] = endpoint
        self.app.add_subapp(prefix, endpoint.app)


class RESTResponse(web.Response):
    """
    A Tribler response for web requests.

    JSON-compatible response bodies are automatically converted to JSON type.
    """

    def __init__(self, body: dict | list | bytes | str | None = None, headers: dict | None = None,
                 content_type: str | None = None, status: int = 200, **kwargs) -> None:
        """
        Create a new rest response.
        """
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
            content_type = "application/json"
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
            "message": f"{exception.__class__.__name__}: {exception!s}"
        }
    }, status=HTTP_INTERNAL_SERVER_ERROR)
