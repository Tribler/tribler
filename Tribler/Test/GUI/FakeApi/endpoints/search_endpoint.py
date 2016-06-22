import json
from random import randint, sample

from twisted.web import http, resource

import tribler_utils


class SearchEndpoint(resource.Resource):

    def __init__(self, events_endpoint):
        resource.Resource.__init__(self)
        self.events_endpoint = events_endpoint

        self.putChild("suggestions", SearchSuggestionsEndpoint())
        self.putChild("completions", SearchCompletionsEndpoint())

    def render_GET(self, request):
        # Just ignore the query and return some random channels/torrents
        num_channels = len(tribler_utils.tribler_data.channels)
        num_torrents = len(tribler_utils.tribler_data.torrents)

        picked_torrents = sample(range(0, num_torrents - 1), randint(20, num_channels - 1))
        picked_channels = sample(range(0, num_channels - 1), randint(20, num_channels - 1))

        torrents_json = []
        for index in picked_torrents:
            torrents_json.append(tribler_utils.tribler_data.torrents[index].get_json())

        self.events_endpoint.on_search_results_torrents(torrents_json)

        channels_json = []
        for index in picked_channels:
            channels_json.append(tribler_utils.tribler_data.channels[index].get_json())

        self.events_endpoint.on_search_results_channels(channels_json)

        return json.dumps({"queried": True})


class SearchSuggestionsEndpoint(resource.Resource):

    def render_GET(self, request):
        if 'q' not in request.args:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "kw parameter missing"})

        return json.dumps({"suggestions": ["tribler1", "tribler2", "tribler3"]})


class SearchCompletionsEndpoint(resource.Resource):

    def render_GET(self, request):
        if 'q' not in request.args:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "kw parameter missing"})

        return json.dumps({"completions": ["tribler1", "tribler2", "tribler3", "tribler4", "tribler5"]})
