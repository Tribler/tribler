import logging
from twisted.internet.defer import maybeDeferred
from twisted.web import server
from Tribler.Core.Modules.restapi.root_endpoint import RootEndpoint
from Tribler.Core.Utilities.twisted_thread import reactor
from Tribler.dispersy.taskmanager import TaskManager


class RESTManager(TaskManager):
    """
    This class is responsible for managing the startup and closing of the Tribler HTTP API.
    """

    def __init__(self, session):
        super(RESTManager, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.site = None

    def start(self):
        """
        Starts the HTTP API with the listen port as specified in the session configuration.
        """
        self.site = reactor.listenTCP(self.session.get_http_api_port(),
                                      server.Site(RootEndpoint(self.session)))

    def stop(self):
        """
        Stop the HTTP API and return a deferred that fires when the server has shut down.
        """
        return maybeDeferred(self.site.stopListening)
