from aiohttp import web

from aiohttp_apispec import docs, json_schema

from ipv8.REST.schema import schema

from marshmallow.fields import Boolean

from tribler_common.network_utils import NetworkUtils

from tribler_core.components.restapi.rest.rest_endpoint import RESTEndpoint, RESTResponse
from tribler_core.utilities.utilities import froze_it


@froze_it
class SettingsEndpoint(RESTEndpoint):
    """
    This endpoint is reponsible for handing all requests regarding settings and configuration.
    """

    def __init__(self):
        super().__init__()
        self.tribler_config = None
        self.download_manager = None

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_settings),
                             web.post('', self.update_settings)])

    @docs(
        tags=["General"],
        summary="Return all the session settings that can be found in Tribler.",
        responses={
            200: {
                "schema": schema(GetTriblerSettingsResponse={})
            }
        },
        description="This endpoint returns all the session settings that can be found in Tribler.\n\n It also returns "
                    "the runtime-determined ports"
    )
    async def get_settings(self, request):
        self._logger.info(f'Get settings. Request: {request}')
        return RESTResponse({
            "settings": self.tribler_config.dict(),
            "ports": list(NetworkUtils.ports_in_use)
        })

    @docs(
        tags=["General"],
        summary="Update Tribler settings.",
        responses={
            200: {
                "schema": schema(UpdateTriblerSettingsResponse={'modified': Boolean})
            }
        }
    )
    @json_schema(schema(UpdateTriblerSettingsRequest={}))
    async def update_settings(self, request):
        settings_dict = await request.json()
        await self.parse_settings_dict(settings_dict)
        self.tribler_config.write()
        return RESTResponse({"modified": True})

    async def parse_setting(self, section, option, value):
        """
        Set a specific Tribler setting. Throw a ValueError if this setting is not available.
        """
        # if section in self.config.config and option in self.config.config[section]:
        self.tribler_config.__getattribute__(section).__setattr__(option, value)
        # else:
        #     raise ValueError(f"Section {section} with option {option} does not exist")

        # Perform some actions when specific keys are set
        if section == "libtorrent" and (option == "max_download_rate" or option == "max_upload_rate"):
            if self.download_manager:
                self.download_manager.update_max_rates_from_config()

    async def parse_settings_dict(self, settings_dict, depth=1, root_key=None):
        """
        Parse the settings dictionary.
        """
        for key, value in settings_dict.items():
            if isinstance(value, dict):
                await self.parse_settings_dict(value, depth=depth + 1, root_key=key)
            else:
                await self.parse_setting(root_key, key, value)
