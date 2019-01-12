from __future__ import absolute_import

import logging
import os
from traceback import format_tb
from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred
from twisted.internet.error import CannotListenError
from twisted.python.compat import intToBytes
from twisted.python.failure import Failure
from twisted.web import server, http

from Tribler.Core.Modules.restapi.root_endpoint import RootEndpoint
import Tribler.Core.Utilities.json_util as json
from Tribler.pyipv8.ipv8.taskmanager import TaskManager


class RESTManager(TaskManager):
    """
    This class is responsible for managing the startup and closing of the Tribler HTTP API.
    """

    def __init__(self, session):
        super(RESTManager, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.site = None
        self.root_endpoint = None

    def start(self):
        """
        Starts the HTTP API with the listen port as specified in the session configuration.
        """
        self.root_endpoint = RootEndpoint(self.session)
        site = server.Site(resource=self.root_endpoint)
        site.requestFactory = RESTRequest
        api_port = self.session.config.get_http_api_port()

        if not self.session.config.get_http_api_retry_port():
            self.site = reactor.listenTCP(api_port, site, interface="127.0.0.1")
        else:
            bind_attempts = 0
            while bind_attempts < 10:
                try:
                    self.site = reactor.listenTCP(api_port + bind_attempts, site, interface="127.0.0.1")
                    self.session.config.set_http_api_port(api_port + bind_attempts)
                    break
                except CannotListenError:
                    bind_attempts += 1

        self._logger.info("Starting REST API on port %d", self.site.port)

        # REST Manager does not accept any new requests if Tribler is shutting down.
        # Note that environment variable 'TRIBLER_SHUTTING_DOWN' is set to 'TRUE' (string)
        # when shutdown has started. Also see RESTRequest.process() method below.
        # Therefore, here while starting the REST Manager we make sure that this
        # variable is set to 'FALSE' (string).
        os.environ['TRIBLER_SHUTTING_DOWN'] = "FALSE"

    def stop(self):
        """
        Stop the HTTP API and return a deferred that fires when the server has shut down.
        """
        return maybeDeferred(self.site.stopListening)


class RESTRequest(server.Request):
    """
    This class overrides the write(data) method to do a safe write only when channel is not None and gracefully
    takes care of unhandled exceptions raised during the processing of any request.
    """
    defaultContentType = b"text/json"

    def __init__(self, *args, **kw):
        server.Request.__init__(self, *args, **kw)
        self._logger = logging.getLogger(self.__class__.__name__)

    def processingFailed(self, failure):
        self._logger.exception(failure)
        response = {
            u"error": {
                u"handled": False,
                u"code": failure.value.__class__.__name__,
                u"message": failure.value.message
            }
        }
        if self.site and self.site.displayTracebacks:
            response[u"error"][u"trace"] = format_tb(failure.getTracebackObject())

        body = json.dumps(response)
        self.setResponseCode(http.INTERNAL_SERVER_ERROR)
        self.setHeader(b'content-type', self.defaultContentType)
        self.setHeader(b'content-length', intToBytes(len(body)))
        self.write(body)
        self.finish()
        return failure

    def write(self, data):
        """
        Writes data only if request has not finished and channel is not None
        """
        if not self.finished and self.channel:
            server.Request.write(self, data)

    def process(self):
        """
        Reject all requests if the shutdown sequence has already started.
        """
        if os.environ.get('TRIBLER_SHUTTING_DOWN', "FALSE") == "TRUE":
            self._logger.error("Tribler shutdown in process. Not accepting any more request - %s", self)
            self.processingFailed(Failure(Exception("Tribler is shutting down")))
        else:
            server.Request.process(self)
