import json
from twisted.web import resource

import tribler_utils


class SettingsEndpoint(resource.Resource):

    isLeaf = True

    # Only contains the most necessary settings needed for the GUI
    def render_GET(self, request):
        return json.dumps(tribler_utils.tribler_data.settings)

    # Do nothing when we are saving the settings
    def render_PUT(self, request):
        return json.dumps({"saved": True})
