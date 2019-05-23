import json

from twisted.web import resource
from twisted.internet import reactor, task


class ShutdownEndpoint(resource.Resource):
    """
    With this endpoint you can shutdown Tribler.
    """

    def render_PUT(self, _):
        """
        Shuts down the fake API
        """
        task.deferLater(reactor, 0, reactor.stop)
        return json.dumps({"shutdown": True})
