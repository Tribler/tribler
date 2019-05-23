from __future__ import absolute_import

import json

from twisted.internet import reactor, task
from twisted.web import resource


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
