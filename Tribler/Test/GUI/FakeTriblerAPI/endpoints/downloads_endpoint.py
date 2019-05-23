from __future__ import absolute_import

import cgi
import json
from binascii import hexlify, unhexlify

from six import text_type

from twisted.web import http, resource

import Tribler.Test.GUI.FakeTriblerAPI.tribler_utils as tribler_utils


class DownloadsEndpoint(resource.Resource):

    def getChild(self, path, request):
        return DownloadEndpoint(path)

    def render_GET(self, request):
        get_peers = False
        if 'get_peers' in request.args and request.args['get_peers'] \
                and request.args['get_peers'][0] == "1":
            get_peers = True

        get_pieces = False
        if 'get_pieces' in request.args and request.args['get_pieces'] \
                and request.args['get_pieces'][0] == "1":
            get_pieces = True

        return json.dumps({"downloads": [download.get_json(get_peers=get_peers, get_pieces=get_pieces)
                                         for download in tribler_utils.tribler_data.downloads]})

    def render_PUT(self, request):
        headers = request.getAllHeaders()
        cgi.FieldStorage(fp=request.content, headers=headers,
                         environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': headers['content-type']})

        # Just start a fake download
        tribler_utils.tribler_data.start_random_download()

        return json.dumps({"added": True})


class DownloadEndpoint(resource.Resource):

    def __init__(self, infohash):
        resource.Resource.__init__(self)
        self.infohash = unhexlify(infohash)
        self.putChild("files", DownloadFilesEndpoint(self.infohash))

    def render_PATCH(self, request):
        download = tribler_utils.tribler_data.get_download_with_infohash(self.infohash)
        parameters = http.parse_qs(request.content.read(), 1)

        if 'selected_files[]' in parameters:
            selected_files_list = [text_type(f, 'utf-8') for f in parameters['selected_files[]']]
            download.set_selected_files(selected_files_list)

        if 'state' in parameters and parameters['state']:
            state = parameters['state'][0]
            if state == "resume":
                download.status = 3
            elif state == "stop":
                download.status = 5
            elif state == "recheck":
                download.status = 2
            else:
                request.setResponseCode(http.BAD_REQUEST)
                return json.dumps({"error": "unknown state parameter"})

        return json.dumps({"modified": True, "infohash": hexlify(self.infohash)})


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
        return json.dumps({"error": message})


class DownloadFilesEndpoint(DownloadBaseEndpoint):

    def __init__(self, infohash):
        DownloadBaseEndpoint.__init__(self, infohash)
        self.infohash = infohash

    def render_GET(self, _):
        return json.dumps({"files": tribler_utils.tribler_data.get_download_with_infohash(self.infohash).files})
