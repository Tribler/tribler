import json
import os

from twisted.web import resource

from Tribler.Core.Utilities.configparser import CallbackConfigParser
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
        libtribler_settings = self.session.sessconfig.get_config_as_json()

        # Load the Tribler GUI configuration file.
        configfilepath = os.path.join(self.session.get_state_dir(), STATEDIR_GUICONFIG)
        tribler_config = CallbackConfigParser()
        tribler_config.read_file(configfilepath, 'utf-8-sig')

        tribler_settings = tribler_config.get_config_as_json()

        # Merge the configuration of libtribler and the Tribler configuration
        settings_dict = libtribler_settings.copy()
        settings_dict.update(tribler_settings)

        return json.dumps({"settings": settings_dict})
