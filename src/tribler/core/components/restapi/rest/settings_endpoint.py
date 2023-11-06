from aiohttp import web
from aiohttp_apispec import docs, json_schema
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean

from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.restapi.rest.rest_endpoint import RESTEndpoint, RESTResponse
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.network_utils import default_network_utils
from tribler.core.utilities.utilities import froze_it


@froze_it
class SettingsEndpoint(RESTEndpoint):
    """
    This endpoint is reponsible for handing all requests regarding settings and configuration.
    """
    path = '/settings'

    def __init__(self, tribler_config: TriblerConfig, download_manager: DownloadManager = None):
        super().__init__()
        self.config = tribler_config
        self.download_manager = download_manager

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
            "settings": self.config.dict(),
            "ports": list(default_network_utils.ports_in_use)
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
        settings = await request.json()
        self._logger.info(f'Received settings: {settings}')
        self.config.update_from_dict(settings)
        self.config.write()

        if self.download_manager:
            self.download_manager.update_max_rates_from_config()

        return RESTResponse({"modified": True})
