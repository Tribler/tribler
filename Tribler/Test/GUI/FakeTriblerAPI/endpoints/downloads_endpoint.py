from __future__ import absolute_import

import cgi
from binascii import unhexlify

from six import text_type

from twisted.web import http, resource

import Tribler.Core.Utilities.json_util as json
import Tribler.Test.GUI.FakeTriblerAPI.tribler_utils as tribler_utils
from Tribler.Core.Utilities.unicode import hexlify


class DownloadsEndpoint(resource.Resource):

    def getChild(self, path, request):
        return DownloadEndpoint(path)

    def render_GET(self, request):
        get_peers = False
        if b'get_peers' in request.args and request.args[b'get_peers'] \
                and request.args[b'get_peers'][0] == b"1":
            get_peers = True

        get_pieces = False
        if b'get_pieces' in request.args and request.args[b'get_pieces'] \
                and request.args[b'get_pieces'][0] == b"1":
            get_pieces = True

        return json.twisted_dumps({"downloads": [download.get_json(get_peers=get_peers, get_pieces=get_pieces)
                                                 for download in tribler_utils.tribler_data.downloads]})

    def render_PUT(self, request):
        headers = request.getAllHeaders()
        cgi.FieldStorage(fp=request.content, headers=headers,
                         environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': headers[b'content-type']})

        # Just start a fake download
        tribler_utils.tribler_data.start_random_download()

        return json.twisted_dumps({"added": True})


class DownloadEndpoint(resource.Resource):

    def __init__(self, infohash):
        resource.Resource.__init__(self)
        self.infohash = unhexlify(infohash)
        self.putChild(b"files", DownloadFilesEndpoint(self.infohash))

    def render_PATCH(self, request):
        download = tribler_utils.tribler_data.get_download_with_infohash(self.infohash)
        parameters = http.parse_qs(request.content.read(), 1)

        if b'selected_files[]' in parameters:
            selected_files_list = [text_type(f, 'utf-8') for f in parameters[b'selected_files[]']]
            download.set_selected_files(selected_files_list)

        if b'state' in parameters and parameters[b'state']:
            state = parameters[b'state'][0]
            if state == b"resume":
                download.status = 3
            elif state == b"stop":
                download.status = 5
            elif state == b"recheck":
                download.status = 2
            else:
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps({"error": "unknown state parameter"})

        return json.twisted_dumps({"modified": True, "infohash": hexlify(self.infohash)})


class DownloadBaseEndpoint(resource.Resource):

    def __init__(self, infohash):
        resource.Resource.__init__(self)
        self.infohash = infohash

    @staticmethod
    def return_404(request, message="the download with given infohash does not exist"):
        """
        Returns a 404 response code if your channel has not been created.
        """
        request.setResponseCode(http.NOT_FOUND)
        return json.twisted_dumps({"error": message})


class DownloadFilesEndpoint(DownloadBaseEndpoint):

    def __init__(self, infohash):
        DownloadBaseEndpoint.__init__(self, infohash)
        self.infohash = infohash

    def render_GET(self, _):
        return json.twisted_dumps({"files": tribler_utils.tribler_data.get_download_with_infohash(self.infohash).files})
