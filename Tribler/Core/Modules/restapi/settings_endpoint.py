import json
import os
from ConfigParser import RawConfigParser
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

        # Load the Tribler GUI configuration file
        self.gui_config_file_path = os.path.join(self.session.config.get_state_dir(), STATEDIR_GUICONFIG)
        self.tribler_gui_config = CallbackConfigParser()
        self.tribler_gui_config.read_file(self.gui_config_file_path, 'utf-8-sig')

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
                        "libtorrent": {
                            "anon_listen_port": -1,
                            ...
                        },
                        ...
                    }
                }
        """
        return json.dumps({"settings": self.session.config.config})

    def render_POST(self, request):
        """
        .. http:post:: /settings

        A POST request to this endpoint will update Tribler settings. A JSON-dictionary should be passed as body
        contents.

            **Example request**:

            .. sourcecode:: none

                curl -X POST http://localhost:8085/settings --data "{"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "modified": True
                }
        """
        settings_dict = json.loads(request.content.read())
        self.parse_settings_dict(settings_dict)
        self.session.config.write()

        return json.dumps({"modified": True})

    def parse_setting(self, section, option, value):
        """
        Set a specific Tribler setting. Throw a ValueError if this setting is not available.
        """
        if section == "Tribler" or section == "downloadconfig":
            # Write to the Tribler GUI config file
            if not self.tribler_gui_config.has_option(section, option):
                raise ValueError("Section %s with option %s does not exist" % (section, option))
            RawConfigParser.set(self.tribler_gui_config, section, option, value)
            self.tribler_gui_config.write_file(self.gui_config_file_path)
            return

        if section in self.session.config.config and option in self.session.config.config[section]:
            self.session.config.config[section][option] = value
        else:
            raise ValueError("Section %s with option %s does not exist" % (section, option))

        # Reload the GUI settings in Tribler (there might have been download settings that have changed)
        self.session.setup_tribler_gui_config()

        # Perform some actions when specific keys are set
        if section == "libtorrent" and (option == "max_download_rate" or option == "max_upload_rate"):
            self.session.lm.ltmgr.update_max_rates_from_config()

    def parse_settings_dict(self, settings_dict, depth=1, root_key=None):
        """
        Parse the settings dictionary.
        """
        for key, value in settings_dict.iteritems():
            if isinstance(value, dict):
                self.parse_settings_dict(value, depth=depth+1, root_key=key)
            else:
                self.parse_setting(root_key, key, value)
