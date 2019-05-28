from __future__ import absolute_import

import json

from twisted.web import resource


class StateEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.dumps({"state": "STARTED", "last_exception": None, "readable_state": "Starting..."})
