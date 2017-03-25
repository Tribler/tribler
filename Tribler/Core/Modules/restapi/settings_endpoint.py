from ConfigParser import RawConfigParser
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

        # Load the Tribler GUI configuration file
        self.gui_config_file_path = os.path.join(self.session.get_state_dir(), STATEDIR_GUICONFIG)
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
        libtribler_settings = self.session.sessconfig.get_config_as_json()
        tribler_settings = self.tribler_gui_config.get_config_as_json()

        # Merge the configuration of libtribler and the Tribler configuration
        settings_dict = libtribler_settings.copy()
        settings_dict.update(tribler_settings)
        settings_dict["general"]["family_filter"] = self.session.tribler_config.config["general"]["family_filter"]

        return json.dumps({"settings": settings_dict})

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
        self.session.save_session_config()

        return json.dumps({"modified": True})

    def parse_setting(self, section, option, value):
        """
        Set a specific Tribler setting. Throw a ValueError if this setting is not available.
        """
        if section == "general" and option == "family_filter":
            self.session.tribler_config.set_family_filter_enabled(value)
            return

        if section == "Tribler" or section == "downloadconfig":
            # Write to the Tribler GUI config file
            if not self.tribler_gui_config.has_option(section, option):
                raise ValueError("Section %s with option %s does not exist" % (section, option))
            RawConfigParser.set(self.tribler_gui_config, section, option, value)
            self.tribler_gui_config.write_file(self.gui_config_file_path)
            return

        if not RawConfigParser.has_option(self.session.sessconfig, section, option):
            raise ValueError("Section %s with option %s does not exist" % (section, option))
        RawConfigParser.set(self.session.sessconfig, section, option, value)

        # Perform some actions when specific keys are set
        if section == "libtorrent" and (option == "max_download_rate" or option == "max_upload_rate"):
            for lt_session in self.session.lm.ltmgr.ltsessions.itervalues():
                ltsession_settings = lt_session.get_settings()
                ltsession_settings['upload_rate_limit'] = self.session.get_libtorrent_max_upload_rate()
                ltsession_settings['download_rate_limit'] = self.session.get_libtorrent_max_download_rate()
                lt_session.set_settings(ltsession_settings)

    def parse_settings_dict(self, settings_dict, depth=1, root_key=None):
        """
        Parse the settings dictionary. Throws an error if the options dictionary seems to be invalid (i.e. there are
        keys not available in the configuration or the depth of the dictionary is too high.
        """
        if depth == 3:
            raise ValueError("Invalid settings dictionary depth (%d)" % depth)

        for key, value in settings_dict.iteritems():
            if isinstance(value, dict):
                self.parse_settings_dict(value, depth=depth+1, root_key=key)
            else:
                self.parse_setting(root_key, key, value)
