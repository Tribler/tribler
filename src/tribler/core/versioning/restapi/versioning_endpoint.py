from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from marshmallow.fields import Bool, List, String

from tribler.core.restapi.rest_endpoint import HTTP_BAD_REQUEST, MAX_REQUEST_SIZE, RESTEndpoint, RESTResponse
from tribler.tribler_config import VERSION_SUBDIR

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

    from tribler.core.restapi.rest_manager import TriblerRequest
    from tribler.core.versioning.manager import VersioningManager
    RequestType: TypeAlias = TriblerRequest[tuple[VersioningManager]]


class VersioningEndpoint(RESTEndpoint):
    """
    An endpoint for version determination and upgrading from the previous version.
    """

    path = "/api/versioning"

    def __init__(self, middlewares: tuple = (), client_max_size: int = MAX_REQUEST_SIZE) -> None:
        """
        Create a new endpoint to create torrents.
        """
        super().__init__(middlewares, client_max_size)

        self.versioning_manager: VersioningManager | None = None
        self.required_components = ("versioning_manager",)

        self.app.add_routes([
            web.get("/versions", self.get_versions),
            web.get("/versions/current", self.get_current_version),
            web.get("/versions/check", self.check_version),
            web.delete("/versions/{version}", self.remove_version),
            web.post("/upgrade", self.perform_upgrade),
            web.get("/upgrade/available", self.can_upgrade),
            web.get("/upgrade/working", self.is_upgrading)
        ])

    @docs(
        tags=["Versioning"],
        summary="Get the current release version or whether we are running from source.",
        responses={
            200: {
                "schema": schema(CurrentVersionResponse={"version": String})
            }
        }
    )
    async def get_current_version(self, request: RequestType) -> RESTResponse:
        """
        Get the current release version, or None when running from archive or GIT.
        """
        return RESTResponse({"version": request.context[0].get_current_version() or "git"})

    @docs(
        tags=["Versioning"],
        summary="Get all versions in our state directory.",
        responses={
            200: {
                "schema": schema(GetVersionsResponse={"versions": List(String), "current": String})
            }
        }
    )
    async def get_versions(self, request: RequestType) -> RESTResponse:
        """
        Get all versions in our state directory.
        """
        return RESTResponse({"versions": request.context[0].get_versions(), "current": VERSION_SUBDIR})

    @docs(
        tags=["Versioning"],
        summary="Check the tribler.org + GitHub websites for a new version.",
        responses={
            200: {
                "schema": schema(CheckVersionResponse={"new_version": String, "has_version": Bool})
            }
        }
    )
    async def check_version(self, request: RequestType) -> RESTResponse:
        """
        Check the tribler.org + GitHub websites for a new version.
        """
        new_version = await request.context[0].check_version()
        return RESTResponse({"new_version": new_version or "", "has_version": new_version is not None})

    @docs(
        tags=["Versioning"],
        summary="Check if we have old database/download files to port to our current version.",
        responses={
            200: {
                "schema": schema(CanUpgradeResponse={"can_upgrade": String})
            }
        }
    )
    async def can_upgrade(self, request: RequestType) -> RESTResponse:
        """
        Check if we have old database/download files to port to our current version.
        """
        return RESTResponse({"can_upgrade": request.context[0].can_upgrade()})

    @docs(
        tags=["Versioning"],
        summary="Perform an upgrade.",
        responses={
            200: {
                "schema": schema(PerformUpgradeResponse={"success": Bool})
            }
        }
    )
    async def perform_upgrade(self, request: RequestType) -> RESTResponse:
        """
        Perform an upgrade.
        """
        request.context[0].perform_upgrade()
        return RESTResponse({"success": True})

    @docs(
        tags=["Versioning"],
        summary="Check if the upgrade is still running.",
        responses={
            200: {
                "schema": schema(IsUpgradingResponse={"running": Bool})
            }
        }
    )
    async def is_upgrading(self, request: RequestType) -> RESTResponse:
        """
        Check if the upgrade is still running.
        """
        return RESTResponse({"running": request.context[0].task_manager.get_task("Upgrade") is not None})

    @docs(
        tags=["Versioning"],
        summary="Check if the upgrade is still running.",
        parameters=[{
            "in": "path",
            "name": "version",
            "description": "The version to remove.",
            "type": "string",
            "required": "true"
        }],
        responses={
            200: {
                "schema": schema(RemoveVersionResponse={"success": Bool})
            },
            HTTP_BAD_REQUEST: {
                "schema": schema(RemoveVersionNotFoundResponse={"error": schema(ErrorResponse={"handled": Bool,
                                                                                               "message": String})})
            }
        }
    )
    async def remove_version(self, request: RequestType) -> RESTResponse:
        """
        Remove the files for a version.
        """
        version = request.match_info["version"]
        if not version:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "No version given"
                                }}, status=HTTP_BAD_REQUEST)
        request.context[0].remove_version(version)
        return RESTResponse({"success": True})
