import base64
import json

from aiohttp import web

from aiohttp_apispec import docs, json_schema

from ipv8.REST.schema import schema

from marshmallow.fields import String

from tribler_core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler_core.components.libtorrent.torrentdef import TorrentDef
from tribler_core.components.restapi.rest.rest_endpoint import HTTP_BAD_REQUEST, RESTEndpoint, RESTResponse
from tribler_core.components.restapi.rest.schema import HandledErrorSchema
from tribler_core.components.restapi.rest.util import return_handled_exception
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.unicode import ensure_unicode, recursive_bytes
from tribler_core.utilities.utilities import bdecode_compat, froze_it


@froze_it
class CreateTorrentEndpoint(RESTEndpoint):
    """
    Create a torrent file from local files.
    See: http://www.bittorrent.org/beps/bep_0012.html
    """

    def __init__(self):
        super().__init__()
        self.download_manager = None

    def setup_routes(self):
        self.app.add_routes([web.post('', self.create_torrent)])

    @docs(
        tags=["Libtorrent"],
        summary="Create a torrent from local files and return it in base64 encoding.",
        parameters=[{
            'in': 'query',
            'name': 'download',
            'description': 'Flag indicating whether or not to start downloading',
            'type': 'boolean',
            'required': False
        }],
        responses={
            200: {
                "schema": schema(CreateTorrentResponse={'torrent': 'base64 encoded torrent file'}),
                "examples": {'Success': {"success": True}}
            },
            HTTP_BAD_REQUEST: {
                "schema": HandledErrorSchema,
                "examples": {"Error": {"error": "files parameter missing"}}
            }
        }
    )
    @json_schema(schema(CreateTorrentRequest={
        'files': [String],
        'name': String,
        'description': String,
        'trackers': [String],
        'export_dir': String
    }))
    async def create_torrent(self, request):
        parameters = await request.json()
        params = {}

        if 'files' in parameters and parameters['files']:
            file_path_list = [ensure_unicode(f, 'utf-8') for f in parameters['files']]
        else:
            return RESTResponse({"error": "files parameter missing"}, status=HTTP_BAD_REQUEST)

        if 'description' in parameters and parameters['description']:
            params['comment'] = parameters['description']

        if 'trackers' in parameters and parameters['trackers']:
            tracker_url_list = parameters['trackers']
            params['announce'] = tracker_url_list[0]
            params['announce-list'] = tracker_url_list

        name = 'unknown'
        if 'name' in parameters and parameters['name']:
            name = parameters['name']
            params['name'] = name

        export_dir = None
        if 'export_dir' in parameters and parameters['export_dir']:
            export_dir = Path(parameters['export_dir'])

        from tribler_core.version import version_id
        params['created by'] = f"Tribler version: {version_id}"

        params['nodes'] = False
        params['httpseeds'] = False
        params['encoding'] = False
        params['piece length'] = 0  # auto

        try:
            result = await self.download_manager.create_torrent_file(file_path_list, recursive_bytes(params))
        except (OSError, UnicodeDecodeError, RuntimeError) as e:
            self._logger.exception(e)
            return return_handled_exception(request, e)

        metainfo_dict = bdecode_compat(result['metainfo'])

        if export_dir and export_dir.exists():
            save_path = export_dir / (f"{name}.torrent")
            with open(save_path, "wb") as fd:
                fd.write(result['metainfo'])

        # Download this torrent if specified
        if 'download' in request.query and request.query['download'] and request.query['download'] == "1":
            download_config = DownloadConfig()
            download_config.set_dest_dir(result['base_path'] if len(file_path_list) == 1 else result['base_dir'])
            download_config.set_hops(self.download_manager.download_defaults.number_hops)
            self.download_manager.start_download(tdef=TorrentDef(metainfo_dict), config=download_config)

        return RESTResponse(json.dumps({"torrent": base64.b64encode(result['metainfo']).decode('utf-8')}))
