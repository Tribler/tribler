
from aiohttp import web

from libtorrent import bencode

from tribler_core.components.restapi.rest.rest_endpoint import HTTP_BAD_REQUEST, RESTResponse
from tribler_core.tests.tools.tracker.tracker_info import TrackerInfo


class HTTPTracker:

    def __init__(self, port):
        super().__init__()
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

        attempts = 0
        while attempts < 20:
            try:
                self.site = web.TCPSite(runner, 'localhost', self.port)
                await self.site.start()
                break
            except OSError:
                attempts += 1
                self.port += 1

    async def stop(self):
        """
        Stop the HTTP Tracker, returns a deferred that fires when the server is closed.
        """
        if self.site:
            return await self.site.stop()

    async def handle_scrape_request(self, request):
        """
        Return a bencoded dictionary with information about the queried infohashes.
        """
        if 'info_hash' not in request.query:
            return RESTResponse("infohash argument missing", status=HTTP_BAD_REQUEST)

        response_dict = {'files': {}}
        for infohash in request.query['info_hash']:
            if not self.tracker_info.has_info_about_infohash(infohash):
                return RESTResponse(f"no info about infohash {infohash}", status=HTTP_BAD_REQUEST)

            info_dict = self.tracker_info.get_info_about_infohash(infohash)
            response_dict['files'][infohash] = {'complete': info_dict['seeders'],
                                                'downloaded': info_dict['downloaded'],
                                                'incomplete': info_dict['leechers']}

        return RESTResponse(bencode(response_dict))
