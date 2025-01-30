import asyncio
import base64
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import libtorrent as lt
from aiohttp import web
from aiohttp.abc import Request
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


def recursive_bytes(obj):  # noqa: ANN001, ANN201
    """
    Converts any unicode strings within a Python data structure to bytes. Strings will be encoded using UTF-8.

    :param obj: object comprised of lists/dicts/strings/bytes
    :return: obj: object comprised of lists/dicts/bytes
    """
    if isinstance(obj, dict):
        return {recursive_bytes(k): recursive_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [recursive_bytes(i) for i in obj]
    if isinstance(obj, str):
        return obj.encode('utf8')
    return obj


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
        params = {}

        if parameters.get("files"):
            file_path_list = [Path(p) for p in parameters["files"]]
        else:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "files parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        if parameters.get("description"):
            params["comment"] = parameters["description"]

        if parameters.get("trackers"):
            tracker_url_list = parameters["trackers"]
            params["announce"] = tracker_url_list[0]
            params["announce-list"] = tracker_url_list

        name = "unknown"
        if parameters.get("name"):
            name = parameters["name"]
            params["name"] = name

        export_dir = None
        if parameters.get("export_dir"):
            export_dir = Path(parameters["export_dir"])

        try:
            v = version("tribler")
        except PackageNotFoundError:
            v = "git"
        params["created by"] = f"Tribler version: {v}"
        params["nodes"] = False
        params["httpseeds"] = False
        params["encoding"] = False
        params["piece length"] = 0  # auto

        save_path = export_dir / (f"{name}.torrent") if export_dir and export_dir.exists() else None

        try:
            result = await asyncio.get_event_loop().run_in_executor(None, create_torrent_file,
                                                                    file_path_list, recursive_bytes(params),
                                                                    save_path)
        except (OSError, UnicodeDecodeError, RuntimeError) as e:
            self._logger.exception(e)
            return return_handled_exception(e)

        metainfo_dict = lt.bdecode(result["metainfo"])

        # Download this torrent if specified
        if "download" in request.query and request.query["download"] and request.query["download"] == "1":
            download_config = DownloadConfig.from_defaults(self.download_manager.config)
            download_config.set_dest_dir(result["base_dir"])
            download_config.set_hops(self.download_manager.config.get("libtorrent/download_defaults/number_hops"))
            await self.download_manager.start_download(save_path, TorrentDef(metainfo_dict), download_config)

        return RESTResponse(json.dumps({"torrent": base64.b64encode(result["metainfo"]).decode()}))
