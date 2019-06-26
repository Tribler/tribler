from __future__ import absolute_import

import json
from random import Random

from twisted.web import http, resource

import Tribler.Test.GUI.FakeTriblerAPI.tribler_utils as tribler_utils


class SearchEndpoint(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)

        self.putChild("completions", SearchCompletionsEndpoint())
        self.putChild("count", SearchCountEndpoint())

    @staticmethod
    def sanitize_parameters(parameters):
        """
        Sanitize the parameters and check whether they exist
        """
        first = 1 if 'first' not in parameters else int(parameters['first'][0])  # TODO check integer!
        last = 50 if 'last' not in parameters else int(parameters['last'][0])  # TODO check integer!
        sort_by = None if 'sort_by' not in parameters else parameters['sort_by'][0]  # TODO check integer!
        sort_asc = True if 'sort_asc' not in parameters else bool(int(parameters['sort_asc'][0]))
        query_filter = None if 'filter' not in parameters else parameters['filter'][0]
        md_type = None if 'type' not in parameters else parameters['type'][0]

        return first, last, sort_by, sort_asc, md_type, query_filter

    def base_get(self, request):

        if 'filter' not in request.args:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "filter parameter missing"})

        first, last, sort_by, sort_asc, md_type, query = SearchEndpoint.sanitize_parameters(request.args)
        random = Random()
        random.seed(hash(query))

        num_channels = len(tribler_utils.tribler_data.channels)
        num_torrents = len(tribler_utils.tribler_data.torrents)
        picked_torrents = random.sample(list(range(0, num_torrents - 1)), random.randint(20, num_channels - 1))
        picked_channels = random.sample(list(range(0, num_channels - 1)), random.randint(5, min(20, num_channels - 1)))

        torrents_json = []
        for index in picked_torrents:
            torrent_json = tribler_utils.tribler_data.torrents[index].get_json()
            torrent_json['type'] = 'torrent'
            torrents_json.append(torrent_json)

        if sort_by:
            torrents_json.sort(key=lambda result: result[sort_by] if sort_by in result else None, reverse=not sort_asc)

        channels_json = []
        for index in picked_channels:
            channel_json = tribler_utils.tribler_data.channels[index].get_json()
            channel_json['type'] = 'channel'
            channels_json.append(channel_json)

        if sort_by and sort_by != 'category':
            channels_json.sort(key=lambda result: result[sort_by] if sort_by in result else None, reverse=not sort_asc)

        if not md_type:
            search_results = channels_json + torrents_json
        elif md_type == 'channel':
            search_results = channels_json
        elif md_type == 'torrent':
            search_results = torrents_json
        else:
            search_results = []

        return first, last, sort_by, sort_asc, search_results

    def render_GET(self, request):
        first, last, sort_by, sort_asc, search_results = self.base_get(request)
        return json.dumps({
            "results": search_results[first-1:last],
            "first": first,
            "last": last,
            "sort_by": sort_by,
            "sort_asc": sort_asc,
        })


class SearchCountEndpoint(SearchEndpoint):
    def __init__(self):
        resource.Resource.__init__(self)

    def render_GET(self, request):
        _, _, _, _, search_results = self.base_get(request)
        return json.dumps({"total": len(search_results)})


class SearchCompletionsEndpoint(resource.Resource):

    def render_GET(self, request):
        if 'q' not in request.args:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "q parameter missing"})

        return json.dumps({"completions": ["tribler1", "tribler2", "tribler3", "tribler4", "tribler5"]})
