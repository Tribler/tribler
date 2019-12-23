from binascii import hexlify

from aiohttp import web

from libtorrent import bencode

from Tribler.Core.Modules.restapi.rest_endpoint import HTTP_BAD_REQUEST, RESTResponse
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Test.util.Tracker.TrackerInfo import TrackerInfo


class HTTPTracker(object):

    def __init__(self, port):
        super(HTTPTracker, self).__init__()
        self.listening_port = None
        self.site = None
        self.port = port
        self.tracker_info = TrackerInfo()

    async def start(self):
        """
        Start the HTTP Tracker
        """
        app = web.Application()
        app.add_routes([web.get('/scrape', self.handle_scrape_request)])
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        self.site = web.TCPSite(runner, 'localhost', self.port)
        await self.site.start()

    async def stop(self):
        """
        Stop the HTTP Tracker, returns a deferred that fires when the server is closed.
        """
        return await self.site.stop()

    async def handle_scrape_request(self, request):
        """
        Return a bencoded dictionary with information about the queried infohashes.
        """
        parameters = await request.post()
        if 'info_hash' not in parameters:
            return RESTResponse("infohash argument missing", status=HTTP_BAD_REQUEST)

        response_dict = {'files': {}}
        for infohash in request.args[b'info_hash']:
            if not self.session.tracker_info.has_info_about_infohash(infohash):
                return RESTResponse("no info about infohash %s" % hexlify(infohash), status=HTTP_BAD_REQUEST)

            info_dict = self.session.tracker_info.get_info_about_infohash(infohash)
            response_dict['files'][infohash] = {'complete': info_dict['seeders'],
                                                'downloaded': info_dict['downloaded'],
                                                'incomplete': info_dict['leechers']}

        return RESTResponse(bencode(response_dict))
