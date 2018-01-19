from twisted.web import resource

import Tribler.Core.Utilities.json_util as json


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
        settings_dict = json.loads(request.content.read(), encoding='latin_1')
        self.parse_settings_dict(settings_dict)
        self.session.config.write()

        return json.dumps({"modified": True})

    def parse_setting(self, section, option, value):
        """
        Set a specific Tribler setting. Throw a ValueError if this setting is not available.
        """
        if section in self.session.config.config and option in self.session.config.config[section]:
            self.session.config.config[section][option] = value
        else:
            raise ValueError("Section %s with option %s does not exist" % (section, option))

        # Perform some actions when specific keys are set
        if section == "libtorrent" and (option == "max_download_rate" or option == "max_upload_rate"):
            self.session.lm.ltmgr.update_max_rates_from_config()

        # Apply changes to the default downloadconfig to already existing downloads
        if section == "download_defaults" and option in ["seeding_mode", "seeding_time", "seeding_ratio"]:
            for download in self.session.get_downloads():
                if download.get_share_mode():
                    # Do not interfere with credit mining downloads
                    continue
                elif option == "seeding_mode":
                    download.set_seeding_mode(value)
                elif option == "seeding_time":
                    download.set_seeding_time(value)
                elif option == "seeding_ratio":
                    download.set_seeding_ratio(value)

    def parse_settings_dict(self, settings_dict, depth=1, root_key=None):
        """
        Parse the settings dictionary.
        """
        for key, value in settings_dict.iteritems():
            if isinstance(value, dict):
                self.parse_settings_dict(value, depth=depth+1, root_key=key)
            else:
                self.parse_setting(root_key, key, value)
