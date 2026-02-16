import asyncio
import base64
import json
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import TemporaryFile

import libtorrent as lt
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp_apispec import docs, json_schema
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean, String

from tribler.core.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.core.libtorrent.torrents import TorrentVersion, create_torrent_file
from tribler.core.restapi.rest_endpoint import (
    HTTP_BAD_REQUEST,
    MAX_REQUEST_SIZE,
    RESTEndpoint,
    RESTResponse,
    return_handled_exception,
)

handled_error_schema = schema(HandledErrorSchema={"error": "any failures that may have occurred"})


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
        self.app.add_routes([web.post("", self.create_torrent),
                             web.post("/dryrun", self.probe_writable)])

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
                "schema": handled_error_schema,
                "examples": {"Error": {"error": {"handled": True, "message": "files parameter missing"}}}
            }
        }
    )
    @json_schema(
        schema(
            CreateTorrentRequest={
                "files": [String],
                "filenames": [String],
                "name": String,
                "description": String,
                "trackers": [String],
                "export_dir": String,
                "initial_nodes": [String],
                "torrent_version": String
            }
        )
    )
    async def create_torrent(self, request: Request) -> RESTResponse:
        """
        Create a torrent from local files and return it in base64 encoding.
        """
        parameters = await request.json()
        download_config = DownloadConfig.from_defaults(self.download_manager.config)
        download_config.set_hops(self.download_manager.config.get("libtorrent/download_defaults/number_hops"))

        if parameters.get("files"):
            file_path_list = [Path(p) for p in parameters["files"]]
        else:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "files parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        tracker_url_list = parameters.get("trackers", [])

        if parameters.get("export_dir"):
            export_dir = Path(parameters["export_dir"])
            download_config.set_dest_dir(export_dir)

        initial_nodes = None
        if parameters.get("initial_nodes"):
            # List of format: <string><space><port>
            # regexpr groups:    1       X     2
            initial_nodes = [(t[0], int(t[1])) for node in parameters["initial_nodes"]
                             if (m := re.match("(.*) ([0-9]*$)", node)) is not None and (t := m.group(1, 2))]

        try:
            v = version("tribler")
        except PackageNotFoundError:
            v = "git"

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                create_torrent_file,
                str(download_config.get_dest_dir()),
                file_path_list,
                parameters.get("filenames"),
                parameters.get("name"),
                tracker_url_list[0] if tracker_url_list else None,
                tracker_url_list or None,
                parameters.get("description"),
                f"Tribler version: {v}",
                None,
                initial_nodes,
                0,
                None,
                getattr(TorrentVersion, parameters.get("torrent_version", "v1"))
            )
        except (OSError, UnicodeDecodeError, RuntimeError) as e:
            self._logger.exception(e)
            return return_handled_exception(e)

        await self.download_manager.start_download(tdef=TorrentDef(result["atp"]), config=download_config)

        return RESTResponse(json.dumps({"torrent": base64.b64encode(
            lt.bencode(lt.write_torrent_file(result["atp"]))  # type: ignore[attr-defined]
        ).decode()}))

    @docs(
        tags=["Libtorrent"],
        summary="Check if a torrent could be created with the given parameters.",
        parameters=[],
        responses={
            200: {
                "schema": schema(DryRunCreateTorrentResponse={"success": Boolean}),
                "examples": {"success": "true"}
            },
            HTTP_BAD_REQUEST: {
                "schema": handled_error_schema,
                "examples": {"error": {"handled": True, "message": "name already exists"}}
            }
        }
    )
    @json_schema(schema(DryRunCreateTorrentRequest={
        "name": String,
        "export_dir": String
    }))
    async def probe_writable(self, request: Request) -> RESTResponse:
        """
        Check if a torrent could be created with the given parameters.
        """
        parameters = await request.json()
        name = parameters.get("name")

        if not name:  # Empty string or None (should have been handled in the GUI)
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "invalid name"
                                }}, status=HTTP_BAD_REQUEST)

        export_dir = parameters.get("export_dir",
                                    self.download_manager.config.get("libtorrent/download_defaults/saveas"))

        path = Path(export_dir) / name
        if path.exists():
            # Attempting to overwrite an existing folder.
            return RESTResponse({"success": False})

        # The first existing parent must be writable
        writable = False
        while path.parent:
            path = path.parent
            if path.exists():
                try:
                    with TemporaryFile(dir=str(path), mode="w"):
                        pass
                    writable = True
                except OSError:
                    writable = False
                break

        return RESTResponse({"success": writable})
