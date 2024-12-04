from __future__ import annotations

import logging
import ssl
import traceback
from asyncio.base_events import Server
from functools import wraps
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable, Generic, TypeVar, cast

from aiohttp import tcp_helpers, web, web_protocol
from aiohttp.web_exceptions import HTTPNotFound, HTTPRequestEntityTooLarge
from aiohttp_apispec import AiohttpApiSpec
from apispec.core import VALID_METHODS_OPENAPI_V2

from tribler.core.restapi.rest_endpoint import (
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    HTTP_REQUEST_ENTITY_TOO_LARGE,
    HTTP_UNAUTHORIZED,
    RESTEndpoint,
    RESTResponse,
    RootEndpoint,
)

if TYPE_CHECKING:
    import asyncio

    from aiohttp.abc import Request

    from tribler.tribler_config import TriblerConfigManager

    ComponentsType = TypeVar("ComponentsType", bound=tuple[type])

    class TriblerRequest(Request, Generic[ComponentsType]):
        """
        A request that guarantees that the given components are not None in its ``context`` attribute.
        """

        context: ComponentsType

logger = logging.getLogger(__name__)
RESTEndpointType = TypeVar("RESTEndpointType", bound=RESTEndpoint)


@wraps(tcp_helpers.tcp_keepalive)
def wrap_tcp_keepalive(transport: asyncio.Transport) -> None:
    """
    A wrapper around aiohttp's tcp_keepalive that catches OSError 22 instances.

    See https://github.com/Tribler/tribler/issues/6429
    """
    try:
         wrap_tcp_keepalive.__wrapped__(transport)
    except OSError as e:
        logger.warning("Setting tcp_keepalive on aiohttp socket failed!")
        if e.errno != 22:
            raise

web_protocol.tcp_keepalive = wrap_tcp_keepalive

@web.middleware
class ApiKeyMiddleware:
    """
    Middleware to check if REST requests include an API key.

    The key can be in:

    - The ``X-Api-Key`` header.
    - The ``apikey`` query parameter.
    - The ``api_key`` cookie.
    """

    def __init__(self, api_key: str) -> None:
        """
        Initialize the middleware with the given API key.
        """
        self.api_key = api_key

    async def __call__(self, request: Request, handler: Callable[[Request], Awaitable[RESTResponse]]) -> RESTResponse:
        """
        Call this middleware.
        """
        if self.authenticate(request):
            return await handler(request)
        return RESTResponse({"error": {
            "handled": True,
            "message": "Unauthorized access"
        }}, status=HTTP_UNAUTHORIZED)

    def authenticate(self, request: Request) -> bool:
        """
        Is the given request authenticated using an API key.
        """
        if any(request.path.startswith(path) for path in ["/docs", "/static", "/ui"]):
            return True
        # The api key can either be in the headers or as part of the url query
        api_key = request.headers.get("X-Api-Key") or request.query.get("key") or request.cookies.get("api_key")
        expected_api_key = self.api_key
        return not expected_api_key or expected_api_key == api_key


@web.middleware
async def error_middleware(request: Request, handler: Callable[[Request], Awaitable[RESTResponse]]) -> RESTResponse:
    """
    Middleware to return nicely-formatted errors when common exceptions occur.
    """
    try:
        response = await handler(request)
    except ConnectionResetError:
        # A client closes the connection. It is not the Core error, nothing to handle or report this.
        # We cannot return response, as the connection is already closed, so we just propagate the exception
        # without reporting it to Sentry. The exception will be printed to the log by aiohttp.server.log_exception()
        raise
    except HTTPNotFound:
        return RESTResponse({"error": {
            "handled": True,
            "message": f"Could not find {request.path}"
        }}, status=HTTP_NOT_FOUND)
    except HTTPRequestEntityTooLarge as http_error:
        return RESTResponse({"error": {
            "handled": True,
            "message": http_error.text,
        }}, status=HTTP_REQUEST_ENTITY_TOO_LARGE)
    except Exception:
        full_exception = traceback.format_exc()

        return RESTResponse({"error": {
            "handled": False,
            "message": str(full_exception)
        }}, status=HTTP_INTERNAL_SERVER_ERROR)
    return response


@web.middleware
async def ui_middleware(request: Request, handler: Callable[[Request], Awaitable[RESTResponse]]) -> RESTResponse:
    """
    Forward request to a unknown pathname to /ui.
    This enables the GUI to request e.g. /index.html instead of using /ui/index.html.
    """
    if not any(request.path.startswith(path) for path in ["/docs", "/static", "/ui", "/api"]):
        raise web.HTTPFound('/ui' + request.rel_url.path)
    return await handler(request)


@web.middleware
async def required_components_middleware(request: Request,
                                         handler: Callable[[Request], Awaitable[RESTResponse]]) -> RESTResponse:
    """
    Read a handler's required components and return HTTP_NOT_FOUND if they have not been set (yet).
    """
    source_handler = handler
    while hasattr(source_handler, "__wrapped__"):
        source_handler = source_handler.__wrapped__
    if hasattr(source_handler, "__self__") and hasattr(source_handler.__self__, "required_components"):
        comps = [getattr(source_handler.__self__, name) for name in source_handler.__self__.required_components]
        if any(comp is None for comp in comps):
            return RESTResponse({"error": {
                "handled": True,
                "message": f"Required components not initialized to serve {request.path}"
            }}, status=HTTP_NOT_FOUND)
        request.context = comps
    return await handler(request)


