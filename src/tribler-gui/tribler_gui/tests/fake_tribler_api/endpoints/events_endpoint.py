import json
from asyncio import CancelledError, sleep

from aiohttp import web

from tribler_common.simpledefs import NTFY

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTStreamResponse


class EventsEndpoint(RESTEndpoint):
    def __init__(self, *args, **kwargs):
        super(EventsEndpoint, self).__init__(*args, **kwargs)
        self.event_response = None

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_events)])

    def on_search_results_channels(self, results):
        for result in results:
            self.event_response.write(json.dumps({"type": "search_result_channel", "event": {"result": result}}) + '\n')

    def on_search_results_torrents(self, results):
        for result in results:
            self.event_response.write(json.dumps({"type": "search_result_torrent", "event": {"result": result}}) + '\n')

    async def get_events(self, request):
        self.event_response = RESTStreamResponse(status=200, reason='OK', headers={'Content-Type': 'text/html'})
        await self.event_response.prepare(request)
        await self.event_response.write(
            json.dumps({"type": NTFY.EVENTS_START.value,
                        "event": {"tribler_started": True,
                                  "version": "1.2.3"}}).encode('utf-8') + b'\n')

        try:
            while True:
                await sleep(3600)
        except CancelledError:
            response = self.event_response
            self.event_response = None
            return response
