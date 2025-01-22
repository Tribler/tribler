from __future__ import annotations

import mimetypes
from asyncio import get_event_loop, shield, wait_for
from binascii import hexlify, unhexlify
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Optional, TypedDict, cast

import libtorrent as lt
from aiohttp import web
from aiohttp.web_exceptions import HTTPPartialContent, HTTPRequestRangeNotSatisfiable
from aiohttp.web_response import StreamResponse
from aiohttp_apispec import docs, json_schema
from ipv8.messaging.anonymization.tunnel import PEER_FLAG_EXIT_BT
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean, Float, Integer, List, String

from tribler.core.libtorrent.download_manager.download import Download, IllegalFileIndex
from tribler.core.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.libtorrent.download_manager.download_state import DOWNLOAD, UPLOAD, DownloadStatus
from tribler.core.libtorrent.download_manager.stream import Stream, StreamChunk
from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.core.restapi.rest_endpoint import (
    HTTP_BAD_REQUEST,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    RESTEndpoint,
    RESTResponse,
    return_handled_exception,
)

if TYPE_CHECKING:
    from aiohttp.abc import AbstractStreamWriter, BaseRequest, Request

    from tribler.core.database.store import MetadataStore
    from tribler.core.tunnel.community import TriblerTunnelCommunity

TOTAL = "total"
LOADED = "loaded"
ALL_LOADED = "all_loaded"


class JSONFilesInfo(TypedDict):
    """
    A JSON dict to describe file info.
    """

    index: int
    name: str
    size: int
    included: bool
    progress: float


class DownloadsEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for all requests regarding downloads. Examples include getting all downloads,
    starting, pausing and stopping downloads.
    """

    path = "/api/downloads"

    def __init__(self, download_manager: DownloadManager, metadata_store: MetadataStore | None = None,
                 tunnel_community: TriblerTunnelCommunity | None = None) -> None:
        """
        Create a new endpoint to query the status of downloads.
        """
        super().__init__()
        self.download_manager = download_manager
        self.mds = metadata_store
        self.tunnel_community = tunnel_community
        self.app.add_routes([
            web.get("", self.get_downloads),
            web.put("", self.add_download),
            web.delete("/{infohash}", self.delete_download),
            web.patch("/{infohash}", self.update_download),
            web.get("/{infohash}/torrent", self.get_torrent),
            web.put("/{infohash}/trackers", self.add_tracker),
            web.delete("/{infohash}/trackers", self.remove_tracker),
            web.put("/{infohash}/tracker_force_announce", self.tracker_force_announce),
            web.get("/{infohash}/files", self.get_files),
            web.get("/{infohash}/files/expand", self.expand_tree_directory),
            web.get("/{infohash}/files/collapse", self.collapse_tree_directory),
            web.get("/{infohash}/files/select", self.select_tree_path),
            web.get("/{infohash}/files/deselect", self.deselect_tree_path),
            web.get("/{infohash}/stream/{fileindex}", self.stream, allow_head=False)
        ])

    @staticmethod
    def return_404(message: str = "this download does not exist") -> RESTResponse:
        """
        Returns a 404 response code if your channel has not been created.
        """
        return RESTResponse({"error": {
                                "handled": True,
                                "message": message
                            }}, status=HTTP_NOT_FOUND)

    def create_dconfig_from_params(self, parameters: dict) -> tuple[DownloadConfig, None] | tuple[None, str]:
        """
        Create a download configuration based on some given parameters.

        Possible parameters are:
        - anon_hops: the number of hops for the anonymous download. 0 hops is equivalent to a plain download
        - safe_seeding: whether the seeding of the download should be anonymous or not (0 = off, 1 = on)
        - destination: the destination path of the torrent (where it is saved on disk)
        """
        download_config = DownloadConfig.from_defaults(self.download_manager.config)

        anon_hops = parameters.get('anon_hops')
        safe_seeding = bool(parameters.get('safe_seeding', 0))

        if anon_hops is not None:
            if anon_hops > 0 and not safe_seeding:
                return None, "Cannot set anonymous download without safe seeding enabled"
            if anon_hops >= 0:
                download_config.set_hops(anon_hops)

        if safe_seeding:
            download_config.set_safe_seeding(True)

        if 'destination' in parameters:
            download_config.set_dest_dir(parameters['destination'])

        if 'completed_dir' in parameters:
            download_config.set_completed_dir(parameters['completed_dir'])

        if 'selected_files' in parameters:
            download_config.set_selected_files(parameters['selected_files'])

        return download_config, None

    @staticmethod
    def get_files_info_json(download: Download) -> list[JSONFilesInfo]:
        """
        Return file information as JSON from a specified download.
        """
        files_json = []
        files_completion = dict(download.get_state().get_files_completion())
        selected_files = download.config.get_selected_files()
        for file_index, (fn, size) in enumerate(download.get_def().get_files_with_length()):
            files_json.append(cast(JSONFilesInfo, {
                "index": file_index,
                # We always return files in Posix format to make GUI independent of Core and simplify testing
                "name": str(PurePosixPath(fn)),
                "size": size,
                "included": (file_index in selected_files or not selected_files),
                "progress": files_completion.get(fn, 0.0)
            }))
        return files_json

    @staticmethod
    def get_files_info_json_paged(download: Download, view_start: Path, view_size: int) -> list[JSONFilesInfo]:
        """
        Return file info, similar to get_files_info_json() but paged (based on view_start and view_size).

        Note that the view_start path is not included in the return value.

        :param view_start: The last-known path from which to fetch new paths.
        :param view_size: The requested number of elements (though only less may be available).
        """
        if not download.tdef.torrent_info_loaded():
            download.tdef.load_torrent_info()
            return [{
                "index": IllegalFileIndex.unloaded.value,
                "name": "loading...",
                "size": 0,
                "included": False,
                "progress": 0.0
            }]
        return [
            {
                "index": download.get_file_index(path),
                "name": str(PurePosixPath(path_str)),
                "size": download.get_file_length(path),
                "included": download.is_file_selected(path),
                "progress": download.get_file_completion(path)
            }
            for path_str in download.tdef.torrent_file_tree.view(view_start, view_size)
            if (path := Path(path_str))
        ]

    @docs(
        tags=["Libtorrent"],
        summary="Return all downloads, both active and inactive",
        parameters=[{
            "in": "query",
            "name": "get_peers",
            "description": "Flag indicating whether or not to include peers",
            "type": "boolean",
            "required": False
        },
            {
                "in": "query",
                "name": "get_pieces",
                "description": "Flag indicating whether or not to include pieces",
                "type": "boolean",
                "required": False
            },
            {
                "in": "query",
                "name": "get_availability",
                "description": "Flag indicating whether or not to include availability",
                "type": "boolean",
                "required": False
            },
            {
                "in": "query",
                "name": "infohash",
                "description": "Limit fetching of files, peers, and pieces to a specific infohash",
                "type": "str",
                "required": False
            },
            {
                "in": "query",
                "name": "excluded",
                "description": "If specified, only return downloads excluding this one",
                "type": "str",
                "required": False
            }
        ],
        responses={
            200: {
                "schema": schema(DownloadsResponse={
                    "downloads": schema(Download={
                        "name": String,
                        "progress": Float,
                        "infohash": String,
                        "speed_down": Float,
                        "speed_up": Float,
                        "status": String,
                        "status_code": Integer,
                        "size": Integer,
                        "eta": Integer,
                        "num_peers": Integer,
                        "num_seeds": Integer,
                        "all_time_upload": Integer,
                        "all_time_download": Integer,
                        "all_time_ratio": Float,
                        "files": String,
                        "trackers": String,
                        "hops": Integer,
                        "anon_download": Boolean,
                        "safe_seeding": Boolean,
                        "max_upload_speed": Integer,
                        "max_download_speed": Integer,
                        "destination": String,
                        "availability": Float,
                        "peers": String,
                        "total_pieces": Integer,
                        "vod_prebuffering_progress": Float,
                        "vod_prebuffering_progress_consec": Float,
                        "error": String,
                        "time_added": Integer
                    }),
                    "checkpoints": schema(Checkpoints={
                        TOTAL: Integer,
                        LOADED: Integer,
                        ALL_LOADED: Boolean,
                    })
                }),
            }
        },
        description="This endpoint returns all downloads in Tribler, both active and inactive. The progress "
                    "is a number ranging from 0 to 1, indicating the progress of the specific state (downloading, "
                    "checking etc). The download speeds have the unit bytes/sec. The size of the torrent is given "
                    "in bytes. The estimated time assumed is given in seconds.\n\n"
                    "Detailed information about peers and pieces is only requested when the get_peers and/or "
                    "get_pieces flag is set. Note that setting this flag has a negative impact on performance "
                    "and should only be used in situations where this data is required. "
    )
    async def get_downloads(self, request: Request) -> RESTResponse:  # noqa: C901
        """
        Return all downloads, both active and inactive.
        """
        params = request.query
        get_peers = params.get('get_peers', '0') == '1'
        get_pieces = params.get('get_pieces', '0') == '1'
        get_availability = params.get('get_availability', '0') == '1'
        unfiltered = not params.get('infohash')

        checkpoints = {
            TOTAL: self.download_manager.checkpoints_count,
            LOADED: self.download_manager.checkpoints_loaded,
            ALL_LOADED: self.download_manager.all_checkpoints_are_loaded,
        }

        result = []
        downloads = self.download_manager.get_downloads()
        for download in downloads:
            if download.hidden:
                continue
            state = download.get_state()
            tdef = download.get_def()
            hex_infohash = hexlify(tdef.get_infohash()).decode()
            if params.get("excluded") == hex_infohash:
                continue

            # Create tracker information of the download
            tracker_info = []
            for url, url_info in download.get_tracker_status().items():
                tracker_info.append({"url": url, "peers": url_info[0], "status": url_info[1]})

            num_seeds, num_peers = state.get_num_seeds_peers()
            num_connected_seeds, num_connected_peers = download.get_num_connected_seeds_peers()

            name = tdef.get_name_utf8()
            status = self._get_extended_status(download)

            info = {
                "name": name,
                "progress": state.get_progress(),
                "infohash": hex_infohash,
                "speed_down": state.get_current_payload_speed(DOWNLOAD),
                "speed_up": state.get_current_payload_speed(UPLOAD),
                "status": status.name,
                "status_code": status.value,
                "size": tdef.get_length(),
                "eta": state.get_eta(),
                "num_peers": num_peers,
                "num_seeds": num_seeds,
                "num_connected_peers": num_connected_peers,
                "num_connected_seeds": num_connected_seeds,
                "all_time_upload": state.all_time_upload,
                "all_time_download": state.all_time_download,
                "all_time_ratio": state.get_all_time_ratio(),
                "trackers": tracker_info,
                "hops": download.config.get_hops(),
                "anon_download": download.get_anon_mode(),
                "safe_seeding": download.config.get_safe_seeding(),
                # Maximum upload/download rates are set for entire sessions
                "max_upload_speed": DownloadManager.get_libtorrent_max_upload_rate(self.download_manager.config),
                "max_download_speed": DownloadManager.get_libtorrent_max_download_rate(self.download_manager.config),
                "destination": str(download.config.get_dest_dir()),
                "completed_dir": download.config.get_completed_dir(),
                "total_pieces": tdef.get_nr_pieces(),
                "error": repr(state.get_error()) if state.get_error() else "",
                "time_added": download.config.get_time_added()
            }
            if download.stream:
                info.update({
                    "vod_prebuffering_progress": download.stream.prebuffprogress,
                    "vod_prebuffering_progress_consec": download.stream.prebuffprogress_consec,
                    "vod_header_progress": download.stream.headerprogress,
                    "vod_footer_progress": download.stream.footerprogress,

                })

            if unfiltered or params.get("infohash") == info["infohash"]:
                # Add peers information if requested
                if get_peers:
                    peer_list = state.get_peer_list(include_have=False)
                    for peer_info in peer_list:
                        if "extended_version" in peer_info:
                            peer_info["extended_version"] = self._safe_extended_peer_info(peer_info["extended_version"])

                    info["peers"] = peer_list

                # Add piece information if requested
                if get_pieces:
                    info["pieces"] = download.get_pieces_base64().decode()

                # Add availability if requested
                if get_availability:
                    info["availability"] = state.get_availability()

            result.append(info)
        return RESTResponse({"downloads": result, "checkpoints": checkpoints})

    @docs(
        tags=["Libtorrent"],
        summary="Start a download from a provided URI.",
        parameters=[{
            "in": "query",
            "name": "get_peers",
            "description": "Flag indicating whether or not to include peers",
            "type": "boolean",
            "required": False
        },
            {
                "in": "query",
                "name": "get_pieces",
                "description": "Flag indicating whether or not to include pieces",
                "type": "boolean",
                "required": False
            },
            {
                "in": "query",
                "name": "get_files",
                "description": "Flag indicating whether or not to include files",
                "type": "boolean",
                "required": False
            }],
        responses={
            200: {
                "schema": schema(AddDownloadResponse={"started": Boolean, "infohash": String}),
                "examples": {"started": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
            }
        },
    )
    @json_schema(schema(AddDownloadRequest={
        "anon_hops": (Integer, "Number of hops for the anonymous download. No hops is equivalent to a plain download"),
        "safe_seeding": (Boolean, "Whether the seeding of the download should be anonymous or not"),
        "destination": (String, "the download destination path of the torrent"),
        "uri*": (String, "The URI of the torrent file that should be downloaded. This URI can either represent a file "
                         "location, a magnet link or a HTTP(S) url."),
    }))
    async def add_download(self, request: Request) -> RESTResponse:  # noqa: C901
        """
        Start a download from a provided URI.
        """
        tdef = uri = None
        if request.content_type == 'applications/x-bittorrent':
            params: dict[str, str | int | list[int]] = {}
            for k, v in request.query.items():
                if k == "anon_hops":
                    params[k] = int(v)
                elif k == "safe_seeding":
                    params[k] = v != "false"
                else:
                    params[k] = v
            body = await request.read()
            metainfo = cast(dict[bytes, Any], lt.bdecode(body))
            packed_selected_files = cast(Optional[list[int]], metainfo.pop(b"selected_files", None))
            if packed_selected_files is not None:
                params["selected_files"] = packed_selected_files
            tdef = TorrentDef.load_from_dict(metainfo)
        else:
            params = await request.json()
            uri = params.get("uri")
            if not uri:
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": "uri parameter missing"
                                    }}, status=HTTP_BAD_REQUEST)

        download_config, error = self.create_dconfig_from_params(params)
        if error:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": error
                                }}, status=HTTP_BAD_REQUEST)

        try:
            if tdef:
                download = await self.download_manager.start_download(tdef=tdef, config=download_config)
            elif uri:
                download = await self.download_manager.start_download_from_uri(uri, config=download_config)
        except Exception as e:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": str(e)
                                }}, status=HTTP_INTERNAL_SERVER_ERROR)

        return RESTResponse({"started": True, "infohash": hexlify(download.get_def().get_infohash()).decode()})

    @docs(
        tags=["Libtorrent"],
        summary="Remove a specific download.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download to remove",
            "type": "string",
            "required": True
        }],
        responses={
            200: {
                "schema": schema(DeleteDownloadResponse={"removed": Boolean, "infohash": String}),
                "examples": {"removed": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
            }
        },
    )
    @json_schema(schema(RemoveDownloadRequest={
        'remove_data': (Boolean, 'Whether or not to remove the associated data'),
    }))
    async def delete_download(self, request: Request) -> RESTResponse:
        """
        Remove a specific download.
        """
        parameters = await request.json()
        if "remove_data" not in parameters:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "remove_data parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        try:
            await self.download_manager.remove_download(download, remove_content=parameters["remove_data"])
        except Exception as e:
            self._logger.exception(e)
            return return_handled_exception(e)

        return RESTResponse({"removed": True, "infohash": hexlify(download.get_def().get_infohash()).decode()})

    @docs(
        tags=["Libtorrent"],
        summary="Update a specific download.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download to update",
            "type": "string",
            "required": True
        }],
        responses={
            200: {
                "schema": schema(UpdateDownloadResponse={"modified": Boolean, "infohash": String}),
                "examples": {"modified": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
            }
        },
    )
    @json_schema(schema(UpdateDownloadRequest={
        "state": (String, "State parameter to be passed to modify the state of the download (resume/stop/recheck)"),
        "selected_files": (List(Integer), "File indexes to be included in the download"),
        "anon_hops": (Integer, "The anonymity of a download can be changed at runtime by passing the anon_hops "
                               "parameter, however, this must be the only parameter in this request.")
    }))
    async def update_download(self, request: Request) -> RESTResponse:  # noqa: C901, PLR0912, PLR0911
        """
        Update a specific download.
        """
        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        parameters = await request.json()
        if len(parameters) > 1 and "anon_hops" in parameters:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "anon_hops must be the only parameter in this request"
                                }}, status=HTTP_BAD_REQUEST)
        if 'anon_hops' in parameters:
            anon_hops = int(parameters['anon_hops'])
            try:
                await self.download_manager.update_hops(download, anon_hops)
            except Exception as e:
                self._logger.exception(e)
                return return_handled_exception(e)
            return RESTResponse({"modified": True, "infohash": hexlify(download.get_def().get_infohash()).decode()})

        if "selected_files" in parameters:
            selected_files_list = parameters["selected_files"]
            num_files = len(download.tdef.get_files())
            if not all(0 <= index < num_files for index in selected_files_list):
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": "index out of range"
                                    }}, status=HTTP_BAD_REQUEST)
            download.set_selected_files(selected_files_list)

        if parameters.get("completed_dir"):
            completed_dir = Path(parameters["completed_dir"])
            if not completed_dir.exists():
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": f"Directory ({completed_dir}) does not exist"
                                    }}, status=HTTP_BAD_REQUEST)
            download.config.set_completed_dir(completed_dir)

        if state := parameters.get("state"):
            if state == "resume":
                download.resume()
            elif state == "stop":
                await download.stop(user_stopped=True)
            elif state == "recheck":
                download.force_recheck()
            elif state == "move_storage":
                dest_dir = Path(parameters["dest_dir"])
                if not dest_dir.exists():
                    return RESTResponse({"error": {
                                            "handled": True,
                                            "message": f"Target directory ({dest_dir}) does not exist"
                                        }}, status=HTTP_BAD_REQUEST)
                download.move_storage(dest_dir)
                download.checkpoint()
            else:
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": "unknown state parameter"
                                    }}, status=HTTP_BAD_REQUEST)

        return RESTResponse({"modified": True, "infohash": hexlify(download.get_def().get_infohash()).decode()})

    @docs(
        tags=["Libtorrent"],
        summary="Return the .torrent file associated with the specified download.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download from which to get the .torrent file",
            "type": "string",
            "required": True
        }],
        responses={
            200: {'description': 'The torrent'}
        }
    )
    async def get_torrent(self, request: Request) -> RESTResponse:
        """
        Return the .torrent file associated with the specified download.
        """
        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        torrent = download.get_torrent_data()
        if not torrent:
            return DownloadsEndpoint.return_404()

        return RESTResponse(lt.bencode(torrent), headers={
            "content-type": "application/x-bittorrent",
            "Content-Disposition": f"attachment; filename={hexlify(infohash).decode()}.torrent"
        })

    @docs(
        tags=["Libtorrent"],
        summary="Add a tracker to the specified torrent.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download to add the given tracker to",
            "type": "string",
            "required": True
        }],
        responses={
            200: {
                "schema": schema(AddTrackerResponse={"added": Boolean}),
                "examples": {"added": True}
            }
        }
    )
    @json_schema(schema(AddTrackerRequest={
        "url": (String, "The tracker URL to insert"),
    }))
    async def add_tracker(self, request: Request) -> RESTResponse:
        """
        Return the .torrent file associated with the specified download.
        """
        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        parameters = await request.json()
        url = parameters.get("url")
        if not url:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "url parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        try:
            download.add_trackers([url])
            download.handle.force_reannounce(0, len(download.handle.trackers()) - 1)
        except RuntimeError as e:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": str(e)
                                }}, status=HTTP_INTERNAL_SERVER_ERROR)

        return RESTResponse({"added": True})

    @docs(
        tags=["Libtorrent"],
        summary="Remove a tracker from the specified torrent.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download to remove the given tracker from",
            "type": "string",
            "required": True
        }],
        responses={
            200: {
                "schema": schema(AddTrackerResponse={"removed": Boolean}),
                "examples": {"removed": True}
            }
        }
    )
    @json_schema(schema(AddTrackerRequest={
        "url": (String, "The tracker URL to remove"),
    }))
    async def remove_tracker(self, request: Request) -> RESTResponse:
        """
        Return the .torrent file associated with the specified download.
        """
        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        parameters = await request.json()
        url = parameters.get("url")
        if not url:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "url parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        try:
            download.handle.replace_trackers([tracker for tracker in download.handle.trackers()
                                              if tracker["url"] != url])
        except RuntimeError as e:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": str(e)
                                }}, status=HTTP_INTERNAL_SERVER_ERROR)

        if download.tdef.metainfo:
            url_bytes = url.encode()
            if download.tdef.metainfo.get(b'announce-list'):
                download.tdef.metainfo[b'announce-list'] = [e for e in download.tdef.metainfo[b'announce-list']
                                                            if e[0] != url_bytes]
            if url_bytes == download.tdef.metainfo.get(b"announce"):
                if download.tdef.metainfo.get(b'announce-list'):
                    download.tdef.metainfo[b"announce"] = download.tdef.metainfo[b'announce-list'][0][0]
                else:
                    download.tdef.metainfo.pop(b"announce")

        return RESTResponse({"removed": True})

    @docs(
        tags=["Libtorrent"],
        summary="Forcefully announce to the given tracker.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download to force the tracker announce for",
            "type": "string",
            "required": True
        }],
        responses={
            200: {
                "schema": schema(AddTrackerResponse={"forced": Boolean}),
                "examples": {"forced": True}
            }
        }
    )
    @json_schema(schema(AddTrackerRequest={
        "url": (String, "The tracker URL to query"),
    }))
    async def tracker_force_announce(self, request: Request) -> RESTResponse:
        """
        Forcefully announce to the given tracker.
        """
        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        parameters = await request.json()
        url = parameters.get("url")
        if not url:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "url parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        try:
            for i, tracker in enumerate(download.handle.trackers()):
                if tracker["url"] == url:
                    download.handle.force_reannounce(0, i)
                    break
        except RuntimeError as e:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": str(e)
                                }}, status=HTTP_INTERNAL_SERVER_ERROR)

        return RESTResponse({"forced": True})

    @docs(
        tags=["Libtorrent"],
        summary="Return file information of a specific download.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download to from which to get file information",
            "type": "string",
            "required": True
        },
            {
                "in": "query",
                "name": "view_start_path",
                "description": "Path of the file or directory to form a view for",
                "type": "string",
                "required": False
            },
            {
                "in": "query",
                "name": "view_size",
                "description": "Number of files to include in the view",
                "type": "number",
                "required": False
            }],
        responses={
            200: {
                "schema": schema(GetFilesResponse={"files": [schema(File={"index": Integer,
                                                                          "name": String,
                                                                          "size": Integer,
                                                                          "included": Boolean,
                                                                          "progress": Float})]})
            }
        }
    )
    async def get_files(self, request: Request) -> RESTResponse:
        """
        Return file information of a specific download.
        """
        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        params = request.query
        view_start_path = params.get("view_start_path")
        if view_start_path is None:
            return RESTResponse({
                "infohash": request.match_info["infohash"],
                "files": self.get_files_info_json(download)
            })

        view_size = int(params.get("view_size", "100"))
        return RESTResponse({
            "infohash": request.match_info["infohash"],
            "query": view_start_path,
            "files": self.get_files_info_json_paged(download, Path(view_start_path), view_size)
        })

    @docs(
        tags=["Libtorrent"],
        summary="Collapse a tree directory.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download",
            "type": "string",
            "required": True
        },
            {
                "in": "query",
                "name": "path",
                "description": "Path of the directory to collapse",
                "type": "string",
                "required": True
            }],
        responses={
            200: {
                "schema": schema(File={"path": path})
            }
        }
    )
    async def collapse_tree_directory(self, request: Request) -> RESTResponse:
        """
        Collapse a tree directory.
        """
        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        params = request.query
        path = params.get("path")
        if not path:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "path parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        download.tdef.torrent_file_tree.collapse(Path(path))

        return RESTResponse({"path": path})

    @docs(
        tags=["Libtorrent"],
        summary="Expand a tree directory.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download",
            "type": "string",
            "required": True
        },
            {
                "in": "query",
                "name": "path",
                "description": "Path of the directory to expand",
                "type": "string",
                "required": True
            }],
        responses={
            200: {
                "schema": schema(File={"path": String})
            }
        }
    )
    async def expand_tree_directory(self, request: Request) -> RESTResponse:
        """
        Expand a tree directory.
        """
        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        params = request.query
        path = params.get("path")
        if not path:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "path parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        download.tdef.torrent_file_tree.expand(Path(path))

        return RESTResponse({"path": path})

    @docs(
        tags=["Libtorrent"],
        summary="Select a tree path.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download",
            "type": "string",
            "required": True
        },
            {
                "in": "query",
                "name": "path",
                "description": "Path of the directory to select",
                "type": "string",
                "required": True
            }],
        responses={
            200: {}
        }
    )
    async def select_tree_path(self, request: Request) -> RESTResponse:
        """
        Select a tree path.
        """
        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        params = request.query
        path = params.get("path")
        if not path:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "path parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        download.set_selected_file_or_dir(Path(path), True)

        return RESTResponse({})

    @docs(
        tags=["Libtorrent"],
        summary="Deselect a tree path.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download",
            "type": "string",
            "required": True
        },
            {
                "in": "query",
                "name": "path",
                "description": "Path of the directory to deselect",
                "type": "string",
                "required": True
            }],
        responses={
            200: {}
        }
    )
    async def deselect_tree_path(self, request: Request) -> RESTResponse:
        """
        Deselect a tree path.
        """
        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        params = request.query
        path = params.get("path")
        if not path:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "path parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        download.set_selected_file_or_dir(Path(path), False)

        return RESTResponse({})

    def _get_extended_status(self, download: Download) -> DownloadStatus:
        """
        This function filters the original download status to possibly add tunnel-related status.
        Extracted from DownloadState to remove coupling between DownloadState and Tunnels.
        """
        state = download.get_state()
        status = state.get_status()

        # Nothing to do with tunnels. If stopped - it happened by the user or libtorrent-only reason
        stopped_by_user = state.lt_status and state.lt_status.paused

        if status == DownloadStatus.STOPPED and not stopped_by_user:
            if download.config.get_hops() == 0:
                return DownloadStatus.STOPPED

            if self.tunnel_community and self.tunnel_community.get_candidates(PEER_FLAG_EXIT_BT):
                return DownloadStatus.CIRCUITS

            return DownloadStatus.EXIT_NODES

        return status

    def _safe_extended_peer_info(self, ext_peer_info: bytes) -> str:
        """
        Given a string describing peer info, return a json.dumps() safe representation.

        :param ext_peer_info: the string to convert to a dumpable format
        :return: the safe string
        """
        # First see if we can use this as-is
        if not ext_peer_info:
            return ""

        try:
            return ext_peer_info.decode()
        except UnicodeDecodeError as e:
            # We might have some special unicode characters in here
            self._logger.warning("Error while decoding peer info: %s. %s: %s",
                                 str(ext_peer_info), e.__class__.__name__, str(e))
            return ''.join(map(chr, ext_peer_info))

    @docs(
        tags=["Libtorrent"],
        summary="Stream the contents of a file that is being downloaded.",
        parameters=[{
            "in": "path",
            "name": "infohash",
            "description": "Infohash of the download to stream",
            "type": "string",
            "required": True
        },
            {
                "in": "path",
                "name": "fileindex",
                "description": "The fileindex to stream",
                "type": "string",
                "required": True
            }],
        responses={
            206: {"description": "Contents of the stream"}
        }
    )
    async def stream(self, request: Request) -> web.StreamResponse:
        """
        Stream the contents of a file that is being downloaded.
        """
        infohash = unhexlify(request.match_info["infohash"])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404()

        file_index = int(request.match_info["fileindex"])
        if not 0 <= file_index < len(download.get_def().get_files()):
            return DownloadsEndpoint.return_404()

        return TorrentStreamResponse(download, file_index)


class TorrentStreamResponse(StreamResponse):
    """A response object to stream the contents of a download."""

    def __init__(self, download: Download, file_index: int, **kwargs) -> None:
        """
        Create a new TorrentStreamResponse.
        """
        super().__init__(**kwargs)
        self._download = download
        self._file_index = file_index

    async def prepare(self, request: BaseRequest) -> AbstractStreamWriter | None:
        """
        Prepare the response.
        """
        file_name, file_size = self._download.get_def().get_files_with_length()[self._file_index]
        try:
            start = request.http_range.start
            stop = request.http_range.stop
        except ValueError:
            self.headers["Content-Range"] = f"bytes */{file_size}"
            self.set_status(HTTPRequestRangeNotSatisfiable.status_code)
            return await super().prepare(request)

        todo = file_size
        if start is not None or stop is not None:
            if start < 0:
                start += file_size
                start = max(start, 0)
            stop = min(stop if stop is not None else file_size, file_size)
            todo = stop - start

            if start >= file_size:
                self.headers["Content-Range"] = f"bytes */{file_size}"
                self.set_status(HTTPRequestRangeNotSatisfiable.status_code)
                return await super().prepare(request)

            self.headers["Content-Range"] = f"bytes {start}-{start + todo - 1}/{file_size}"
            self.set_status(HTTPPartialContent.status_code)

        content_type, _ = mimetypes.guess_type(str(file_name))
        self.content_type = content_type or "application/octet-stream"
        self.content_length = todo
        self.headers["Accept-Ranges"] = "bytes"

        if self._download.stream is None:
            self._download.add_stream()
            self._download.stream = cast(Stream, self._download.stream)
        stream = self._download.stream

        start = start or 0
        if not stream.enabled or stream.fileindex != self._file_index:
            await wait_for(stream.enable(self._file_index, start), 10)
            await stream.updateprios()

        reader = StreamChunk(self._download.stream, start)
        await reader.open()
        try:
            writer = await super().prepare(request)
            assert writer is not None

            await reader.seek(start)
            # Note that the chuck size is the same as the underlying torrent's piece length
            data = await reader.read()
            while data:
                await writer.write(data[:todo])
                todo -= len(data)
                if todo <= 0:
                    break
                data = await reader.read()

            await writer.drain()
            await writer.write_eof()
            return writer
        finally:
            await shield(get_event_loop().run_in_executor(None, reader.close))
