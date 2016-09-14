import json
import os

from twisted.web import resource

from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.defaults import tribler_defaults
from Tribler.Core.simpledefs import STATEDIR_GUICONFIG


class SettingsEndpoint(resource.Resource):
    """
    This endpoint is reponsible for handing all requests regarding settings and configuration.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        """
        .. http:get:: /settings

        A GET request to this endpoint returns all the session settings that can be found in Tribler.
        Please note that a port with a value of -1 means that the port is randomly assigned at startup.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/settings

            **Example response**:

            .. sourcecode:: javascript

                {
                    "settings": {
                        "barter_community": {
                            "enabled": false
                        },
                        "libtorrent": {
                            "anon_listen_port": -1,
                            ...
                        },
                        ...
                    }
                }
        """
        return json.dumps({"settings": self.session.config.config})
