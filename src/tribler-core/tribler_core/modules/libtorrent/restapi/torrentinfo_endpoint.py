import hashlib
import json
from copy import deepcopy
from urllib.request import url2pathname

from aiohttp import ClientResponseError, ClientSession, ServerConnectionError, web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from libtorrent import bencode

from marshmallow.fields import String

import tribler_core.utilities.json_util as json
from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.orm_bindings.torrent_metadata import tdef_to_metadata_dict
from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR, RESTEndpoint, RESTResponse
from tribler_core.utilities.unicode import hexlify, recursive_unicode
from tribler_core.utilities.utilities import bdecode_compat, parse_magnetlink


class TorrentInfoEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing all requests regarding torrent info in Tribler.
    """

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
        args = request.query

        hops = None
        if 'hops' in args:
            try:
                hops = int(args['hops'])
            except ValueError:
                return RESTResponse({"error": f"wrong value of 'hops' parameter: {repr(args['hops'])}"},
                                    status=HTTP_BAD_REQUEST)

        if 'uri' not in args or not args['uri']:
            return RESTResponse({"error": "uri parameter missing"}, status=HTTP_BAD_REQUEST)

        uri = args['uri']
        if uri.startswith('file:'):
            try:
                filename = url2pathname(uri[5:])
                tdef = TorrentDef.load(filename)
                metainfo = tdef.get_metainfo()
            except (TypeError, RuntimeError):
                return RESTResponse({"error": "error while decoding torrent file"}, status=HTTP_INTERNAL_SERVER_ERROR)
        elif uri.startswith('http'):
            try:
                async with ClientSession(raise_for_status=True) as session:
                    response = await session.get(uri)
                    response = await response.read()
            except (ServerConnectionError, ClientResponseError) as e:
                return RESTResponse({"error": str(e)}, status=HTTP_INTERNAL_SERVER_ERROR)

            if response.startswith(b'magnet'):
                _, infohash, _ = parse_magnetlink(response)
                if infohash:
                    metainfo = await self.session.dlmgr.get_metainfo(infohash, timeout=60, hops=hops, url=response)
            else:
                metainfo = bdecode_compat(response)
        elif uri.startswith('magnet'):
            infohash = parse_magnetlink(uri)[1]
            if infohash is None:
                return RESTResponse({"error": "missing infohash"}, status=HTTP_BAD_REQUEST)
            metainfo = await self.session.dlmgr.get_metainfo(infohash, timeout=60, hops=hops, url=uri)
        else:
            return RESTResponse({"error": "invalid uri"}, status=HTTP_BAD_REQUEST)

        if not metainfo:
            return RESTResponse({"error": "metainfo error"}, status=HTTP_INTERNAL_SERVER_ERROR)

        if not isinstance(metainfo, dict) or b'info' not in metainfo:
            self._logger.warning("Received metainfo is not a valid dictionary")
            return RESTResponse({"error": "invalid response"}, status=HTTP_INTERNAL_SERVER_ERROR)

        # Add the torrent to GigaChannel as a free-for-all entry, so others can search it
        self.session.mds.TorrentMetadata.add_ffa_from_dict(
            tdef_to_metadata_dict(TorrentDef.load_from_dict(metainfo)))

        # TODO(Martijn): store the stuff in a database!!!
        # TODO(Vadim): this means cache the downloaded torrent in a binary storage, like LevelDB
        infohash = hashlib.sha1(bencode(metainfo[b'info'])).digest()

        download = self.session.dlmgr.downloads.get(infohash)
        metainfo_request = self.session.dlmgr.metainfo_requests.get(infohash, [None])[0]
        download_is_metainfo_request = download == metainfo_request

        # Check if the torrent is already in the downloads
        encoded_metainfo = deepcopy(metainfo)

        # FIXME: json.dumps garbles binary data that is used by the 'pieces' field
        # However, this is fine as long as the GUI does not use this field.
        encoded_metainfo[b'info'][b'pieces'] = hexlify(encoded_metainfo[b'info'][b'pieces']).encode('utf-8')
        encoded_metainfo = hexlify(json.dumps(recursive_unicode(encoded_metainfo, ignore_errors=True), ensure_ascii=False).encode('utf-8'))
        return RESTResponse({"metainfo": encoded_metainfo,
                             "download_exists": download and not download_is_metainfo_request})
