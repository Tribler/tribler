import logging
import os

from aiohttp import web

from ipv8.taskmanager import TaskManager

from Tribler.Core.Modules.restapi.rest_endpoint import HTTP_INTERNAL_SERVER_ERROR, HTTP_UNAUTHORIZED, RESTResponse
from Tribler.Core.Modules.restapi.root_endpoint import RootEndpoint


@web.middleware
class ApiKeyMiddleware(object):
    def __init__(self, config):
        self.config = config

    async def __call__(self, request, handler):
        if self.authenticate(request):
            return await handler(request)
        else:
            return RESTResponse({'error': 'Unauthorized access'}, status=HTTP_UNAUTHORIZED)

    def authenticate(self, request):
        # The api key can either be in the headers or as part of the url query
        api_key = request.headers.get('X-Api-Key') or request.query.get('apikey')
        expected_api_key = self.config.get_http_api_key()
        return not expected_api_key or expected_api_key == api_key


@web.middleware
async def error_middleware(request, handler):
    try:
        if os.environ.get('TRIBLER_SHUTTING_DOWN', "FALSE") == "TRUE":
            raise Exception('Tribler is shutting down')
        response = await handler(request)
    except Exception as e:
        return RESTResponse({"error": {
            "handled": False,
            "code": e.__class__.__name__,
            "message": str(e)
        }}, status=HTTP_INTERNAL_SERVER_ERROR)
    return response


class RESTManager(TaskManager):
    """
    This class is responsible for managing the startup and closing of the Tribler HTTP API.
    """

    def __init__(self, session):
        super(RESTManager, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.root_endpoint = None
        self.session = session
        self.site = None

    def get_endpoint(self, name):
        return self.root_endpoint.endpoints['/' + name]

    def set_ipv8_session(self, ipv8_session):
        self.root_endpoint.set_ipv8_session(ipv8_session)

    async def start(self):
        """
        Starts the HTTP API with the listen port as specified in the session configuration.
        """
        self.root_endpoint = RootEndpoint(self.session, middlewares=[ApiKeyMiddleware(self.session.config),
                                                                     error_middleware])
        runner = web.AppRunner(self.root_endpoint.app, access_log=None)
        await runner.setup()

        api_port = self.session.config.get_http_api_port()
        if not self.session.config.get_http_api_retry_port():
            self.site = web.TCPSite(runner, 'localhost', api_port)
        else:
            bind_attempts = 0
            while bind_attempts < 10:
                try:
                    self.site = web.TCPSite(runner, 'localhost', api_port + bind_attempts)
                    self.session.config.set_http_api_port(api_port + bind_attempts)
                    break
                except OSError:
                    bind_attempts += 1
        await self.site.start()

        self._logger.info("Starting REST API on port %d", self.site._port)

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
        await self.root_endpoint.stop()
        await self.site.stop()
