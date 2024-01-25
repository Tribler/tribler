import hashlib
import json
from copy import deepcopy

from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from marshmallow.fields import String

from tribler.core import notifications
from tribler.core.components.database.db.orm_bindings.torrent_metadata import tdef_to_metadata_dict
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.libtorrent.utils.libtorrent_helper import libtorrent as lt
from tribler.core.components.restapi.rest.rest_endpoint import (
    HTTP_BAD_REQUEST,
    HTTP_INTERNAL_SERVER_ERROR,
    RESTEndpoint,
    RESTResponse,
)
from tribler.core.utilities.aiohttp.aiohttp_utils import query_uri, unshorten
from tribler.core.utilities.aiohttp.exceptions import AiohttpException
from tribler.core.utilities.rest_utils import (
    FILE_SCHEME,
    HTTPS_SCHEME,
    HTTP_SCHEME,
    MAGNET_SCHEME,
    scheme_from_url,
    url_to_path,
)
from tribler.core.utilities.unicode import hexlify, recursive_unicode
from tribler.core.utilities.utilities import bdecode_compat, froze_it, parse_magnetlink


@froze_it
class TorrentInfoEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing all requests regarding torrent info in Tribler.
    """
    path = '/torrentinfo'

    def __init__(self, download_manager: DownloadManager):
        super().__init__()
        self.download_manager = download_manager

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_torrent_info)])

    @docs(
        tags=["Libtorrent"],
        summary="Return metainfo from a torrent found at a provided URI.",
        parameters=[{
            'in': 'query',
            'name': 'torrent',
            'description': 'URI for which to return torrent information. This URI can either represent '
                           'a file location, a magnet link or a HTTP(S) url.',
            'type': 'string',
            'required': True
        }],
        responses={
            200: {
                'description': 'Return a hex-encoded json-encoded string with torrent metainfo',
                "schema": schema(GetMetainfoResponse={'metainfo': String})
            }
        }
    )
    async def get_torrent_info(self, request):
        params = request.query
        hops = params.get('hops')
        uri = params.get('uri')
        self._logger.info(f'URI: {uri}')
        if hops:
            try:
                hops = int(hops)
            except ValueError:
                return RESTResponse({"error": f"wrong value of 'hops' parameter: {hops}"}, status=HTTP_BAD_REQUEST)

        if not uri:
            return RESTResponse({"error": "uri parameter missing"}, status=HTTP_BAD_REQUEST)

        uri = await unshorten(uri)
        scheme = scheme_from_url(uri)

        if scheme == FILE_SCHEME:
            file = url_to_path(uri)
            try:
                tdef = await TorrentDef.load(file)
                metainfo = tdef.metainfo
            except (FileNotFoundError, TypeError, ValueError, RuntimeError):
                return RESTResponse({"error": f"error while decoding torrent file: {file}"},
                                    status=HTTP_INTERNAL_SERVER_ERROR)
        elif scheme in (HTTP_SCHEME, HTTPS_SCHEME):
            try:
                response = await query_uri(uri)
            except AiohttpException as e:
                return RESTResponse({"error": str(e)}, status=HTTP_INTERNAL_SERVER_ERROR)

            if response.startswith(b'magnet'):
                try:
                    _, infohash, _ = parse_magnetlink(response)
                except RuntimeError as e:
                    return RESTResponse(
                        {"error": f'Error while getting an infohash from magnet: {e.__class__.__name__}: {e}'},
                        status=HTTP_INTERNAL_SERVER_ERROR
                    )
                url = response.decode("utf-8")
                metainfo = await self.download_manager.get_metainfo(infohash, timeout=60, hops=hops, url=url)
            else:
                metainfo = bdecode_compat(response)
        elif scheme == MAGNET_SCHEME:
            self._logger.info(f'{MAGNET_SCHEME} scheme detected')

            try:
                _, infohash, _ = parse_magnetlink(uri)
            except RuntimeError as e:
                return RESTResponse(
                    {"error": f'Error while getting an infohash from magnet: {e.__class__.__name__}: {e}'},
                    status=HTTP_BAD_REQUEST
                )

            metainfo = await self.download_manager.get_metainfo(infohash, timeout=60, hops=hops, url=uri)
        else:
            return RESTResponse({"error": "invalid uri"}, status=HTTP_BAD_REQUEST)

        if not metainfo:
            return RESTResponse({"error": "metainfo error"}, status=HTTP_INTERNAL_SERVER_ERROR)

        if not isinstance(metainfo, dict) or b'info' not in metainfo:
            self._logger.warning("Received metainfo is not a valid dictionary")
            return RESTResponse({"error": "invalid response"}, status=HTTP_INTERNAL_SERVER_ERROR)

        # Add the torrent to metadata.db
        torrent_def = TorrentDef.load_from_dict(metainfo)
        metadata_dict = tdef_to_metadata_dict(torrent_def)
        self.download_manager.notifier[notifications.torrent_metadata_added](metadata_dict)

        infohash = metadata_dict['infohash']
        download = self.download_manager.downloads.get(infohash)
        metainfo_request = self.download_manager.metainfo_requests.get(infohash, [None])[0]
        download_is_metainfo_request = download == metainfo_request

        # Check if the torrent is already in the downloads
        encoded_metainfo = deepcopy(metainfo)

        ready_for_unicode = recursive_unicode(encoded_metainfo, ignore_errors=True)
        json_dump = json.dumps(ready_for_unicode, ensure_ascii=False)
        encoded_metainfo = hexlify(json_dump.encode('utf-8'))
        return RESTResponse({"metainfo": encoded_metainfo,
                             "download_exists": download and not download_is_metainfo_request})
