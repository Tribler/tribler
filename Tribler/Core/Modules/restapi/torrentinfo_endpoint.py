import json
from urllib import url2pathname
from libtorrent import bdecode
from twisted.internet.defer import Deferred

from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET
from Tribler.Core.Utilities.utilities import fix_torrent, http_get


class TorrentInfoEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing all requests regarding torrent info in Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

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
        metainfo_deferred = Deferred()

        def on_got_metainfo(metainfo):
            del metainfo['info']['pieces']
            request.write(json.dumps({"metainfo": metainfo}))
            request.finish()

        if 'uri' not in request.args or len(request.args['uri']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "uri parameter missing"})

        uri = request.args['uri'][0]
        if uri.startswith('file:'):
            filename = url2pathname(uri[5:])
            torrent_data = fix_torrent(filename)
            metainfo_deferred.callback(bdecode(torrent_data))
        elif uri.startswith('http'):
            def _on_loaded(tdef):
                metainfo_deferred.callback(bdecode(tdef))
            http_get(uri).addCallback(_on_loaded)
        elif uri.startswith('magnet'):
            self.session.lm.ltmgr.get_metainfo(uri, callback=metainfo_deferred.callback, timeout=20,
                                               timeout_callback=metainfo_deferred.errback, notify=True)
        else:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "invalid uri"})

        metainfo_deferred.addCallback(on_got_metainfo)

        return NOT_DONE_YET
