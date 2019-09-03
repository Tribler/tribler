from __future__ import absolute_import

from twisted.web import resource

import Tribler.Core.Utilities.json_util as json
import Tribler.Test.GUI.FakeTriblerAPI.tribler_utils as tribler_utils


class SettingsEndpoint(resource.Resource):

    isLeaf = True

    # Only contains the most necessary settings needed for the GUI
    def render_GET(self, _request):
        return json.twisted_dumps(tribler_utils.tribler_data.settings)

    # Do nothing when we are saving the settings
    def render_POST(self, _request):
        return json.twisted_dumps({"modified": True})
