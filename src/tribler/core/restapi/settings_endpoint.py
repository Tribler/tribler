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

    def __init__(self, tribler_config: TriblerConfigManager, download_manager: DownloadManager | None = None) -> None:
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
        has_lt_settings = "libtorrent" in settings
        self._logger.info("Received settings: %s", settings)
        self._recursive_merge_settings(settings)
        self.config.write()

        if has_lt_settings and self.download_manager:
            self.download_manager.set_session_limits()

        return RESTResponse({"modified": True})

    def _recursive_merge_settings(self, updates: dict, pointer: str = "") -> None:
        for key, value in updates.items():
            abs_pointer = f"{pointer}/{key}" if pointer else key
            # Since the core doesn't need to be aware of the GUI settings, we just copy them.
            if isinstance(value, dict) and abs_pointer != "ui":
                self._recursive_merge_settings(value, abs_pointer)
            else:
                self.config.set(abs_pointer, value)  # type: ignore[arg-type]
