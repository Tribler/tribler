import logging
import os
import ssl
import traceback

from aiohttp import web
from aiohttp.web_exceptions import HTTPNotFound

from aiohttp_apispec import AiohttpApiSpec

from apispec.core import VALID_METHODS_OPENAPI_V2

from tribler_core.components.restapi.rest.rest_endpoint import (
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    HTTP_UNAUTHORIZED,
    RESTResponse,
)
from tribler_core.components.restapi.rest.root_endpoint import RootEndpoint
from tribler_core.components.restapi.rest.settings import APISettings
from tribler_core.version import version_id

logger = logging.getLogger(__name__)


def tribler_shutting_down():
    return os.environ.get('TRIBLER_SHUTTING_DOWN', "FALSE") == "TRUE"


class ShuttingDownException(Exception):
    pass


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
        if tribler_shutting_down():
            raise ShuttingDownException('Tribler is shutting down')
        response = await handler(request)
    except HTTPNotFound:
        return RESTResponse({'error': {
            'handled': True,
            'message': f'Could not find {request.path}'
        }}, status=HTTP_NOT_FOUND)
    except ShuttingDownException as e:
        return RESTResponse({"error": {
            "handled": True,
            "code": e.__class__.__name__,
            "message": str(e)
        }}, status=HTTP_NOT_FOUND)
    except Exception as e:
        logger.exception(e)
        full_exception = traceback.format_exc()
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

    def __init__(self, config: APISettings, root_endpoint: RootEndpoint, state_dir=None):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.root_endpoint = root_endpoint
        self.runner = None
        self.site = None
        self.site_https = None
        self.config = config
        self.state_dir = state_dir

    def get_endpoint(self, name):
        return self.root_endpoint.endpoints.get('/' + name)

    async def start(self):
        """
        Starts the HTTP API with the listen port as specified in the session configuration.
        """
        try:
            pass
        except ImportError:
            pass
        else:
            # self.root_endpoint.add_endpoint('/debug-ui', DebugUIEndpoint(self.session))
            # self._logger.info('Loaded tribler-debug-ui')
            pass

        # Not using setup_aiohttp_apispec here, as we need access to the APISpec to set the security scheme
        aiohttp_apispec = AiohttpApiSpec(
            url='/docs/swagger.json',
            app=self.root_endpoint.app,
            title='Tribler REST API documentation',
            version=version_id,
            swagger_path='/docs'
        )
        if self.config.key:
            # Set security scheme and apply to all endpoints
            aiohttp_apispec.spec.options['security'] = [{'apiKey': []}]
            aiohttp_apispec.spec.components.security_scheme('apiKey', {'type': 'apiKey',
                                                                       'in': 'header',
                                                                       'name': 'X-Api-Key'})

        if 'head' in VALID_METHODS_OPENAPI_V2:
            VALID_METHODS_OPENAPI_V2.remove('head')

        self.runner = web.AppRunner(self.root_endpoint.app, access_log=None)
        await self.runner.setup()

        if self.config.http_enabled:
            api_port = self.config.http_port
            if not self.config.retry_port:
                self.site = web.TCPSite(self.runner, 'localhost', api_port)
                await self.site.start()
            else:
                bind_attempts = 0
                while bind_attempts < 10:
                    try:
                        self.site = web.TCPSite(self.runner, 'localhost', api_port + bind_attempts)
                        await self.site.start()
                        self.config.http_port = api_port + bind_attempts
                        break
                    except OSError:
                        bind_attempts += 1

            self._logger.info("Started HTTP REST API: %s", self.site.name)

        if self.config.https_enabled:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

            cert = self.config.get_path_as_absolute('https_certfile', self.state_dir)
            ssl_context.load_cert_chain(cert)

            port = self.config.https_port
            self.site_https = web.TCPSite(self.runner, '0.0.0.0', port, ssl_context=ssl_context)

            await self.site_https.start()
            self._logger.info("Started HTTPS REST API: %s", self.site_https.name)

        # REST Manager does not accept any new requests if Tribler is shutting down.
        # Note that environment variable 'TRIBLER_SHUTTING_DOWN' is set to 'TRUE' (string)
        # when shutdown has started. Also see RESTRequest.process() method below.
        # Therefore, here while starting the REST Manager we make sure that this
        # variable is set to 'FALSE' (string).
        os.environ['TRIBLER_SHUTTING_DOWN'] = "FALSE"

    async def stop(self):
        """
        Stop the HTTP API and return a deferred that fires when the server has shut down.
        """
        if self.site:
            await self.site.stop()
        if self.site_https:
            await self.site_https.stop()
        # Should the next line be used instead of the above lines?
        # await self.runner.cleanup()
