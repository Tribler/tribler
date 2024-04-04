from aiohttp import web
from aiohttp_apispec import docs, json_schema
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean

from tribler.core.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.restapi.rest_endpoint import RESTEndpoint, RESTResponse
from tribler.tribler_config import TriblerConfigManager


class SettingsEndpoint(RESTEndpoint):
    """
    This endpoint is reponsible for handing all requests regarding settings and configuration.
    """
    path = '/settings'

    def __init__(self, tribler_config: TriblerConfigManager, download_manager: DownloadManager = None) -> None:
        super().__init__()
        self.config = tribler_config
        self.download_manager = download_manager
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
    async def get_settings(self, request: web.Request) -> RESTResponse:
        self._logger.info(f'Get settings. Request: {request}')
        return RESTResponse({
            "settings": self.config.configuration,
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
    async def update_settings(self, request: web.Request) -> RESTResponse:
        settings = await request.json()
        self._logger.info(f'Received settings: {settings}')
        self._recursive_merge_settings(self.config.configuration, settings)
        self.config.write()

        if self.download_manager:
            self.download_manager.update_max_rates_from_config()

        return RESTResponse({"modified": True})

    def _recursive_merge_settings(self, existing: dict, updates: dict) -> None:
        for key in existing:
            value = updates.get(key, existing[key])
            if isinstance(value, dict):
                self._recursive_merge_settings(existing[key], value)
            existing[key] = value
