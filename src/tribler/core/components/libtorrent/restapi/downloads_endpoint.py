from binascii import unhexlify
from pathlib import PurePosixPath

from aiohttp import web
from aiohttp_apispec import docs, json_schema
from ipv8.REST.schema import schema
from ipv8.messaging.anonymization.tunnel import PEER_FLAG_EXIT_BT
from marshmallow.fields import Boolean, Float, Integer, List, String

from tribler.core.components.database.db.store import MetadataStore
from tribler.core.components.libtorrent.download_manager.download import Download, IllegalFileIndex
from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.utils.libtorrent_helper import libtorrent as lt
from tribler.core.components.restapi.rest.rest_endpoint import (
    HTTP_BAD_REQUEST,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    RESTEndpoint,
    RESTResponse,
)
from tribler.core.components.restapi.rest.utils import return_handled_exception
from tribler.core.components.tunnel.community.tunnel_community import TriblerTunnelCommunity
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.simpledefs import (
    DOWNLOAD,
    DownloadStatus, UPLOAD,
)
from tribler.core.utilities.unicode import ensure_unicode, hexlify
from tribler.core.utilities.utilities import froze_it

TOTAL = 'total'
LOADED = 'loaded'
ALL_LOADED = 'all_loaded'


@froze_it
class DownloadsEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for all requests regarding downloads. Examples include getting all downloads,
    starting, pausing and stopping downloads.
    """
    path = '/downloads'

    def __init__(self, download_manager: DownloadManager, metadata_store: MetadataStore,
                 tunnel_community: TriblerTunnelCommunity):
        super().__init__()
        self.download_manager = download_manager
        self.mds = metadata_store
        self.tunnel_community = tunnel_community

    def setup_routes(self):
        self.app.add_routes([
            web.get('', self.get_downloads),
            web.put('', self.add_download),
            web.delete('/{infohash}', self.delete_download),
            web.patch('/{infohash}', self.update_download),
            web.get('/{infohash}/torrent', self.get_torrent),
            web.get('/{infohash}/files', self.get_files),
            web.get('/{infohash}/files/expand', self.expand_tree_directory),
            web.get('/{infohash}/files/collapse', self.collapse_tree_directory),
            web.get('/{infohash}/files/select', self.select_tree_path),
            web.get('/{infohash}/files/deselect', self.deselect_tree_path),
        ])

    @staticmethod
    def return_404(request, message="this download does not exist"):
        """
        Returns a 404 response code if your channel has not been created.
        """
        return RESTResponse({"error": message}, status=HTTP_NOT_FOUND)

    @staticmethod
    def create_dconfig_from_params(parameters):
        """
        Create a download configuration based on some given parameters. Possible parameters are:
        - anon_hops: the number of hops for the anonymous download. 0 hops is equivalent to a plain download
        - safe_seeding: whether the seeding of the download should be anonymous or not (0 = off, 1 = on)
        - destination: the destination path of the torrent (where it is saved on disk)
        """
        download_config = DownloadConfig()

        anon_hops = parameters.get('anon_hops', 0)
        safe_seeding = bool(parameters.get('safe_seeding', 0))

        if anon_hops > 0 and not safe_seeding:
            return None, "Cannot set anonymous download without safe seeding enabled"

        if anon_hops > 0:
            download_config.set_hops(anon_hops)

        if safe_seeding:
            download_config.set_safe_seeding(True)

        if 'destination' in parameters:
            download_config.set_dest_dir(parameters['destination'])

        if 'selected_files' in parameters:
            download_config.set_selected_files(parameters['selected_files'])

        return download_config, None

    @staticmethod
    def get_files_info_json(download):
        """
        Return file information as JSON from a specified download.
        """
        files_json = []
        files_completion = {name: progress for name, progress in download.get_state().get_files_completion()}
        selected_files = download.config.get_selected_files()
        file_index = 0
        for fn, size in download.get_def().get_files_with_length():
            files_json.append({
                "index": file_index,
                # We always return files in Posix format to make GUI independent of Core and simplify testing
                "name": str(PurePosixPath(fn)),
                "size": size,
                "included": (file_index in selected_files or not selected_files),
                "progress": files_completion.get(fn, 0.0)
            })
            file_index += 1
        return files_json

    @staticmethod
    def get_files_info_json_paged(download: Download, view_start: Path, view_size: int):
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
                "included": 0,
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
        parameters=[
            {
                'in': 'query',
                'name': 'get_peers',
                'description': 'Flag indicating whether or not to include peers',
                'type': 'boolean',
                'required': False
            },
            {
                'in': 'query',
                'name': 'get_pieces',
                'description': 'Flag indicating whether or not to include pieces',
                'type': 'boolean',
                'required': False
            },
            {
                'in': 'query',
                'name': 'get_availability',
                'description': 'Flag indicating whether or not to include availability',
                'type': 'boolean',
                'required': False
            },
            {
                'in': 'query',
                'name': 'infohash',
                'description': 'If specified only return the download with the given infohash',
                'type': 'str',
                'required': False
            },
            {
                'in': 'query',
                'name': 'excluded',
                'description': 'If specified, only return downloads excluding this one',
                'type': 'str',
                'required': False
            },
        ],
        responses={
            200: {
                "schema": schema(DownloadsResponse={
                    'downloads': schema(Download={
                        'name': String,
                        'progress': Float,
                        'infohash': String,
                        'speed_down': Float,
                        'speed_up': Float,
                        'status': String,
                        'status_code': Integer,
                        'size': Integer,
                        'eta': Integer,
                        'num_peers': Integer,
                        'num_seeds': Integer,
                        'all_time_upload': Integer,
                        'all_time_download': Integer,
                        'all_time_ratio': Float,
                        'files': String,
                        'trackers': String,
                        'hops': Integer,
                        'anon_download': Boolean,
                        'safe_seeding': Boolean,
                        'max_upload_speed': Integer,
                        'max_download_speed': Integer,
                        'destination': String,
                        'availability': Float,
                        'peers': String,
                        'total_pieces': Integer,
                        'error': String,
                        'time_added': Integer
                    }),
                    'checkpoints': schema(Checkpoints={
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
    async def get_downloads(self, request):
        params = request.query
        get_peers = params.get('get_peers')
        get_pieces = params.get('get_pieces')
        get_availability = params.get('get_availability')
        infohash = params.get('infohash')
        excluded = params.get('excluded')

        checkpoints = {
            TOTAL: self.download_manager.checkpoints_count,
            LOADED: self.download_manager.checkpoints_loaded,
            ALL_LOADED: self.download_manager.all_checkpoints_are_loaded,
        }

        if not self.download_manager.all_checkpoints_are_loaded:
            return RESTResponse({"downloads": [], "checkpoints": checkpoints})

        result = []
        downloads = (d for d in self.download_manager.get_downloads() if not d.hidden)
        if infohash:
            downloads = (d for d in downloads if d.tdef.get_infohash_hex() == infohash)
        if excluded:
            downloads = (d for d in downloads if d.tdef.get_infohash_hex() != excluded)

        for download in downloads:
            state = download.get_state()
            tdef = download.get_def()

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
                "infohash": tdef.get_infohash_hex(),
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
                "total_pieces": tdef.get_nr_pieces(),
                "error": repr(state.get_error()) if state.get_error() else "",
                "time_added": download.config.get_time_added()
            }

            if get_availability:
                info["availability"] = state.get_availability()

            if get_peers:
                peer_list = state.get_peer_list(include_have=False)
                for peer_info in peer_list:
                    if 'extended_version' in peer_info:
                        peer_info['extended_version'] = self._safe_extended_peer_info(peer_info['extended_version'])

                info["peers"] = peer_list

            if get_pieces:
                info["pieces"] = download.get_pieces_base64().decode('utf-8')

            result.append(info)

        return RESTResponse({"downloads": result, "checkpoints": checkpoints})

    @docs(
        tags=["Libtorrent"],
        summary="Start a download from a provided URI.",
        parameters=[{
            'in': 'query',
            'name': 'get_peers',
            'description': 'Flag indicating whether or not to include peers',
            'type': 'boolean',
            'required': False
        },
            {
                'in': 'query',
                'name': 'get_pieces',
                'description': 'Flag indicating whether or not to include pieces',
                'type': 'boolean',
                'required': False
            },
            {
                'in': 'query',
                'name': 'get_files',
                'description': 'Flag indicating whether or not to include files',
                'type': 'boolean',
                'required': False
            }],
        responses={
            200: {
                "schema": schema(AddDownloadResponse={"started": Boolean, "infohash": String}),
                'examples': {"started": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
            }
        },
    )
    @json_schema(schema(AddDownloadRequest={
        'anon_hops': (Integer, 'Number of hops for the anonymous download. No hops is equivalent to a plain download'),
        'safe_seeding': (Boolean, 'Whether the seeding of the download should be anonymous or not'),
        'destination': (String, 'the download destination path of the torrent'),
        'uri*': (String, 'The URI of the torrent file that should be downloaded. This URI can either represent a file '
                         'location, a magnet link or a HTTP(S) url.'),
    }))
    async def add_download(self, request):
        params = await request.json()
        uri = params.get('uri')
        if not uri:
            return RESTResponse({"error": "uri parameter missing"}, status=HTTP_BAD_REQUEST)

        download_config, error = DownloadsEndpoint.create_dconfig_from_params(params)
        if error:
            return RESTResponse({"error": error}, status=HTTP_BAD_REQUEST)

        try:
            download = await self.download_manager.start_download_from_uri(uri, config=download_config)
        except Exception as e:
            return RESTResponse({"error": str(e)}, status=HTTP_INTERNAL_SERVER_ERROR)

        return RESTResponse({"started": True, "infohash": hexlify(download.get_def().get_infohash())})

    @docs(
        tags=["Libtorrent"],
        summary="Remove a specific download.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download to remove',
            'type': 'string',
            'required': True
        }],
        responses={
            200: {
                "schema": schema(DeleteDownloadResponse={"removed": Boolean, "infohash": String}),
                'examples': {"removed": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
            }
        },
    )
    @json_schema(schema(RemoveDownloadRequest={
        'remove_data': (Boolean, 'Whether or not to remove the associated data'),
    }))
    async def delete_download(self, request):
        parameters = await request.json()
        if 'remove_data' not in parameters:
            return RESTResponse({"error": "remove_data parameter missing"}, status=HTTP_BAD_REQUEST)

        infohash = unhexlify(request.match_info['infohash'])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        try:
            await self.download_manager.remove_download(download, remove_content=parameters['remove_data'])
        except Exception as e:
            self._logger.exception(e)
            return return_handled_exception(request, e)

        return RESTResponse({"removed": True, "infohash": hexlify(download.get_def().get_infohash())})

    @docs(
        tags=["Libtorrent"],
        summary="Update a specific download.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download to update',
            'type': 'string',
            'required': True
        }],
        responses={
            200: {
                "schema": schema(UpdateDownloadResponse={"modified": Boolean, "infohash": String}),
                'examples': {"modified": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
            }
        },
    )
    @json_schema(schema(UpdateDownloadRequest={
        'state': (String, 'State parameter to be passed to modify the state of the download (resume/stop/recheck)'),
        'selected_files': (List(Integer), 'File indexes to be included in the download'),
        'anon_hops': (Integer, 'The anonymity of a download can be changed at runtime by passing the anon_hops '
                               'parameter, however, this must be the only parameter in this request.')
    }))
    async def update_download(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        parameters = await request.json()

        if len(parameters) > 1 and 'anon_hops' in parameters:
            return RESTResponse({"error": "anon_hops must be the only parameter in this request"},
                                status=HTTP_BAD_REQUEST)
        elif 'anon_hops' in parameters:
            anon_hops = int(parameters['anon_hops'])
            try:
                await self.download_manager.update_hops(download, anon_hops)
            except Exception as e:
                self._logger.exception(e)
                return return_handled_exception(request, e)
            return RESTResponse({"modified": True, "infohash": hexlify(download.get_def().get_infohash())})

        if 'selected_files' in parameters:
            selected_files_list = parameters['selected_files']
            num_files = len(download.tdef.get_files())
            if not all([0 <= index < num_files for index in selected_files_list]):
                return RESTResponse({"error": "index out of range"}, status=HTTP_BAD_REQUEST)
            download.set_selected_files(selected_files_list)

        if state := parameters.get('state'):
            if state == "resume":
                download.resume()
            elif state == "stop":
                await download.stop(user_stopped=True)
            elif state == "recheck":
                download.force_recheck()
            elif state == "move_storage":
                dest_dir = Path(parameters['dest_dir'])
                if not dest_dir.exists():
                    return RESTResponse({"error": f"Target directory ({dest_dir}) does not exist"})
                download.move_storage(dest_dir)
                download.checkpoint()
            else:
                return RESTResponse({"error": "unknown state parameter"}, status=HTTP_BAD_REQUEST)

        return RESTResponse({"modified": True, "infohash": hexlify(download.get_def().get_infohash())})

    @docs(
        tags=["Libtorrent"],
        summary="Return the .torrent file associated with the specified download.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download from which to get the .torrent file',
            'type': 'string',
            'required': True
        }],
        responses={
            200: {'description': 'The torrent'}
        }
    )
    async def get_torrent(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        torrent = download.get_torrent_data()
        if not torrent:
            return DownloadsEndpoint.return_404(request)

        return RESTResponse(lt.bencode(torrent), headers={'content-type': 'application/x-bittorrent',
                                                          'Content-Disposition': 'attachment; filename=%s.torrent'
                                                                                 % hexlify(infohash).encode('utf-8')})

    @docs(
        tags=["Libtorrent"],
        summary="Return file information of a specific download.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download to from which to get file information',
            'type': 'string',
            'required': True
        },
            {
                'in': 'query',
                'name': 'view_start_path',
                'description': 'Path of the file or directory to form a view for',
                'type': 'string',
                'required': False
            },
            {
                'in': 'query',
                'name': 'view_size',
                'description': 'Number of files to include in the view',
                'type': 'number',
                'required': False
            }],
        responses={
            200: {
                "schema": schema(GetFilesResponse={"files": [schema(File={'index': Integer,
                                                                          'name': String,
                                                                          'size': Integer,
                                                                          'included': Boolean,
                                                                          'progress': Float})]})
            }
        }
    )
    async def get_files(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        params = request.query
        view_start_path = params.get('view_start_path')
        if view_start_path is None:
            return RESTResponse({
                "infohash": request.match_info['infohash'],
                "files": self.get_files_info_json(download)
            })

        view_size = int(params.get('view_size', '100'))
        return RESTResponse({
            "infohash": request.match_info['infohash'],
            "query": view_start_path,
            "files": self.get_files_info_json_paged(download, Path(view_start_path), view_size)
        })

    @docs(
        tags=["Libtorrent"],
        summary="Collapse a tree directory.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download',
            'type': 'string',
            'required': True
        },
            {
                'in': 'query',
                'name': 'path',
                'description': 'Path of the directory to collapse',
                'type': 'string',
                'required': True
            }],
        responses={
            200: {
                "schema": schema(File={'path': path})
            }
        }
    )
    async def collapse_tree_directory(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        params = request.query
        path = params.get('path')
        download.tdef.torrent_file_tree.collapse(Path(path))

        return RESTResponse({'path': path})

    @docs(
        tags=["Libtorrent"],
        summary="Expand a tree directory.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download',
            'type': 'string',
            'required': True
        },
            {
                'in': 'query',
                'name': 'path',
                'description': 'Path of the directory to expand',
                'type': 'string',
                'required': True
            }],
        responses={
            200: {
                "schema": schema(File={'path': String})
            }
        }
    )
    async def expand_tree_directory(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        params = request.query
        path = params.get('path')
        download.tdef.torrent_file_tree.expand(Path(path))

        return RESTResponse({'path': path})

    @docs(
        tags=["Libtorrent"],
        summary="Select a tree path.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download',
            'type': 'string',
            'required': True
        },
            {
                'in': 'query',
                'name': 'path',
                'description': 'Path of the directory to select',
                'type': 'string',
                'required': True
            }],
        responses={
            200: {}
        }
    )
    async def select_tree_path(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        params = request.query
        path = params.get('path')
        download.set_selected_file_or_dir(Path(path), True)

        return RESTResponse({})

    @docs(
        tags=["Libtorrent"],
        summary="Deselect a tree path.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download',
            'type': 'string',
            'required': True
        },
            {
                'in': 'query',
                'name': 'path',
                'description': 'Path of the directory to deselect',
                'type': 'string',
                'required': True
            }],
        responses={
            200: {}
        }
    )
    async def deselect_tree_path(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.download_manager.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        params = request.query
        path = params.get('path')
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
            if download.config.get_hops() <= 0:
                return DownloadStatus.STOPPED

            if self.tunnel_community.get_candidates(PEER_FLAG_EXIT_BT):
                return DownloadStatus.CIRCUITS

            return DownloadStatus.EXIT_NODES

        return status

    def _safe_extended_peer_info(self, ext_peer_info):
        """
        Given a string describing peer info, return a json.dumps() safe representation.

        :param ext_peer_info: the string to convert to a dumpable format
        :return: the safe string
        """
        # First see if we can use this as-is
        if not ext_peer_info:
            return ""

        try:
            return ensure_unicode(ext_peer_info, "utf8")
        except UnicodeDecodeError as e:
            # We might have some special unicode characters in here
            self._logger.warning(f'Error while decoding peer info: {ext_peer_info}. {e.__class__.__name__}: {e}')

        return ''.join(map(chr, ext_peer_info))
