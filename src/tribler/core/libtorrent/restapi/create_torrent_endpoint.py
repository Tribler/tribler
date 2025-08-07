import asyncio
import base64
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import libtorrent as lt
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp_apispec import docs, json_schema
from ipv8.REST.schema import schema
from marshmallow.fields import String

from tribler.core.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.core.libtorrent.torrents import create_torrent_file
from tribler.core.restapi.rest_endpoint import (
    HTTP_BAD_REQUEST,
    MAX_REQUEST_SIZE,
    RESTEndpoint,
    RESTResponse,
    return_handled_exception,
)


class CreateTorrentEndpoint(RESTEndpoint):
    """
    Create a torrent file from local files.

    See: http://www.bittorrent.org/beps/bep_0012.html
    """

    path = "/api/createtorrent"

    def __init__(self, download_manager: DownloadManager, client_max_size: int = MAX_REQUEST_SIZE) -> None:
        """
        Create a new endpoint to create torrents.
        """
        super().__init__(client_max_size=client_max_size)
        self.download_manager = download_manager
        self.app.add_routes([web.post("", self.create_torrent)])

    @docs(
        tags=["Libtorrent"],
        summary="Create a torrent from local files and return it in base64 encoding.",
        parameters=[{
            "in": "query",
            "name": "download",
            "description": "Flag indicating whether or not to start downloading",
            "type": "boolean",
            "required": False
        }],
        responses={
            200: {
                "schema": schema(CreateTorrentResponse={"torrent": "base64 encoded torrent file"}),
                "examples": {"Success": {"success": True}}
            },
            HTTP_BAD_REQUEST: {
                "schema": schema(HandledErrorSchema={"error": "any failures that may have occurred"}),
                "examples": {"Error": {"error": {"handled": True, "message": "files parameter missing"}}}
            }
        }
    )
    @json_schema(schema(CreateTorrentRequest={
        "files": [String],
        "name": String,
        "description": String,
        "trackers": [String],
        "export_dir": String
    }))
    async def create_torrent(self, request: Request) -> RESTResponse:
        """
        Create a torrent from local files and return it in base64 encoding.
        """
        parameters = await request.json()

        if parameters.get("files"):
            file_path_list = [Path(p) for p in parameters["files"]]
        else:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "files parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        tracker_url_list = parameters.get("trackers", [])

        export_dir = None
        if parameters.get("export_dir"):
            export_dir = Path(parameters["export_dir"])

        try:
            v = version("tribler")
        except PackageNotFoundError:
            v = "git"

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                create_torrent_file,
                file_path_list,
                tracker_url_list[0] if tracker_url_list else None,
                tracker_url_list if tracker_url_list else None,
                parameters.get("description"),
                f"Tribler version: {v}",
                None,
                None,
                0,
                (str(export_dir / f"{parameters.get("name", "unknown")}.torrent")
                 if export_dir and export_dir.exists() else None),
                None
            )
        except (OSError, UnicodeDecodeError, RuntimeError) as e:
            self._logger.exception(e)
            return return_handled_exception(e)

        # Download this torrent if specified
        if "download" in request.query and request.query["download"] and request.query["download"] == "1":
            download_config = DownloadConfig.from_defaults(self.download_manager.config)
            download_config.set_dest_dir(result["base_dir"])
            download_config.set_hops(self.download_manager.config.get("libtorrent/download_defaults/number_hops"))
            await self.download_manager.start_download(result["torrent_file_path"],
                                                       TorrentDef(result["atp"]),
                                                       download_config)

        return RESTResponse(json.dumps({"torrent": base64.b64encode(
            lt.bencode(lt.write_torrent_file(result["atp"]))  # type: ignore[attr-defined]
        ).decode()}))
