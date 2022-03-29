import hashlib
import json
from copy import deepcopy

from aiohttp import ClientResponseError, ClientSession, ServerConnectionError, web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import String

from tribler.core import notifications
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.libtorrent.utils.libtorrent_helper import libtorrent as lt
from tribler.core.components.metadata_store.db.orm_bindings.torrent_metadata import tdef_to_metadata_dict
from tribler.core.components.restapi.rest.rest_endpoint import (
    RESTEndpoint,
    RESTResponse,
)
from tribler.core.utilities.rest_utils import (
    FILE_SCHEME,
    HTTPS_SCHEME,
    HTTP_SCHEME,
    MAGNET_SCHEME,
    scheme_from_uri,
    uri_to_path,
)
from tribler.core.utilities.unicode import hexlify, recursive_unicode
from tribler.core.utilities.utilities import bdecode_compat, froze_it, parse_magnetlink


async def query_http_uri(uri: str) -> bytes:
    # This is moved to a separate method to be able to patch it separately,
    # for compatibility with pytest-aiohttp
    async with ClientSession(raise_for_status=True) as session:
        response = await session.get(uri)
        response = await response.read()
        return response


@froze_it
class TorrentInfoEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing all requests regarding torrent info in Tribler.
    """

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
                return self.bad_request(f"wrong value of 'hops' parameter: {hops}")

        if not uri:
            return self.bad_request("uri parameter missing")

        metainfo = None
        scheme = scheme_from_uri(uri)

        if scheme == FILE_SCHEME:
            file = uri_to_path(uri)
            try:
                tdef = TorrentDef.load(file)
                metainfo = tdef.metainfo
            except (TypeError, ValueError, RuntimeError) as e:
                return self.internal_error(e, f"error while decoding torrent file: {file}")
        elif scheme in (HTTP_SCHEME, HTTPS_SCHEME):
            try:
                response = await query_http_uri(uri)
            except (ServerConnectionError, ClientResponseError) as e:
                return self.internal_error(e)

            if response.startswith(b'magnet'):
                _, infohash, _ = parse_magnetlink(response)
                if infohash:
                    metainfo = await self.download_manager.get_metainfo(infohash, timeout=60, hops=hops, url=response)
            else:
                metainfo = bdecode_compat(response)
        elif scheme == MAGNET_SCHEME:
            infohash = parse_magnetlink(uri)[1]
            if infohash is None:
                return self.bad_request("missing infohash")
            metainfo = await self.download_manager.get_metainfo(infohash, timeout=60, hops=hops, url=uri)
        else:
            return self.bad_request("invalid uri")

        if not metainfo:
            return self.internal_error(msg="metainfo error")

        if not isinstance(metainfo, dict) or b'info' not in metainfo:
            self._logger.warning("Received metainfo is not a valid dictionary")
            return self.internal_error(msg="Received metainfo is not a valid dictionary")

        # Add the torrent to GigaChannel as a free-for-all entry, so others can search it
        self.download_manager.notifier[notifications.torrent_metadata_added](
            tdef_to_metadata_dict(TorrentDef.load_from_dict(metainfo)))

        # TODO(Martijn): store the stuff in a database!!!
        # TODO(Vadim): this means cache the downloaded torrent in a binary storage, like LevelDB
        infohash = hashlib.sha1(lt.bencode(metainfo[b'info'])).digest()

        download = self.download_manager.downloads.get(infohash)
        metainfo_request = self.download_manager.metainfo_requests.get(infohash, [None])[0]
        download_is_metainfo_request = download == metainfo_request

        # Check if the torrent is already in the downloads
        encoded_metainfo = deepcopy(metainfo)

        # FIXME: json.dumps garbles binary data that is used by the 'pieces' field
        # However, this is fine as long as the GUI does not use this field.
        encoded_metainfo[b'info'][b'pieces'] = hexlify(encoded_metainfo[b'info'][b'pieces']).encode('utf-8')
        encoded_metainfo = hexlify(json.dumps(recursive_unicode(
            encoded_metainfo, ignore_errors=True), ensure_ascii=False).encode('utf-8'))
        return RESTResponse({"metainfo": encoded_metainfo,
                             "download_exists": download and not download_is_metainfo_request})
