from __future__ import absolute_import

import hashlib
import logging
from copy import deepcopy

from libtorrent import bencode

from six.moves.urllib.request import url2pathname

from twisted.internet.error import ConnectError, ConnectionLost, DNSLookupError
from twisted.web import http, resource
from twisted.web.error import SchemeNotSupported
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.MetadataStore.OrmBindings.torrent_metadata import tdef_to_metadata_dict
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.unicode import hexlify, recursive_unicode
from Tribler.Core.Utilities.utilities import bdecode_compat, http_get, parse_magnetlink, unichar_string
from Tribler.Core.exceptions import HttpError


class TorrentInfoEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing all requests regarding torrent info in Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self._logger = logging.getLogger(self.__class__.__name__)

    def finish_request(self, request):
        try:
            request.finish()
        except RuntimeError:
            self._logger.warning("Writing response failed, probably the client closed the connection already.")

    def render_GET(self, request):
        """
        .. http:get:: /torrentinfo

        A GET request to this endpoint will return information from a torrent found at a provided URI.
        This URI can either represent a file location, a magnet link or a HTTP(S) url.
        - torrent: the URI of the torrent file that should be downloaded. This parameter is required.

            **Example request**:

                .. sourcecode:: none

                    curl -X GET http://localhost:8085/torrentinfo?torrent=file:/home/me/test.torrent

            **Example response**:

                .. sourcecode:: javascript

                    {"metainfo": <torrent metainfo dictionary>}
        """

        def on_got_metainfo(metainfo):
            if not metainfo:
                if not request.finished:
                    request.setResponseCode(http.INTERNAL_SERVER_ERROR)
                    request.write(json.twisted_dumps({"error": "metainfo error"}))
                # If the above request.write failed, the request will have already been finished
                if not request.finished:
                    self.finish_request(request)
                    return

            if not isinstance(metainfo, dict) or b'info' not in metainfo:
                self._logger.warning("Received metainfo is not a valid dictionary")
                request.setResponseCode(http.INTERNAL_SERVER_ERROR)
                request.write(json.twisted_dumps({"error": 'invalid response'}))
                self.finish_request(request)
                return

            # Add the torrent to GigaChannel as a free-for-all entry, so others can search it
            self.session.lm.mds.TorrentMetadata.add_ffa_from_dict(
                tdef_to_metadata_dict(TorrentDef.load_from_dict(metainfo)))

            # TODO(Martijn): store the stuff in a database!!!
            # TODO(Vadim): this means cache the downloaded torrent in a binary storage, like LevelDB
            infohash = hashlib.sha1(bencode(metainfo[b'info'])).digest()

            # Check if the torrent is already in the downloads
            encoded_metainfo = deepcopy(metainfo)
            encoded_metainfo['download_exists'] = infohash in self.session.lm.downloads
            # FIXME: json.dumps garbles binary data that is used by the 'pieces' field
            # However, this is fine as long as the GUI does not use this field.
            encoded_metainfo[b'info'][b'pieces'] = hexlify(encoded_metainfo[b'info'][b'pieces']).encode('utf-8')
            encoded_metainfo = hexlify(json.dumps(recursive_unicode(encoded_metainfo, ignore_errors=True),
                                                  ensure_ascii=False).encode('utf-8'))

            request.write(json.twisted_dumps({"metainfo": encoded_metainfo}))
            self.finish_request(request)

        def on_lookup_error(failure):
            failure.trap(ConnectError, DNSLookupError, HttpError, ConnectionLost, SchemeNotSupported)
            request.setResponseCode(http.INTERNAL_SERVER_ERROR)
            request.write(json.twisted_dumps({"error": unichar_string(failure.getErrorMessage())}))
            self.finish_request(request)

        def _on_loaded(response):
            if response.startswith(b'magnet'):
                _, infohash, _ = parse_magnetlink(response)
                if infohash:
                    self.session.lm.ltmgr.get_metainfo(infohash, timeout=20).addCallback(on_got_metainfo)
                    return

            # Otherwise, we directly invoke the on_got_metainfo method
            try:
                decoded_response = bdecode_compat(response)
                on_got_metainfo(decoded_response)
            except RuntimeError:
                # The decoding failed - handle it like a None metainfo
                on_got_metainfo(None)

        def on_file():
            try:
                filename = url2pathname(uri[5:])
                tdef = TorrentDef.load(filename)
                on_got_metainfo(tdef.get_metainfo())
                return NOT_DONE_YET
            except (TypeError, RuntimeError):
                request.setResponseCode(http.INTERNAL_SERVER_ERROR)
                return json.twisted_dumps({"error": "error while decoding torrent file"})

        def on_magnet(mlink=None):
            infohash = parse_magnetlink(mlink or uri)[1]
            if infohash is None:
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps({"error": "missing infohash"})

            self.session.lm.ltmgr.get_metainfo(infohash, timeout=20).addCallback(on_got_metainfo)
            return NOT_DONE_YET

        args = recursive_unicode(request.args)
        if 'uri' not in args or not args['uri']:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "uri parameter missing"})

        uri = args['uri'][0]
        if uri.startswith('file:'):
            return on_file()
        elif uri.startswith('http'):
            http_get(uri.encode('utf-8')).addCallback(_on_loaded).addErrback(on_lookup_error)
        elif uri.startswith('magnet'):
            return on_magnet()
        else:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "invalid uri"})

        return NOT_DONE_YET
