from __future__ import annotations

import logging
import mimetypes
from asyncio import get_event_loop, shield
from binascii import hexlify, unhexlify
from functools import lru_cache
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, TypedDict, cast

import libtorrent as lt
from aiohttp import web
from aiohttp.web_exceptions import HTTPPartialContent, HTTPRequestRangeNotSatisfiable
from aiohttp.web_response import StreamResponse
from aiohttp_apispec import docs, json_schema
from ipv8.messaging.anonymization.tunnel import PEER_FLAG_EXIT_BT
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean, Float, Integer, List, String

from tribler.core.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.libtorrent.download_manager.download_state import DOWNLOAD, UPLOAD, DownloadStatus
from tribler.core.libtorrent.download_manager.stream import StreamReader
from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.core.notifier import Notification
from tribler.core.restapi.rest_endpoint import (
    HTTP_BAD_REQUEST,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    RESTEndpoint,
    RESTResponse,
    return_handled_exception,
)

if TYPE_CHECKING:
    from typing import Any

    from aiohttp.abc import AbstractStreamWriter, BaseRequest
    from aiohttp.web_request import Request

    from tribler.core.libtorrent.download_manager.download import Download, TrackerStatusDict
    from tribler.core.libtorrent.download_manager.download_manager import DownloadManager
    from tribler.core.libtorrent.download_manager.stream import Stream
    from tribler.core.tunnel.community import TriblerTunnelCommunity

TOTAL = "total"
LOADED = "loaded"
ALL_LOADED = "all_loaded"
logger = logging.getLogger(__name__)


class JSONFilesInfo(TypedDict):
    """
    A JSON dict to describe file info.
    """

    index: int
    name: str
    size: int
    included: bool
    progress: float


@lru_cache(maxsize=1)
def cached_read(tracker_file: str, _: int) -> list[str]:
    """
    Keep one cache for one tracker file at a time (by default: for a max of 120 seconds, see caller).

    When adding X torrents at once, this avoids reading the same file X times.
    """
    try:
        with open(tracker_file) as f:
            return [line.rstrip() for line in f if line.rstrip()]  # uTorrent format contains blank lines between URLs
    except OSError:
        logger.exception("Failed to read tracker file!")
        return []


class DownloadsEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for all requests regarding downloads. Examples include getting all downloads,
    starting, pausing and stopping downloads.
    """

    path = "/api/downloads"

    def __init__(self, download_manager: DownloadManager,
                 tunnel_community: TriblerTunnelCommunity | None = None) -> None:
        """
        Create a new endpoint to query the status of downloads.
        """
        super().__init__()
        self.download_manager = download_manager
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
        safe_seeding = bool(parameters.get('safe_seeding', download_config.get_safe_seeding()))

        if anon_hops is not None:
            if anon_hops > 0 and not safe_seeding:
                return None, "Cannot set anonymous download without safe seeding enabled"
            if anon_hops >= 0:
                download_config.set_hops(anon_hops)

        download_config.set_safe_seeding(safe_seeding)

        if 'destination' in parameters:
            download_config.set_dest_dir(parameters['destination'])

        if 'completed_dir' in parameters:
            download_config.set_completed_dir(parameters['completed_dir'])

        if 'selected_files' in parameters:
            download_config.set_selected_files(parameters['selected_files'])

        if 'auto_managed' in parameters:
            download_config.set_auto_managed(parameters['auto_managed'])

        return download_config, None

    @staticmethod
    def get_files_info_json(download: Download) -> list[JSONFilesInfo]:
        """
        Return file information as JSON from a specified download.
        """
        files_json = []
        tinfo = download.get_def().torrent_info
        if tinfo is None:
            return []
        files_completion = dict(download.get_state().get_files_completion())
        selected_files = download.config.get_selected_files()
        index_mapping = download.get_def().get_file_indices()
        for file_index in index_mapping:
            fn = Path(tinfo.file_at(file_index).path)
            if len(index_mapping) > 1:
                fn = fn.relative_to(tinfo.name())
            size = tinfo.file_at(file_index).size
            files_json.append(
                JSONFilesInfo(
                    index=file_index,
                    # We always return files in Posix format to make GUI independent of Core and simplify testing
                    name=str(fn.as_posix()),
                    size=size,
                    included=(selected_files is None or file_index in selected_files),
                    progress= files_completion.get(fn, 0.0),
                )
            )
        return files_json

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
    async def get_downloads(self, request: Request) -> RESTResponse:
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
            hex_infohash = hexlify(tdef.infohash).decode()
            if params.get("excluded") == hex_infohash:
                continue

            num_seeds, num_peers = state.get_num_seeds_peers()
            num_connected_seeds, num_connected_peers = download.get_num_connected_seeds_peers()

            tracker_info: list[TrackerStatusDict] = download.get_tracker_status()
            num_seeds_scraped = max([ti.get("seeds", 0) for ti in tracker_info]) if tracker_info else 0
            num_peers_scraped = max([ti.get("leeches", 0) for ti in tracker_info]) if tracker_info else 0
            if (num_seeds_scraped + num_peers_scraped) > (num_seeds + num_peers):
                num_seeds = num_seeds_scraped
                num_peers = num_peers_scraped

            name = tdef.name
            status = self._get_extended_status(download)

            info = {
                "name": name,
                "progress": state.get_progress(),
                "infohash": hex_infohash,
                "speed_down": state.get_current_payload_speed(DOWNLOAD),
                "speed_up": state.get_current_payload_speed(UPLOAD),
                "status": status.name,
                "status_code": status.value,
                "size": tdef.torrent_info.total_size() if tdef.torrent_info else 0,
                "eta": state.get_eta(),
                "num_peers": num_peers,
                "num_seeds": num_seeds,
                "num_connected_peers": num_connected_peers,
                "num_connected_seeds": num_connected_seeds,
                "all_time_upload": state.all_time_upload,
                "all_time_download": state.all_time_download,
                "all_time_ratio": state.get_all_time_ratio(),
                "last_upload": state.get_last_up(),
                "trackers": tracker_info,
                "hops": download.config.get_hops(),
                "anon_download": download.get_anon_mode(),
                "safe_seeding": download.config.get_safe_seeding(),
                "upload_limit": download.get_upload_limit(),
                "download_limit": download.get_download_limit(),
                "destination": str(download.config.get_dest_dir()),
                "completed_dir": str(download.config.get_completed_dir() or ""),
                "total_pieces": tdef.torrent_info.num_pieces() if tdef.torrent_info else 0,
                "error": repr(state.get_error()) if state.get_error() else "",
                "time_added": download.config.get_time_added(),
                "time_finished": download.tdef.atp.completed_time,
                # To prevent the queue_position from becoming stale, we get it directly from the download
                "queue_position": download.get_queue_position(),
                "auto_managed": download.config.get_auto_managed(),
                "user_stopped": download.config.get_user_stopped(),
                "streamable": bool(tdef and tdef.torrent_info
                                   and any(tdef.torrent_info.file_at(fi).path.endswith(("mp4", "m4v", "mov", "mkv"))
                                           for fi in range(tdef.torrent_info.num_files())))
            }

            if unfiltered or params.get("infohash") == info["infohash"]:
                # Add peers information if requested
                if get_peers:
                    info["peers"] = state.get_peer_list(include_have=False)

                # Add piece information if requested
                if get_pieces:
                    info["pieces"] = download.get_pieces_base64().decode()

                # Add availability if requested
                if get_availability:
                    info["availability"] = state.get_availability()

            result.append(info)
        return RESTResponse({"downloads": result, "checkpoints": checkpoints})

    def _get_default_trackers(self) -> list[str]:
        """
        Get the default trackers from the configured tracker file.

        Tracker file format is "(<TRACKER><NEWLINE><NEWLINE>)*". We assume "<TRACKER>" does not include newlines.
        """
        tracker_file = self.download_manager.config.get("libtorrent/download_defaults/trackers_file")
        if not tracker_file:
            return []
        return cached_read(tracker_file, int(time())//120)

    @docs(
        tags=["Libtorrent"],
        summary="Start a download from a provided URI.",
        parameters=[{
            "in": "query",
            "name": "anon_hops",
            "description": "Number of hops for the anonymous download. No hops is equivalent to a plain download",
            "type": "integer",
            "required": False
        },
            {
                "in": "query",
                "name": "safe_seeding",
                "description": "Whether the seeding of the download should be anonymous or not",
                "type": "boolean",
                "required": False
            },
            {
                "in": "query",
                "name": "destination",
                "description": "The download destination path of the torrent",
                "type": "string",
                "required": False
            },
            {
                "in": "query",
                "name": "only_metadata",
                "description": "Stop the download after the metadata has been received",
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
        "destination": (String, "The download destination path of the torrent"),
        "uri*": (String, "The URI of the torrent file that should be downloaded. This URI can either represent a file "
                         "location, a magnet link or a HTTP(S) url."),
        "cli": (Boolean, "This was invoked from CLI, we might still need to ask user permission/settings.")
    }))
    async def add_download(self, request: Request) -> RESTResponse:  # noqa: C901, PLR0912
        """
        Start a download from a provided URI.
        """
        tdef = uri = None
        if request.content_type == "applications/x-bittorrent":
            params: dict[str, str | int | list[int]] = {}
            for k, v in request.query.items():
                if k == "anon_hops":
                    params[k] = int(v)
                elif k in ["auto_managed", "safe_seeding"]:
                    params[k] = v != "false"
                else:
                    params[k] = v
            body = await request.read()

            try:
                metainfo = lt.bdecode(body)
                packed_selected_files = cast("list[int] | None",
                                             cast("dict", metainfo).pop(b"selected_files", None))
                if packed_selected_files is not None:
                    params["selected_files"] = packed_selected_files
                tdef = TorrentDef.load_from_memory(lt.bencode(metainfo))
            except Exception as e:
                return RESTResponse({"error": {"handled": True, "message": f"corrupt torrent file ({e!s})"}},
                                    status=HTTP_INTERNAL_SERVER_ERROR)
        else:
            params = await request.json()
            uri = params.get("uri")
            if not uri:
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": "uri parameter missing"
                                    }}, status=HTTP_BAD_REQUEST)

        ask_download = self.download_manager.config.get("libtorrent/ask_download_settings")
        if uri and params.get("cli") and ask_download:
            self.download_manager.notifier.notify(Notification.ask_add_download, uri=uri)
            return RESTResponse({"started": False, "infohash": ""})

        download_config, error = self.create_dconfig_from_params(params)
        if error:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": error
                                }}, status=HTTP_BAD_REQUEST)

        try:
            if tdef:
                download = await self.download_manager.start_download(tdef=tdef, config=download_config)
            else:  # guaranteed to have uri
                download = await self.download_manager.start_download_from_uri(cast("str", uri), config=download_config)
            if (self.download_manager.config.get("libtorrent/download_defaults/trackers_file")
                    and (not download.tdef.torrent_info or not download.tdef.torrent_info.priv())):
                await download.get_handle()  # We can only add trackers to a valid handle, wait for it.
                download.add_trackers(self._get_default_trackers())
            if self.download_manager.config.get("libtorrent/download_defaults/torrent_folder"):
                await download.get_handle()  # We can only generate a torrent file for a valid handle, wait for it.
                download.write_backup_torrent_file()
            if params.get("only_metadata", "false") != "false":
                download.stop_after_metainfo()
        except Exception as e:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": str(e)
                                }}, status=HTTP_INTERNAL_SERVER_ERROR)

        return RESTResponse({"started": True, "infohash": hexlify(download.get_def().infohash).decode()})

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

        return RESTResponse({"removed": True, "infohash": hexlify(download.get_def().infohash).decode()})

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
                               "parameter, however, this must be the only parameter in this request."),
        "upload_limit": (Integer, "Upload limit in bytes/s."),
        "download_limit": (Integer, "Download limit in bytes/s."),
        "queue_position": (String, "Change the position of the download in the queue. "
                                   "Possible values are queue_up/queue_top/queue_down/queue_bottom."),
        "auto_managed": (Boolean, "Set the auto managed flag.")
    }))
    async def update_download(self, request: Request) -> RESTResponse:  # noqa: C901, PLR0912, PLR0915, PLR0911
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
            return RESTResponse({"modified": True, "infohash": hexlify(download.get_def().infohash).decode()})

        if "selected_files" in parameters:
            selected_files_list = parameters["selected_files"]
            max_index = max(download.tdef.get_file_indices())
            if not all(0 <= index <= max_index for index in selected_files_list):
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": "index out of range"
                                    }}, status=HTTP_BAD_REQUEST)
            download.set_selected_files(selected_files_list)

        if upload_limit := parameters.get("upload_limit"):
            await download.set_upload_limit(upload_limit)

        if download_limit := parameters.get("download_limit"):
            await download.set_download_limit(download_limit)

        if queue_position := parameters.get("queue_position"):
            if queue_position == "queue_up":
                download.queue_position_up()
            elif queue_position == "queue_top":
                download.queue_position_top()
            elif queue_position == "queue_down":
                download.queue_position_down()
            elif queue_position == "queue_bottom":
                download.queue_position_bottom()
            else:
                return RESTResponse({"error": {
                    "handled": True,
                    "message": "invalid value for queue_position"
                }}, status=HTTP_BAD_REQUEST)

        if "auto_managed" in parameters:
            if isinstance(parameters["auto_managed"], bool):
                download.set_auto_managed(parameters["auto_managed"])
            else:
                return RESTResponse({"error": {
                    "handled": True,
                    "message": "invalid value for auto_managed"
                }}, status=HTTP_BAD_REQUEST)

        if state := parameters.get("state"):
            if state == "resume":
                download.resume()
            elif state == "stop":
                await download.stop(user_stopped=True)
            elif state == "recheck":
                download.force_recheck()
            elif state == "move_storage":
                dest_dir = Path(parameters["dest_dir"])
                completed_dir = Path(parameters.get("completed_dir") or dest_dir)
                if not dest_dir.exists() or not completed_dir.exists():
                    return RESTResponse({"error": {
                                            "handled": True,
                                            "message": f"Target directory ({dest_dir}) does not exist"
                                        }}, status=HTTP_BAD_REQUEST)
                download.move_storage(dest_dir)
                if download.get_state().get_progress() != 1:
                    download.config.set_completed_dir(completed_dir)
                else:
                    download.config.set_completed_dir(dest_dir)
                download.checkpoint()
            else:
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": "unknown state parameter"
                                    }}, status=HTTP_BAD_REQUEST)

        return RESTResponse({"modified": True, "infohash": hexlify(download.get_def().infohash).decode()})

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
            handle = cast("lt.torrent_handle", download.handle)
            handle.force_reannounce(0, len(handle.trackers()) - 1)
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
            handle = cast("lt.torrent_handle", download.handle)
            handle.replace_trackers(cast("list[dict[str, Any]]",
                                         [tracker for tracker in handle.trackers() if tracker["url"] != url]))
        except RuntimeError as e:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": str(e)
                                }}, status=HTTP_INTERNAL_SERVER_ERROR)

        download.tdef.atp.trackers = [t for t in download.tdef.atp.trackers if t != url]

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
            handle = cast("lt.torrent_handle", download.handle)
            for i, tracker in enumerate(handle.trackers()):
                if tracker["url"] == url:
                    handle.force_reannounce(0, i)
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

        return RESTResponse({
            "infohash": request.match_info["infohash"],
            "files": self.get_files_info_json(download)
        })

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

            # Are we waiting for exit nodes?
            if self.tunnel_community and not self.tunnel_community.get_candidates(PEER_FLAG_EXIT_BT):
                return DownloadStatus.EXIT_NODES

            # We're probably waiting for the DHT to be ready. See DownloadManager.dht_ready_task.
            return DownloadStatus.LOADING

        return status

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
        if not 0 <= file_index <= max(download.get_def().get_file_indices()):
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

    async def prepare(self, request: BaseRequest) -> AbstractStreamWriter | None:  # noqa: PLR0915
        """
        Prepare the response.
        """
        torrent_info = cast("lt.torrent_info", self._download.get_def().torrent_info)
        num_files = torrent_info.num_files()
        file_name = Path(torrent_info.file_at(self._file_index).path)
        if num_files > 1:
            file_name = file_name.relative_to(torrent_info.name())
        file_size = torrent_info.file_at(self._file_index).size
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
            self._download.stream = cast("Stream", self._download.stream)
        stream = self._download.stream

        start = start or 0
        await stream.enable(self._file_index)
        reader = StreamReader(stream, start)
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
                if todo <= 0 or len(data) == 0:
                    break
                data = await reader.read()

            await writer.drain()
            await writer.write_eof()
            return writer
        finally:
            await shield(get_event_loop().run_in_executor(None, reader.close))
