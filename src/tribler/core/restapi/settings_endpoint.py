from aiohttp import web
from aiohttp_apispec import docs, json_schema
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean

from tribler.core.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.restapi.rest_endpoint import RESTEndpoint, RESTResponse
from tribler.tribler_config import TriblerConfigManager


class SettingsEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing all requests regarding settings and configuration.
    """

    path = "/api/settings"

    def __init__(self, tribler_config: TriblerConfigManager, download_manager: DownloadManager = None) -> None:
        """
        Create a new settings endpoint.
        """
        super().__init__()
        self.config = tribler_config
        self.download_manager = download_manager
        self.app.add_routes([web.get("", self.get_settings),
                             web.post("", self.update_settings)])

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
        """
        Return all the session settings that can be found in Tribler.
        """
        self._logger.info("Get settings. Request: %s", str(request))
        return RESTResponse({
            "settings": self.config.configuration,
        })

    @docs(
        tags=["General"],
        summary="Update Tribler settings.",
        responses={
            200: {
                "schema": schema(UpdateTriblerSettingsResponse={"modified": Boolean})
            }
        }
    )
    @json_schema(schema(UpdateTriblerSettingsRequest={}))
    async def update_settings(self, request: web.Request) -> RESTResponse:
        """
        Update Tribler settings.
        """
        settings = await request.json()
        self._logger.info("Received settings: %s", settings)
        self._recursive_merge_settings(self.config.configuration, settings)
        self.config.write()

        if self.download_manager:
            self.download_manager.update_max_rates_from_config()

        return RESTResponse({"modified": True})

    def _recursive_merge_settings(self, existing: dict, updates: dict, top: bool = True) -> None:
        for key in existing:  # noqa: PLC0206
            # Ignore top-level ui entry
            if top and key == "ui":
                continue
            value = updates.get(key, existing[key])
            if isinstance(value, dict):
                self._recursive_merge_settings(existing[key], value, False)
            existing[key] = value
        # It can also be that the updated entry does not exist (yet) in an old config.
        for key in updates:  # noqa: PLC0206
            if key in existing:
                continue
            existing[key] = updates[key]

        # Since the core doesn't need to be aware of the GUI settings, we just copy them.
        if top and "ui" in updates:
            existing["ui"] = existing.get("ui", {})
            existing["ui"].update(updates["ui"])
