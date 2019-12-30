import cgi
from binascii import unhexlify

from aiohttp import web

from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, HTTP_NOT_FOUND, RESTEndpoint, RESTResponse
from tribler_core.utilities.unicode import hexlify

import tribler_gui.tests.fake_tribler_api.tribler_utils as tribler_utils


class DownloadsEndpoint(RESTEndpoint):

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_downloads),
                             web.put('', self.add_download),
                             web.delete('/{infohash}', self.return_404),
                             web.patch('/{infohash}', self.update_download),
                             web.get('/{infohash}/torrent', self.return_404),
                             web.get('/{infohash}/files', self.get_files)])

    async def get_downloads(self, request):
        get_peers = request.query.get('get_peers', False)
        get_pieces = request.query.get('get_pieces', False)
        return RESTResponse({"downloads": [download.get_json(get_peers=get_peers, get_pieces=get_pieces)
                                           for download in tribler_utils.tribler_data.downloads]})

    async def add_download(self, request):
        headers = request.getAllHeaders()
        cgi.FieldStorage(fp=request.content, headers=headers,
                         environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': headers[b'content-type']})

        # Just start a fake download
        tribler_utils.tribler_data.start_random_download()

        return RESTResponse({"added": True})

    async def update_download(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = tribler_utils.tribler_data.get_download_with_infohash(infohash)
        parameters = request.query

        if 'selected_files' in parameters:
            selected_files_list = [str(f, 'utf-8') for f in parameters['selected_files']]
            download.set_selected_files(selected_files_list)

        if 'state' in parameters and parameters['state']:
            state = parameters['state']
            if state == "resume":
                download.status = 3
            elif state == "stop":
                download.status = 5
            elif state == "recheck":
                download.status = 2
            else:
                return RESTResponse({"error": "unknown state parameter"}, status=HTTP_BAD_REQUEST)

        return RESTResponse({"modified": True, "infohash": hexlify(infohash)})

    async def get_files(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        return RESTResponse({"files": tribler_utils.tribler_data.get_download_with_infohash(infohash).files})

    async def return_404(request, message="the download with given infohash does not exist"):
        return RESTResponse({"error": message}, HTTP_NOT_FOUND)
