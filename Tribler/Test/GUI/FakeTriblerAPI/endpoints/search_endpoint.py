from __future__ import absolute_import

from random import Random

from twisted.web import http, resource

import Tribler.Core.Utilities.json_util as json
import Tribler.Test.GUI.FakeTriblerAPI.tribler_utils as tribler_utils
from Tribler.Core.Utilities.unicode import recursive_unicode


class SearchEndpoint(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)

        self.putChild(b"completions", SearchCompletionsEndpoint())

    @staticmethod
    def sanitize_parameters(parameters):
        """
        Sanitize the parameters and check whether they exist
        """
        first = 1 if 'first' not in parameters else int(parameters['first'][0])  # TODO check integer!
        last = 50 if 'last' not in parameters else int(parameters['last'][0])  # TODO check integer!
        sort_by = None if 'sort_by' not in parameters else parameters['sort_by'][0]  # TODO check integer!
        sort_asc = True if 'sort_desc' not in parameters else bool(int(parameters['sort_desc'][0]))
        query_filter = None if 'filter' not in parameters else parameters['filter'][0]
        md_type = None if 'type' not in parameters else parameters['type'][0]

        return first, last, sort_by, sort_asc, md_type, query_filter

    def base_get(self, request):

        args = recursive_unicode(request.args)
        if 'filter' not in args:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "filter parameter missing"})

        first, last, sort_by, sort_asc, md_type, query = SearchEndpoint.sanitize_parameters(args)
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

        if sort_by and sort_by not in ['category', 'size']:
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
        args = recursive_unicode(request.args)
        include_total = args['include_total'][0] if 'include_total' in args else ''
        first, last, sort_by, sort_asc, search_results = self.base_get(request)
        result = {
            "results": search_results[first - 1 : last],
            "first": first,
            "last": last,
            "sort_by": sort_by,
            "sort_desc": sort_asc,
        }
        if include_total:
            result.update({"total": len(search_results)})
        return json.twisted_dumps(result)


class SearchCompletionsEndpoint(resource.Resource):
    def render_GET(self, request):
        args = recursive_unicode(request.args)
        if 'q' not in args:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "q parameter missing"})

        return json.twisted_dumps({"completions": ["tribler1", "tribler2", "tribler3", "tribler4", "tribler5"]})
