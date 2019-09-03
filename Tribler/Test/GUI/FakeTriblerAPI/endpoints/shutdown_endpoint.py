from __future__ import absolute_import

from twisted.internet import reactor, task
from twisted.web import resource

import Tribler.Core.Utilities.json_util as json


class ShutdownEndpoint(resource.Resource):
    """
    With this endpoint you can shutdown Tribler.
    """

    def render_PUT(self, _):
        """
        Shuts down the fake API
        """
        task.deferLater(reactor, 0, reactor.stop)
        return json.twisted_dumps({"shutdown": True})
