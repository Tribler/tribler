from __future__ import absolute_import

import hashlib
import logging
from binascii import hexlify

from libtorrent import bdecode, bencode

from six import text_type
from six.moves.urllib.request import url2pathname

from twisted.internet.defer import Deferred
from twisted.internet.error import ConnectError, ConnectionLost, DNSLookupError
from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import BLOB_EXTENSION
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, \
    REGULAR_TORRENT, read_payload
from Tribler.Core.Utilities.utilities import fix_torrent, http_get, parse_magnetlink, unichar_string
from Tribler.Core.exceptions import HttpError, InvalidSignatureException
from Tribler.util import cast_to_unicode_utf8


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

                    curl -X PUT http://localhost:8085/torrentinfo?torrent=file:/home/me/test.torrent

            **Example response**:

                .. sourcecode:: javascript

                    {"metainfo": <torrent metainfo dictionary>}
        """

        def on_got_metainfo(metainfo):
            if not isinstance(metainfo, dict) or 'info' not in metainfo:
                self._logger.warning("Received metainfo is not a valid dictionary")
                request.setResponseCode(http.INTERNAL_SERVER_ERROR)
                request.write(json.dumps({"error": 'invalid response'}))
                self.finish_request(request)
                return

            # TODO(Martijn): store the stuff in a database!!!
            infohash = hashlib.sha1(bencode(metainfo['info'])).digest()

            # Check if the torrent is already in the downloads
            metainfo['download_exists'] = infohash in self.session.lm.downloads
            encoded_metainfo = hexlify(json.dumps(metainfo, ensure_ascii=False))

            request.write(json.dumps({"metainfo": encoded_metainfo}))
            self.finish_request(request)

        def on_metainfo_timeout(_):
            if not request.finished:
                request.setResponseCode(http.REQUEST_TIMEOUT)
                request.write(json.dumps({"error": "timeout"}))
            # If the above request.write failed, the request will have already been finished
            if not request.finished:
                self.finish_request(request)

        def on_lookup_error(failure):
            failure.trap(ConnectError, DNSLookupError, HttpError, ConnectionLost)
            request.setResponseCode(http.INTERNAL_SERVER_ERROR)
            request.write(json.dumps({"error": unichar_string(failure.getErrorMessage())}))
            self.finish_request(request)

        def _on_loaded(response):
            if response.startswith('magnet'):
                _, infohash, _ = parse_magnetlink(response)
                if infohash:
                    self.session.lm.ltmgr.get_metainfo(response, callback=metainfo_deferred.callback, timeout=20,
                                                       timeout_callback=on_metainfo_timeout, notify=True)
                    return
            metainfo_deferred.callback(bdecode(response))

        def on_mdblob(filename):
            try:
                with open(filename, 'rb') as f:
                    serialized_data = f.read()
                payload = read_payload(serialized_data)
                if payload.metadata_type not in [REGULAR_TORRENT, CHANNEL_TORRENT]:
                    request.setResponseCode(http.INTERNAL_SERVER_ERROR)
                    return json.dumps({"error": "Non-torrent metadata type"})
                magnet = payload.get_magnet()
            except InvalidSignatureException:
                request.setResponseCode(http.INTERNAL_SERVER_ERROR)
                return json.dumps({"error": "metadata has incorrect signature"})
            else:
                return on_magnet(magnet)

        def on_file():
            try:
                filename = url2pathname(uri[5:].encode('utf-8') if isinstance(uri, text_type) else uri[5:])
                if filename.endswith(BLOB_EXTENSION):
                    return on_mdblob(filename)
                metainfo_deferred.callback(bdecode(fix_torrent(filename)))
                return NOT_DONE_YET
            except TypeError:
                request.setResponseCode(http.INTERNAL_SERVER_ERROR)
                return json.dumps({"error": "error while decoding torrent file"})

        def on_magnet(mlink=None):
            infohash = parse_magnetlink(mlink or uri)[1]
            if infohash is None:
                request.setResponseCode(http.BAD_REQUEST)
                return json.dumps({"error": "missing infohash"})

            self.session.lm.ltmgr.get_metainfo(mlink or uri, callback=metainfo_deferred.callback, timeout=20,
                                               timeout_callback=on_metainfo_timeout, notify=True)
            return NOT_DONE_YET

        metainfo_deferred = Deferred()
        metainfo_deferred.addCallback(on_got_metainfo)

        if 'uri' not in request.args or not request.args['uri']:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "uri parameter missing"})

        uri = cast_to_unicode_utf8(request.args['uri'][0])

        if uri.startswith('file:'):
            return on_file()
        elif uri.startswith('http'):
            http_get(uri.encode('utf-8')).addCallback(_on_loaded).addErrback(on_lookup_error)
        elif uri.startswith('magnet'):
            return on_magnet()
        else:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "invalid uri"})

        return NOT_DONE_YET
