import asyncio
import logging
import ssl
import traceback
from typing import Optional

from aiohttp import web
from aiohttp.web_exceptions import HTTPNotFound, HTTPRequestEntityTooLarge
from aiohttp_apispec import AiohttpApiSpec
from apispec.core import VALID_METHODS_OPENAPI_V2

from tribler.core.components.reporter.exception_handler import default_core_exception_handler
from tribler.core.components.restapi.rest.rest_endpoint import (
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    HTTP_UNAUTHORIZED,
    HTTP_REQUEST_ENTITY_TOO_LARGE,
    MAX_REQUEST_SIZE,
    RESTResponse,
)
from tribler.core.components.restapi.rest.root_endpoint import RootEndpoint
from tribler.core.components.restapi.rest.settings import APISettings
from tribler.core.utilities.network_utils import default_network_utils
from tribler.core.utilities.process_manager import get_global_process_manager
from tribler.core.version import version_id


SITE_START_TIMEOUT = 5.0  # seconds


logger = logging.getLogger(__name__)


@web.middleware
class ApiKeyMiddleware:
    def __init__(self, api_key):
        self.api_key = api_key

    async def __call__(self, request, handler):
        if self.authenticate(request):
            return await handler(request)
        else:
            return RESTResponse({'error': 'Unauthorized access'}, status=HTTP_UNAUTHORIZED)

    def authenticate(self, request):
        if any([request.path.startswith(path) for path in ['/docs', '/static', '/debug-ui']]):
            return True
        # The api key can either be in the headers or as part of the url query
        api_key = request.headers.get('X-Api-Key') or request.query.get('apikey') or request.cookies.get('api_key')
        expected_api_key = self.api_key
        return not expected_api_key or expected_api_key == api_key


@web.middleware
async def error_middleware(request, handler):
    try:
        response = await handler(request)
    except ConnectionResetError:
        # A client closes the connection. It is not the Core error, nothing to handle or report this.
        # We cannot return response, as the connection is already closed, so we just propagate the exception
        # without reporting it to Sentry. The exception will be printed to the log by aiohttp.server.log_exception()
        raise
    except HTTPNotFound:
        return RESTResponse({'error': {
            'handled': True,
            'message': f'Could not find {request.path}'
        }}, status=HTTP_NOT_FOUND)
    except HTTPRequestEntityTooLarge as http_error:
        return RESTResponse({'error': {
            'handled': True,
            'message': http_error.text,
        }}, status=HTTP_REQUEST_ENTITY_TOO_LARGE)
    except Exception as e:
        logger.exception(e)
        full_exception = traceback.format_exc()

        default_core_exception_handler.unhandled_error_observer(None, {'exception': e, 'should_stop': False})

        return RESTResponse({"error": {
            "handled": False,
            "code": e.__class__.__name__,
            "message": str(full_exception)
        }}, status=HTTP_INTERNAL_SERVER_ERROR)
    return response


class RESTManager:
    """
    This class is responsible for managing the startup and closing of the Tribler HTTP API.
    """

    def __init__(self, config: APISettings, root_endpoint: RootEndpoint, state_dir=None, shutdown_timeout: int = 10):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.root_endpoint = root_endpoint
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.site_https: Optional[web.TCPSite] = None
        self.config = config
        self.state_dir = state_dir

        self.http_host = '127.0.0.1'
        self.https_host = '0.0.0.0'
        self.shutdown_timeout = shutdown_timeout

    def get_endpoint(self, name):
        return self.root_endpoint.endpoints.get('/' + name)

    def set_api_port(self, api_port: int):
        default_network_utils.remember(api_port)

        if self.config.http_port != api_port:
            self.config.http_port = api_port

        process_manager = get_global_process_manager()
        if process_manager:
            process_manager.current_process.set_api_port(api_port)

    async def start(self):
        """
        Starts the HTTP API with the listen port as specified in the session configuration.
        """
        self._logger.info('Starting RESTManager...')

        # Not using setup_aiohttp_apispec here, as we need access to the APISpec to set the security scheme
        aiohttp_apispec = AiohttpApiSpec(
            url='/docs/swagger.json',
            app=self.root_endpoint.app,
            title='Tribler REST API documentation',
            version=version_id,
            swagger_path='/docs'
        )
        if self.config.key:
            self._logger.info('Set security scheme and apply to all endpoints')

            aiohttp_apispec.spec.options['security'] = [{'apiKey': []}]
            api_key_scheme = {'type': 'apiKey', 'in': 'header', 'name': 'X-Api-Key'}
            aiohttp_apispec.spec.components.security_scheme('apiKey', api_key_scheme)

        if 'head' in VALID_METHODS_OPENAPI_V2:
            self._logger.info('Remove head')
            VALID_METHODS_OPENAPI_V2.remove('head')

        self.runner = web.AppRunner(self.root_endpoint.app, access_log=None)
        await self.runner.setup()

        if self.config.http_enabled:
            self._logger.info('Http enabled')
            await self.start_http_site()

        if self.config.https_enabled:
            self._logger.info('Https enabled')
            await self.start_https_site()

        self._logger.info(f'Swagger docs: http://{self.http_host}:{self.config.http_port}/docs')
        self._logger.info(f'Swagger JSON: http://{self.http_host}:{self.config.http_port}/docs/swagger.json')

    async def start_http_site(self):
        api_port = max(self.config.http_port, 0)  # if the value in config is -1 we convert it to 0

        self.site = web.TCPSite(self.runner, self.http_host, api_port, shutdown_timeout=self.shutdown_timeout)
        self._logger.info(f"Starting HTTP REST API server on port {api_port}...")

        try:
            # The self.site.start() is expected to start immediately. It looks like on some machines, it hangs.
            # The timeout is added to prevent the hypothetical hanging.
            await asyncio.wait_for(self.site.start(), timeout=SITE_START_TIMEOUT)

        except BaseException as e:
            self._logger.exception(f"Can't start HTTP REST API on port {api_port}: {e.__class__.__name__}: {e}")
            raise

        if not api_port:
            api_port = self.site._server.sockets[0].getsockname()[1]  # pylint: disable=protected-access

        self.set_api_port(api_port)
        self._logger.info(f"HTTP REST API server started on port {api_port}")

    async def start_https_site(self):
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

        cert = self.config.get_path_as_absolute('https_certfile', self.state_dir)
        ssl_context.load_cert_chain(cert)

        port = self.config.https_port
        self.site_https = web.TCPSite(self.runner, self.https_host, port, ssl_context=ssl_context)

        await self.site_https.start()
        self._logger.info("Started HTTPS REST API: %s", self.site_https.name)

    async def stop(self):
        self._logger.info('Stopping...')
        if self.runner:
            await self.runner.cleanup()
        self._logger.info('Stopped')
