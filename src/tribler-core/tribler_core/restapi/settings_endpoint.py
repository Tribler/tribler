from asyncio import gather

from aiohttp import web

from tribler_core.modules.credit_mining.credit_mining_manager import CreditMiningManager
from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class SettingsEndpoint(RESTEndpoint):
    """
    This endpoint is reponsible for handing all requests regarding settings and configuration.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_settings),
                             web.post('', self.update_settings)])

    async def get_settings(self, request):
        """
        .. http:get:: /settings

        A GET request to this endpoint returns all the session settings that can be found in Tribler.
        It also returns the runtime-determined ports, i.e. the port for the video server.
        Please note that a port with a value of -1 in the settings means that the port is randomly assigned at startup.

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
        return RESTResponse({
            "settings": self.session.config.config,
            "ports": self.session.config.selected_ports
        })

    async def update_settings(self, request):
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
        settings_dict = await request.json()
        await self.parse_settings_dict(settings_dict)
        self.session.config.write()
        return RESTResponse({"modified": True})

    async def parse_setting(self, section, option, value):
        """
        Set a specific Tribler setting. Throw a ValueError if this setting is not available.
        """
        if section in self.session.config.config and option in self.session.config.config[section]:
            self.session.config.config[section][option] = value
        else:
            raise ValueError("Section %s with option %s does not exist" % (section, option))

        # Perform some actions when specific keys are set
        if section == "libtorrent" and (option == "max_download_rate" or option == "max_upload_rate"):
            self.session.ltmgr.update_max_rates_from_config()

        if section == 'credit_mining' and option == 'enabled' and \
             value != bool(self.session.credit_mining_manager):
            if value:
                self.session.credit_mining_manager = CreditMiningManager(self.session)
            else:
                await self.session.credit_mining_manager.shutdown(remove_downloads=True)
                self.session.credit_mining_manager = None
        elif section == 'credit_mining' and option == 'sources':
            if self.session.config.get_credit_mining_enabled():
                # Out with the old..
                if self.session.credit_mining_manager.sources:
                    await gather(*[self.session.credit_mining_manager.remove_source(source) for source in
                                   list(self.session.credit_mining_manager.sources.keys())])
                # In with the new
                for source in value:
                    self.session.credit_mining_manager.add_source(source)
        elif section == 'credit_mining' and option == 'max_disk_space':
            if self.session.config.get_credit_mining_enabled():
                self.session.credit_mining_manager.settings.max_disk_space = value

    async def parse_settings_dict(self, settings_dict, depth=1, root_key=None):
        """
        Parse the settings dictionary.
        """
        for key, value in settings_dict.items():
            if isinstance(value, dict):
                await self.parse_settings_dict(value, depth=depth+1, root_key=key)
            else:
                await self.parse_setting(root_key, key, value)