class RESTManager:
    """
    This class is responsible for managing the startup and closing of the Tribler HTTP API.
    """

    def __init__(self, config: TriblerConfigManager, shutdown_timeout: int = 1) -> None:
        """
        Create a new REST manager.
        """
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.root_endpoint = RootEndpoint(middlewares=(ui_middleware, ApiKeyMiddleware(config.get("api/key")),
                                                       error_middleware, required_components_middleware))
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None
        self.site_https: web.TCPSite | None = None
        self.config = config
        self.state_dir = config.get("state_dir")

        self.http_host = self.config.get("api/http_host")
        self.https_host = self.config.get("api/https_host")
        self.shutdown_timeout = shutdown_timeout

    def add_endpoint(self, endpoint: RESTEndpointType) -> RESTEndpointType:
        """
        Add a REST endpoint to the root endpoint.
        """
        self.root_endpoint.add_endpoint(endpoint.path, endpoint)
        return endpoint

    def get_endpoint(self, name: str) -> RESTEndpoint:
        """
        Get an endpoint by its name, including the first forward slash.
        """
        return self.root_endpoint.endpoints.get(name)

    def get_api_port(self) -> int | None:
        """
        Get the API port of the currently running server.
        """
        if self.site:
            return cast(Server, self.site._server).sockets[0].getsockname()[1]  # noqa: SLF001
        return None

    async def start(self) -> None:
        """
        Starts the HTTP API with the listen port as specified in the session configuration.
        """
        self._logger.info("Starting RESTManager...")
        try:
            v = version("tribler")
        except PackageNotFoundError:
            v = "git"

        # Not using setup_aiohttp_apispec here, as we need access to the APISpec to set the security scheme
        aiohttp_apispec = AiohttpApiSpec(
            url="/docs/swagger.json",
            app=self.root_endpoint.app,
            title="Tribler REST API documentation",
            version=f"Tribler {v}",
            swagger_path="/docs"
        )
        if self.config.get("api/key"):
            self._logger.info("Set security scheme and apply to all endpoints")

            aiohttp_apispec.spec.options["security"] = [{"apiKey": []}]
            api_key_scheme = {"type": "apiKey", "in": "header", "name": "X-Api-Key"}
            aiohttp_apispec.spec.components.security_scheme("apiKey", api_key_scheme)

        if "head" in VALID_METHODS_OPENAPI_V2:
            self._logger.info("Remove head")
            VALID_METHODS_OPENAPI_V2.remove("head")

        self.runner = web.AppRunner(self.root_endpoint.app, access_log=None, shutdown_timeout=self.shutdown_timeout)
        await self.runner.setup()

        if self.config.get("api/http_enabled"):
            self._logger.info("Http enabled")
            await self.start_http_site(self.runner)

        if self.config.get("api/https_enabled"):
            self._logger.info("Https enabled")
            await self.start_https_site(self.runner)

        api_port = self.get_api_port()
        self._logger.info("Swagger docs: http://%s:%d/docs", self.http_host, api_port)
        self._logger.info("Swagger JSON: http://%s:%d/docs/swagger.json", self.http_host, api_port)

    async def start_http_site(self, runner: web.AppRunner) -> None:
        """
        Start serving HTTP requests.
        """
        api_port = self.config.get("api/http_port") or 0

        self.site = web.TCPSite(runner, self.http_host, api_port, shutdown_timeout=self.shutdown_timeout)
        self._logger.info("Starting HTTP REST API server on port %d...", api_port)

        try:
            await self.site.start()
        except BaseException as e:
            self._logger.exception("Can't start HTTP REST API on port %d: %s: %s", api_port, e.__class__.__name__,
                                   str(e))
            raise

        current_port = api_port or cast(Server, self.site._server).sockets[0].getsockname()[1]  # noqa: SLF001
        self.config.set("api/http_port_running", current_port)
        self.config.write()

        self._logger.info("HTTP REST API server started on port %d", self.get_api_port())

    async def start_https_site(self, runner: web.AppRunner) -> None:
        """
        Start serving HTTPS requests.
        """
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(Path(self.config.get("api/https_certfile")))

        port = self.config.get("api/https_port")
        self.site_https = web.TCPSite(runner, self.https_host, port, ssl_context=ssl_context)

        await self.site_https.start()
        self._logger.info("Started HTTPS REST API: %s", self.site_https.name)

        current_port = port or cast(Server, self.site_https._server).sockets[0].getsockname()[1]  # noqa: SLF001
        self.config.set("api/https_port_running", current_port)
        self.config.write()

    async def stop(self) -> None:
        """
        Clean up all the REST endpoints and connections.
        """
        self._logger.info("Stopping...")
        if self.runner:
            await self.runner.cleanup()
        for endpoint in self.root_endpoint.endpoints.values():
            await endpoint.shutdown_task_manager()
        self._logger.info("Stopped")
