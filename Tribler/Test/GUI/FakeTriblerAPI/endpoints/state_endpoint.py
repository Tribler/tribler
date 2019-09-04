from __future__ import absolute_import

from twisted.web import resource

import Tribler.Core.Utilities.json_util as json


class StateEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.twisted_dumps({"state": "STARTED", "last_exception": None, "readable_state": "Starting..."})
